from __future__ import annotations

import contextlib
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from queue import Empty, Queue
from threading import Event, Lock, Thread
from typing import TypeVar

from PIL import Image

from desktranslate.algorithms import PRESETS, FrameGate, TextStabilizer, preprocess
from desktranslate.context import TranslationCache, TranslationContext, cache_key
from desktranslate.errors import Cancelled, DeskTranslateError, ProviderRateLimitError
from desktranslate.models import (
    CaptureProvider,
    OCREngine,
    PipelineEvent,
    SessionState,
    Stamp,
    TranslationProvider,
    TranslationRequest,
)
from desktranslate.settings import Settings

T = TypeVar("T")


class LatestMailbox[T]:
    """Exactly one pending item. Producers replace obsolete work without blocking."""

    def __init__(self) -> None:
        self.queue: Queue[T] = Queue(maxsize=1)
        self.lock = Lock()

    def put(self, value: T) -> None:
        with self.lock:
            with contextlib.suppress(Empty):
                self.queue.get_nowait()
            self.queue.put_nowait(value)

    def get(self, timeout: float = 0.1) -> T:
        return self.queue.get(timeout=timeout)


ACTIVE = {
    SessionState.STARTING,
    SessionState.WATCHING,
    SessionState.RECOGNIZING,
    SessionState.TRANSLATING,
}


class Session:
    def __init__(self) -> None:
        self.lock = Lock()
        self.serial = 0
        self.generation = 0
        self.state = SessionState.IDLE

    def start(self) -> Stamp:
        with self.lock:
            if self.state not in {SessionState.IDLE, SessionState.SELECTING, SessionState.ERROR}:
                raise ValueError("Stop the current session before starting another")
            self.serial += 1
            self.generation = 0
            self.state = SessionState.STARTING
            return Stamp(self.serial, self.generation)

    def changed(self) -> Stamp:
        with self.lock:
            self.generation += 1
            return Stamp(self.serial, self.generation)

    def stamp(self) -> Stamp:
        with self.lock:
            return Stamp(self.serial, self.generation)

    def activity(self, state: SessionState, stamp: Stamp | None = None) -> Stamp | None:
        with self.lock:
            current = Stamp(self.serial, self.generation)
            if self.state not in ACTIVE or (stamp is not None and stamp != current):
                return None
            self.state = state
            return current

    def current(self, stamp: Stamp) -> bool:
        with self.lock:
            return self.state in ACTIVE and stamp == Stamp(self.serial, self.generation)

    def transition(self, target: SessionState) -> None:
        with self.lock:
            allowed = {
                SessionState.IDLE: {SessionState.SELECTING, SessionState.STARTING},
                SessionState.SELECTING: {
                    SessionState.IDLE,
                    SessionState.STARTING,
                    SessionState.STOPPING,
                },
                SessionState.PAUSED: {SessionState.WATCHING, SessionState.STOPPING},
                SessionState.ERROR: {SessionState.STOPPING, SessionState.STARTING},
                SessionState.STOPPING: {SessionState.IDLE},
            }
            valid = allowed.get(
                self.state,
                ACTIVE | {SessionState.PAUSED, SessionState.ERROR, SessionState.STOPPING},
            )
            if target != self.state and target not in valid:
                raise ValueError(f"Invalid session transition: {self.state} → {target}")
            self.state = target
            if target in {SessionState.PAUSED, SessionState.ERROR, SessionState.STOPPING}:
                self.generation += 1


@dataclass(frozen=True)
class CapturedWork:
    stamp: Stamp
    image: Image.Image
    captured: float
    timings: dict[str, float]


@dataclass(frozen=True)
class TextWork:
    stamp: Stamp
    text: str
    captured: float
    queued: float
    timings: dict[str, float]


class Pipeline:
    def __init__(
        self,
        settings: Settings,
        capture_factory: Callable[[], CaptureProvider],
        ocr_factory: Callable[[], OCREngine],
        provider_factory: Callable[[], TranslationProvider],
        once: bool = False,
    ) -> None:
        self.settings = settings
        self.capture_factory = capture_factory
        self.ocr_factory = ocr_factory
        self.provider_factory = provider_factory
        self.once = once
        self.session = Session()
        self.cancel = Event()
        self.paused = Event()
        self.frames: LatestMailbox[CapturedWork] = LatestMailbox()
        self.texts: LatestMailbox[TextWork] = LatestMailbox()
        self.events: Queue[PipelineEvent] = Queue(maxsize=32)
        self.event_lock = Lock()
        self.reset_text = Event()
        self.reset_frames = Event()
        self.confirm_frame = Event()
        self.context = TranslationContext(settings.context_entries, settings.context_chars)
        self.context_lock = Lock()
        self.cache = TranslationCache()
        self.ocr: OCREngine | None = None
        self.threads: list[Thread] = []
        self.counters = {"captures": 0, "ocr": 0, "translations": 0, "stale": 0, "cache_hits": 0}

    def start(self) -> None:
        if self.settings.region is None:
            raise ValueError("A region is required")
        self.session.start()
        self.emit(SessionState.STARTING)
        for name, target in [
            ("capture", self._capture),
            ("ocr", self._recognize),
            ("translation", self._translate),
        ]:
            thread = Thread(target=target, name=f"desktranslate-{name}", daemon=True)
            self.threads.append(thread)
            thread.start()

    def enqueue(self, event: PipelineEvent) -> None:
        with self.event_lock:
            if self.events.full():
                with contextlib.suppress(Empty):
                    self.events.get_nowait()
            self.events.put_nowait(event)

    def emit(self, state: SessionState, stamp: Stamp | None = None, **kwargs: object) -> None:
        if state in ACTIVE:
            stamp = self.session.activity(state, stamp)
            if stamp is None:
                return
        else:
            stamp = self.session.stamp()
        self.enqueue(PipelineEvent(stamp, state, **kwargs))  # type: ignore[arg-type]

    def fail(self, error: Exception) -> None:
        if self.cancel.is_set():
            return
        safe = str(error) if isinstance(error, DeskTranslateError) else DeskTranslateError.message
        self.paused.set()
        self.session.transition(SessionState.ERROR)
        self.emit(SessionState.ERROR, error=safe, category=type(error).__name__)
        logging.getLogger("desktranslate").error(
            "",
            extra={
                "component": "pipeline",
                "category": type(error).__name__,
                "session": self.session.serial,
            },
        )

    def pause(self) -> None:
        if self.session.state in ACTIVE:
            self.paused.set()
            self.session.transition(SessionState.PAUSED)
            self.emit(SessionState.PAUSED)

    def resume(self) -> None:
        if self.session.state == SessionState.PAUSED:
            self.session.transition(SessionState.WATCHING)
            self.reset_text.set()
            self.reset_frames.set()
            self.paused.clear()
            self.emit(SessionState.WATCHING)

    def clear_context(self) -> None:
        with self.context_lock:
            self.context.clear()
            self.session.changed()
            self.reset_text.set()
            self.reset_frames.set()

    def stop(self) -> None:
        self.cancel.set()
        self.session.transition(SessionState.STOPPING)
        if self.ocr:
            self.ocr.close()
        self.session.transition(SessionState.IDLE)
        # Workers are daemon threads with bounded HTTP timeouts; Qt never joins them.

    def poll(self) -> list[PipelineEvent]:
        events = []
        while True:
            try:
                event = self.events.get_nowait()
                with self.context_lock, self.session.lock:
                    if event.stamp == Stamp(self.session.serial, self.session.generation):
                        if event.result and self.session.state in ACTIVE:
                            self.context.accept(event.source, event.result.text)
                        events.append(event)
            except Empty:
                return events

    def _capture(self) -> None:
        capture = None
        try:
            capture = self.capture_factory()
            preset = PRESETS[self.settings.quality]
            gate = FrameGate(preset.frame_settle)
            last_paused = False
            while not self.cancel.is_set():
                if self.paused.is_set():
                    last_paused = True
                    self.cancel.wait(0.1)
                    continue
                if last_paused or self.reset_frames.is_set():
                    gate = FrameGate(preset.frame_settle)
                    last_paused = False
                    self.reset_frames.clear()
                start = time.perf_counter()
                region = self.settings.region
                if region is None:
                    return
                image = capture.capture(region)
                self.counters["captures"] += 1
                captured = time.monotonic()
                capture_ms = (time.perf_counter() - start) * 1000
                start = time.perf_counter()
                decision = gate.observe(image, captured)
                change_ms = (time.perf_counter() - start) * 1000
                if decision.changed:
                    self.session.changed()
                if decision.ready or self.once or (self.confirm_frame.is_set() and gate.emitted):
                    self.confirm_frame.clear()
                    self.frames.put(
                        CapturedWork(
                            self.session.stamp(),
                            image,
                            captured,
                            {"capture_ms": capture_ms, "change_ms": change_ms},
                        )
                    )
                    if self.once:
                        return
                cadence = (
                    preset.idle_cadence
                    if gate.emitted and captured - gate.since > 3
                    else preset.cadence
                )
                self.cancel.wait(cadence)
        except Exception as error:
            self.fail(error)
        finally:
            if capture:
                capture.close()

    def _recognize(self) -> None:
        try:
            stabilizer = TextStabilizer(PRESETS[self.settings.quality].text_settle)
            while not self.cancel.is_set():
                try:
                    work = self.frames.get()
                except Empty:
                    continue
                if not self.session.current(work.stamp):
                    continue
                if self.reset_text.is_set():
                    stabilizer = TextStabilizer(PRESETS[self.settings.quality].text_settle)
                    self.reset_text.clear()
                if self.ocr is None:
                    self.ocr = self.ocr_factory()
                    if self.cancel.is_set():
                        self.ocr.close()
                        return
                self.emit(SessionState.RECOGNIZING, work.stamp)
                start = time.perf_counter()
                image = preprocess(work.image, self.settings.preprocessing)
                timings = {**work.timings, "preprocess_ms": (time.perf_counter() - start) * 1000}
                self.counters["ocr"] += 1
                result = self.ocr.recognize(image, self.settings.source, self.settings.vertical)
                timings["ocr_ms"] = result.duration_ms
                text = (
                    result.text
                    if self.once
                    else stabilizer.observe(
                        result, time.monotonic(), settled_frame=self.settings.quality != "accuracy"
                    )
                )
                if not self.session.current(work.stamp):
                    self.counters["stale"] += 1
                    continue
                if text and len(text) <= 5000:
                    now = time.monotonic()
                    self.texts.put(TextWork(work.stamp, text, work.captured, now, timings))
                else:
                    if result.text and stabilizer.candidate != stabilizer.accepted:
                        # Confirmation must use a fresh captured frame, not run the
                        # deterministic recognizer twice on identical frozen pixels.
                        self.confirm_frame.set()
                    self.emit(
                        SessionState.WATCHING,
                        work.stamp,
                        error="No readable text yet. Try a tighter region or subtitle preprocessing."
                        if self.once
                        else "",
                        clear=not bool(result.text),
                    )
        except Cancelled:
            pass
        except Exception as error:
            self.fail(error)
        finally:
            if self.ocr:
                self.ocr.close()

    def _translate(self) -> None:
        provider = None
        try:
            provider = self.provider_factory()
            while not self.cancel.is_set():
                try:
                    work = self.texts.get()
                except Empty:
                    continue
                if not self.session.current(work.stamp):
                    continue
                self.emit(SessionState.TRANSLATING, work.stamp)
                with self.context_lock:
                    context = self.context.snapshot() if provider.capabilities.context else ()
                request = TranslationRequest(
                    work.text,
                    self.settings.source,
                    self.settings.target,
                    self.settings.model,
                    self.settings.style,
                    context,
                    tuple(sorted(self.settings.glossary.items())),
                    self.settings.instructions,
                )
                key = cache_key(self.settings.provider, self.settings.endpoint, request)
                result = self.cache.get(key)
                start = time.monotonic()
                if result:
                    self.counters["cache_hits"] += 1
                else:
                    self.counters["translations"] += 1
                    try:
                        try:
                            result = provider.translate(request)
                        except ProviderRateLimitError as error:
                            # One bounded retry; wait is cancellable and stale work is discarded.
                            if self.cancel.wait(error.retry_after) or not self.session.current(
                                work.stamp
                            ):
                                continue
                            result = provider.translate(request)
                    except DeskTranslateError:
                        if not self.session.current(work.stamp):
                            self.counters["stale"] += 1
                            continue
                        raise
                    self.cache.put(key, result)
                with self.context_lock:
                    if not self.session.current(work.stamp):
                        self.counters["stale"] += 1
                        continue
                    timings = {
                        **work.timings,
                        "queue_ms": (start - work.queued) * 1000,
                        "provider_ms": (time.monotonic() - start) * 1000,
                        "total_ms": (time.monotonic() - work.captured) * 1000,
                    }
                    # Use the work stamp, never the current stamp: capture can change during enqueue.
                    event = PipelineEvent(
                        work.stamp, SessionState.WATCHING, work.text, result, timings=timings
                    )
                    self.session.activity(SessionState.WATCHING, work.stamp)
                    self.enqueue(event)
        except Exception as error:
            self.fail(error)
        finally:
            if provider:
                provider.close()
