from __future__ import annotations

import contextlib
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from queue import Empty, Queue
from threading import BoundedSemaphore, Event, Lock, Thread
from typing import TypeVar

from PIL import Image

from desktranslate.algorithms import PRESETS, FrameGate, preprocess
from desktranslate.context import ContextEngine, TranslationCache, TranslationContext, cache_key
from desktranslate.errors import (
    Cancelled,
    ConfigurationError,
    DeskTranslateError,
    OCRInferenceError,
    ProviderRateLimitError,
    TargetUnavailableError,
)
from desktranslate.models import (
    CaptureProvider,
    OCREngine,
    PipelineEvent,
    Rect,
    SessionState,
    Stamp,
    TranslationProvider,
    TranslationResult,
)
from desktranslate.settings import Settings
from desktranslate.temporal import TemporalTextTracker

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
    SessionState.WAITING_TARGET,
    SessionState.RECOGNIZING,
    SessionState.TRANSLATING,
}

# Budgets span replaced sessions. Waiting workers create no native/HTTP resources.
OCR_SLOTS = BoundedSemaphore(2)
PROVIDER_SLOTS = BoundedSemaphore(2)


def acquire_slot(slot: BoundedSemaphore, cancel: Event) -> bool:
    while not cancel.is_set():
        if slot.acquire(timeout=0.05):
            if cancel.is_set():
                slot.release()
                return False
            return True
    return False


class Session:
    def __init__(self) -> None:
        self.lock = Lock()
        self.serial = 0
        self.generation = 0
        self.control_generation = 0
        self.state = SessionState.IDLE

    def start(self) -> Stamp:
        with self.lock:
            if self.state not in {SessionState.IDLE, SessionState.SELECTING, SessionState.ERROR}:
                raise ValueError("Stop the current session before starting another")
            self.serial += 1
            self.generation = 0
            self.control_generation = 0
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

    def recognition_current(self, stamp: Stamp, control_generation: int) -> bool:
        """Visual revisions can supply evidence, but lifecycle changes cannot."""
        with self.lock:
            return (
                self.state in ACTIVE
                and stamp.session == self.serial
                and control_generation == self.control_generation
            )

    def failure(self, stamp: Stamp | None = None) -> Stamp | None:
        with self.lock:
            current = Stamp(self.serial, self.generation)
            if self.state not in ACTIVE or (stamp is not None and stamp != current):
                return None
            self.state = SessionState.ERROR
            self.generation += 1
            self.control_generation += 1
            return Stamp(self.serial, self.generation)

    def pause(self) -> bool:
        with self.lock:
            if self.state not in ACTIVE:
                return False
            self.state = SessionState.PAUSED
            self.generation += 1
            self.control_generation += 1
            return True

    def resume(self) -> bool:
        with self.lock:
            if self.state != SessionState.PAUSED:
                return False
            self.state = SessionState.WATCHING
            return True

    def stop(self) -> None:
        with self.lock:
            self.generation += 1
            self.control_generation += 1
            self.state = SessionState.IDLE

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
                self.control_generation += 1


@dataclass(frozen=True)
class CapturedWork:
    stamp: Stamp
    image: Image.Image
    captured: float
    timings: dict[str, float]
    region: Rect | None = None
    moving: bool = False
    control_generation: int = 0


@dataclass(frozen=True)
class TextWork:
    stamp: Stamp
    text: str
    captured: float
    queued: float
    timings: dict[str, float]
    region: Rect | None = None
    replaces_source: str = ""


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
        self.cleanup_failed = Event()
        self.paused = Event()
        self.frames: LatestMailbox[CapturedWork] = LatestMailbox()
        self.texts: LatestMailbox[TextWork] = LatestMailbox()
        self.events: Queue[PipelineEvent] = Queue(maxsize=32)
        self.event_lock = Lock()
        self.reset_text = Event()
        self.reset_frames = Event()
        self.confirm_frame = Event()
        self.context = TranslationContext(settings.context_entries, settings.context_chars)
        glossary = (
            settings.glossary
            if (
                settings.glossary_source == settings.source
                and settings.glossary_target == settings.target
            )
            else {}
        )
        self.context_engine = ContextEngine(self.context, glossary, settings.story_context)
        self.context_lock = Lock()
        self.cache = TranslationCache()
        self.ocr: OCREngine | None = None
        self.provider: TranslationProvider | None = None
        self.capture_region = settings.region
        # OCR acceptance is provisional until the current result reaches the UI.
        self.delivered_source = ""
        self.motion_source = ""
        self.threads: list[Thread] = []
        self.counters = {
            "captures": 0,
            "ocr": 0,
            "translations": 0,
            "stale": 0,
            "cache_hits": 0,
            "ocr_restarts": 0,
            "glossary_hits": 0,
            "temporal_suppressed": 0,
        }

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

    def fail(self, error: Exception, stamp: Stamp | None = None) -> None:
        if self.cancel.is_set():
            return
        failed = self.session.failure(stamp)
        if failed is None:
            return
        safe = str(error) if isinstance(error, DeskTranslateError) else DeskTranslateError.message
        self.paused.set()
        self.cancel.set()
        if self.ocr and hasattr(self.ocr, "cancel_pending"):
            self.ocr.cancel_pending()  # type: ignore[attr-defined]
        if self.provider and hasattr(self.provider, "cancel_pending"):
            self.provider.cancel_pending()  # type: ignore[attr-defined]
        self.enqueue(
            PipelineEvent(failed, SessionState.ERROR, error=safe, category=type(error).__name__)
        )
        logging.getLogger("desktranslate").error(
            "",
            extra={
                "component": "pipeline",
                "category": type(error).__name__,
                "session": self.session.serial,
            },
        )

    def pause(self) -> None:
        if self.session.pause():
            self.paused.set()
            if self.ocr and hasattr(self.ocr, "cancel_pending"):
                self.ocr.cancel_pending()  # type: ignore[attr-defined]
            if self.provider and hasattr(self.provider, "cancel_pending"):
                self.provider.cancel_pending()  # type: ignore[attr-defined]
            self.emit(SessionState.PAUSED)

    def resume(self) -> None:
        if self.session.resume():
            self.reset_text.set()
            self.reset_frames.set()
            self.paused.clear()
            self.emit(SessionState.WATCHING)

    def clear_context(self) -> None:
        with self.context_lock, self.session.lock:
            self.context.clear()
            # Invalidate work and its presentation receipt in one transition.
            self.session.generation += 1
            self.session.control_generation += 1
            self.delivered_source = ""
            self.reset_text.set()
            self.reset_frames.set()

    def stop(self) -> None:
        self.cancel.set()
        self.session.stop()
        if self.ocr:
            if hasattr(self.ocr, "cancel_pending"):
                self.ocr.cancel_pending()  # type: ignore[attr-defined]
            else:
                self.ocr.close()
        if self.provider and hasattr(self.provider, "cancel_pending"):
            self.provider.cancel_pending()  # type: ignore[attr-defined]
        # Native process reaping and bounded client cleanup occur in existing workers.

    def wait_closed(self, timeout: float = 5.0) -> bool:
        """Release probes/shutdown coordinator only; never called on the GUI thread."""
        deadline = time.monotonic() + timeout
        for thread in self.threads:
            thread.join(max(0.0, deadline - time.monotonic()))
        return (
            not any(thread.is_alive() for thread in self.threads)
            and not self.cleanup_failed.is_set()
        )

    def cleanup_failure(self) -> None:
        self.cleanup_failed.set()
        logging.getLogger("desktranslate").error(
            "", extra={"component": "pipeline", "category": "ResourceCleanupError"}
        )

    def poll(self) -> list[PipelineEvent]:
        events = []
        while True:
            try:
                event = self.events.get_nowait()
                with self.context_lock, self.session.lock:
                    if event.stamp == Stamp(self.session.serial, self.session.generation):
                        if event.result and self.session.state in ACTIVE:
                            self.context.accept(
                                event.source, event.result.text, event.replaces_source
                            )
                        events.append(event)
            except Empty:
                return events

    def _capture(self) -> None:
        capture = None
        try:
            capture = self.capture_factory()
            preset = PRESETS[self.settings.quality]
            gate = FrameGate(preset.frame_settle, motion_interval=preset.motion_interval)
            last_paused = False
            unavailable = False
            while not self.cancel.is_set():
                if self.paused.is_set():
                    last_paused = True
                    self.cancel.wait(0.1)
                    continue
                if last_paused or self.reset_frames.is_set():
                    gate = FrameGate(preset.frame_settle, motion_interval=preset.motion_interval)
                    last_paused = False
                    self.reset_frames.clear()
                start = time.perf_counter()
                region = self.settings.region
                if region is None:
                    return
                with self.session.lock:
                    capture_control = self.session.control_generation
                try:
                    image = capture.capture(region)
                except TargetUnavailableError as error:
                    blocked_region = getattr(capture, "region", None)
                    if not unavailable:
                        self.clear_context()
                        unavailable = True
                        self.capture_region = blocked_region or self.capture_region
                        self.emit(
                            SessionState.WAITING_TARGET,
                            error=str(error),
                            clear=True,
                            region=getattr(capture, "region", None),
                        )
                    elif blocked_region is not None and blocked_region != self.capture_region:
                        self.capture_region = blocked_region
                        self.emit(
                            SessionState.WAITING_TARGET, error=str(error), region=blocked_region
                        )
                    self.cancel.wait(0.5)
                    continue
                actual = getattr(capture, "region", region) or region
                with self.session.lock:
                    if capture_control != self.session.control_generation:
                        continue  # A pause/reset during capture revokes those pixels.
                rebound = getattr(capture, "rebound", False)
                if unavailable or actual != self.capture_region or rebound:
                    self.clear_context()
                    with self.session.lock:
                        capture_control = self.session.control_generation
                    gate = FrameGate(preset.frame_settle, motion_interval=preset.motion_interval)
                    unavailable = False
                    self.capture_region = actual
                    if rebound:
                        capture.rebound = False  # type: ignore[attr-defined]
                    self.emit(
                        SessionState.WATCHING,
                        region=actual,
                        error="Following the chosen window. Dialogue context reset."
                        if rebound
                        else "",
                    )
                self.counters["captures"] += 1
                captured = time.monotonic()
                capture_ms = (time.perf_counter() - start) * 1000
                start = time.perf_counter()
                was_moving = gate.moving
                decision = gate.observe(image, captured)
                change_ms = (time.perf_counter() - start) * 1000
                if (decision.changed and not decision.moving) or (
                    was_moving and not decision.moving and decision.ready
                ):
                    self.session.changed()
                    self.reset_text.set()
                    if self.provider and getattr(self.provider, "pending", None) is not None:
                        self.provider.cancel_pending()  # type: ignore[attr-defined]
                if decision.ready or self.once or (self.confirm_frame.is_set() and gate.emitted):
                    self.confirm_frame.clear()
                    self.frames.put(
                        CapturedWork(
                            self.session.stamp(),
                            image,
                            captured,
                            {"capture_ms": capture_ms, "change_ms": change_ms},
                            actual,
                            decision.moving,
                            capture_control,
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
                try:
                    capture.close()
                except Exception:
                    self.cleanup_failure()

    def _recognize(self) -> None:
        acquired = acquire_slot(OCR_SLOTS, self.cancel)
        if not acquired:
            return
        try:
            stabilizer = TemporalTextTracker(PRESETS[self.settings.quality].text_settle)
            stabilizer_stamp: Stamp | None = None
            control_stamp: tuple[int, int] | None = None
            recoveries: list[float] = []
            while not self.cancel.is_set():
                try:
                    work = self.frames.get()
                except Empty:
                    continue
                if not self.session.current(work.stamp):
                    continue
                if work.stamp != stabilizer_stamp or self.reset_text.is_set():
                    with self.session.lock:
                        if work.stamp != Stamp(self.session.serial, self.session.generation):
                            continue
                        current_control = (self.session.serial, self.session.control_generation)
                        if current_control != control_stamp:
                            stabilizer = TemporalTextTracker(
                                PRESETS[self.settings.quality].text_settle
                            )
                            control_stamp = current_control
                        stabilizer.rebase_delivery(self.delivered_source)
                        stabilizer_stamp = work.stamp
                    # A concurrent reset cannot be lost: its newer stamp also
                    # requires fresh stabilization when that work is consumed.
                    self.reset_text.clear()
                if self.ocr is None:
                    self.ocr = self.ocr_factory()
                    if self.cancel.is_set():
                        self.ocr.close()
                        return
                self.emit(SessionState.RECOGNIZING, work.stamp, region=work.region)
                start = time.perf_counter()
                image = preprocess(work.image, self.settings.preprocessing)
                timings = {**work.timings, "preprocess_ms": (time.perf_counter() - start) * 1000}
                self.counters["ocr"] += 1
                inference_start = time.perf_counter()
                try:
                    result = self.ocr.recognize(image, self.settings.source, self.settings.vertical)
                except Cancelled:
                    self.ocr.close()
                    if hasattr(self.ocr, "reap"):
                        self.ocr.reap()  # type: ignore[attr-defined]
                    self.ocr = None
                    # Pause can cancel an idle native worker. Its cancellation
                    # is first observed on the next frame after resume; retry a
                    # fresh capture rather than leaving a static region emitted
                    # forever with no replacement recognition work.
                    self.reset_text.set()
                    self.reset_frames.set()
                    continue
                except OCRInferenceError as error:
                    self.ocr.close()
                    if hasattr(self.ocr, "reap"):
                        self.ocr.reap()  # type: ignore[attr-defined]
                    self.ocr = None
                    now = time.monotonic()
                    recoveries = [t for t in recoveries if now - t < 60]
                    if len(recoveries) >= 2:
                        self.fail(error, work.stamp)
                        continue
                    recoveries.append(now)
                    self.counters["ocr_restarts"] += 1
                    self.reset_text.set()
                    self.reset_frames.set()
                    if self.once and self.session.current(work.stamp):
                        self.frames.put(work)
                    self.emit(
                        SessionState.WATCHING,
                        work.stamp,
                        error="Recognition restarted after a worker failure. Retrying locally.",
                    )
                    continue
                timings.update(result.timings)
                timings["ocr_ms"] = result.duration_ms
                timings["ocr_call_ms"] = (time.perf_counter() - inference_start) * 1000
                if not self.session.recognition_current(work.stamp, work.control_generation):
                    self.counters["stale"] += 1
                    continue
                text = (
                    result.text
                    if self.once
                    else stabilizer.observe(
                        result,
                        work.captured,
                        settled_frame=not work.moving and self.settings.quality != "accuracy",
                    )
                )
                if not self.session.current(work.stamp):
                    self.counters["stale"] += 1
                    continue
                emitted_stamp = work.stamp
                confirmed_source = text if text else ("" if not result.text.strip() else None)
                semantic_change = False
                with self.session.lock:
                    if work.stamp != Stamp(self.session.serial, self.session.generation):
                        self.counters["stale"] += 1
                        continue
                    if confirmed_source is not None:
                        if work.moving and confirmed_source != self.motion_source:
                            self.session.generation += 1
                            emitted_stamp = Stamp(self.session.serial, self.session.generation)
                            stabilizer_stamp = emitted_stamp
                            semantic_change = True
                        self.motion_source = confirmed_source
                    if not result.text.strip():
                        self.delivered_source = ""
                if (
                    semantic_change
                    and self.provider
                    and getattr(self.provider, "pending", None) is not None
                ):
                    self.provider.cancel_pending()  # type: ignore[attr-defined]
                if text and len(text) > 5000:
                    self.fail(
                        ConfigurationError(
                            "Recognized text exceeds 5,000 characters. Select a smaller region before translating."
                        ),
                        emitted_stamp,
                    )
                    continue
                if text:
                    now = time.monotonic()
                    self.texts.put(
                        TextWork(
                            emitted_stamp,
                            text,
                            work.captured,
                            now,
                            timings,
                            work.region,
                            "" if self.once else stabilizer.replaces_source,
                        )
                    )
                else:
                    if result.text and stabilizer.needs_confirmation:
                        self.counters["temporal_suppressed"] += 1
                        # Confirmation must use a fresh captured frame, not run the
                        # deterministic recognizer twice on identical frozen pixels.
                        self.confirm_frame.set()
                    self.emit(
                        SessionState.WATCHING,
                        emitted_stamp,
                        error="No readable text yet. Try a tighter region or subtitle preprocessing."
                        if self.once
                        else "",
                        clear=not bool(result.text),
                    )
                    if self.once:
                        self.cancel.set()
        except Cancelled:
            pass
        except Exception as error:
            self.fail(error)
        finally:
            try:
                if self.ocr:
                    self.ocr.close()
                    if hasattr(self.ocr, "reap"):
                        self.ocr.reap()  # type: ignore[attr-defined]
            except Exception:
                self.cleanup_failure()
            finally:
                OCR_SLOTS.release()

    def _translate(self) -> None:
        provider = None
        acquired = acquire_slot(PROVIDER_SLOTS, self.cancel)
        if not acquired:
            return
        try:
            provider = self.provider_factory()
            self.provider = provider
            while not self.cancel.is_set():
                try:
                    work = self.texts.get()
                except Empty:
                    continue
                if not self.session.current(work.stamp):
                    continue
                cancelled = getattr(provider, "cancelled", None)
                if cancelled is not None and cancelled.is_set():
                    provider.close()
                    provider = self.provider_factory()
                    self.provider = provider
                self.emit(SessionState.TRANSLATING, work.stamp, region=work.region)
                lookup_start = time.perf_counter()
                with self.context_lock:
                    request = self.context_engine.request(
                        work.text,
                        self.settings.source,
                        self.settings.target,
                        contextual=provider.capabilities.context,
                        model=self.settings.model,
                        style=self.settings.style,
                        instructions=self.settings.instructions,
                        replaces_source=work.replaces_source,
                    )
                work.timings["context_ms"] = (time.perf_counter() - lookup_start) * 1000
                key = cache_key(self.settings.provider, self.settings.endpoint, request)
                result = self.cache.get(key)
                start = time.monotonic()
                exact_term = self.context_engine.terminology.exact(work.text)
                if result is None and exact_term is not None:
                    result = TranslationResult(exact_term)
                    self.counters["glossary_hits"] += 1
                if result:
                    if result.cached:
                        self.counters["cache_hits"] += 1
                    else:
                        self.cache.put(key, result)
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
                    except Exception as error:
                        if not self.session.current(work.stamp):
                            self.counters["stale"] += 1
                            continue
                        self.fail(error, work.stamp)
                        continue
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
                        work.stamp,
                        SessionState.WATCHING,
                        work.text,
                        result,
                        timings=timings,
                        region=work.region,
                        replaces_source=work.replaces_source,
                    )
                    self.session.activity(SessionState.WATCHING, work.stamp)
                    self.enqueue(event)
                    if self.once:
                        self.cancel.set()  # Preserve the result stamp while retiring workers.
        except Exception as error:
            self.fail(error)
        finally:
            try:
                if provider:
                    provider.close()
            except Exception:
                self.cleanup_failure()
            finally:
                self.provider = None
                PROVIDER_SLOTS.release()
