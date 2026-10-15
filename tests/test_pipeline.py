import time
from queue import Empty
from threading import Event

import pytest
from PIL import Image

from desktranslate.models import Capabilities, OCRResult, SessionState, TranslationResult
from desktranslate.pipeline import LatestMailbox, Pipeline, Session
from desktranslate.settings import Settings


def test_failed_sessions_release_worker_state_without_waiting_for_cyclic_gc():
    import gc
    import weakref

    import httpx

    from desktranslate.models import SessionState
    from desktranslate.providers import create_provider

    def failed_session():
        provider = create_provider(
            "custom", transport=httpx.MockTransport(lambda request: httpx.Response(500))
        )
        pipeline = Pipeline(
            Settings(recent_region=[0, 0, 120, 80]), Capture, OCR, lambda: provider, once=True
        )
        reference = weakref.ref(pipeline)
        pipeline.start()
        try:
            until(lambda: pipeline.session.state == SessionState.ERROR)
        finally:
            pipeline.stop()
            assert pipeline.wait_closed()
        return reference

    gc.collect()
    collecting = gc.isenabled()
    gc.disable()
    try:
        retired = [failed_session() for _ in range(8)]
        assert all(reference() is None for reference in retired), (
            "Failed provider tasks retained retired sessions and their native synchronization handles"
        )
    finally:
        if collecting:
            gc.enable()
        gc.collect()


def until(predicate, timeout=3):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("Timed out")


def test_mailbox_is_bounded_and_latest_wins():
    mailbox = LatestMailbox()
    for n in range(10000):
        mailbox.put(n)
    assert mailbox.get() == 9999
    with pytest.raises(Empty):
        mailbox.get(0.001)


def test_lifecycle_invalidates_pause_stop_and_new_session():
    session = Session()
    first = session.start()
    assert session.current(first)
    session.transition(SessionState.PAUSED)
    assert not session.current(first)
    session.transition(SessionState.WATCHING)
    second = session.stamp()
    assert session.current(second)
    session.transition(SessionState.STOPPING)
    session.transition(SessionState.IDLE)
    session.start()
    assert not session.current(second)
    with pytest.raises(ValueError):
        session.start()


class Capture:
    color = 0

    def capture(self, region):
        return Image.new("RGB", (120, 80), (self.color,) * 3)

    def close(self):
        pass


class OCR:
    def recognize(self, image, language, vertical=False):
        return OCRResult("A" if image.getpixel((0, 0))[0] == 0 else "C", confidence=0.99)

    def close(self):
        pass


class SlowProvider:
    capabilities = Capabilities(context=True)

    def __init__(self):
        self.started = Event()
        self.release = Event()
        self.calls = []

    def translate(self, request):
        self.calls.append(request.text)
        if request.text == "A":
            self.started.set()
            self.release.wait(3)
        return TranslationResult(request.text + " translated")

    def close(self):
        self.release.set()


def test_screen_changes_discard_stale_network_result_and_context():
    capture = Capture()
    provider = SlowProvider()
    settings = Settings(quality="fast", recent_region=[0, 0, 120, 80])
    pipeline = Pipeline(settings, lambda: capture, OCR, lambda: provider)
    pipeline.start()
    try:
        until(provider.started.is_set)
        first_stamp = pipeline.session.stamp()
        capture.color = 200
        until(lambda: pipeline.session.stamp() != first_stamp)
        provider.release.set()
        results = []

        def translated():
            results.extend(event for event in pipeline.poll() if event.result)
            return bool(results)

        until(translated)
        assert [event.result.text for event in results] == ["C translated"]
        assert all(pair.source != "A" for pair in pipeline.context.snapshot())
        assert pipeline.counters["stale"] >= 1
    finally:
        pipeline.stop()


def test_pixel_change_retries_identical_text_after_invalidated_translation():
    class SameTextOCR(OCR):
        def recognize(self, *args, **kwargs):
            return OCRResult("A", confidence=0.99)

    capture, provider = Capture(), SlowProvider()
    pipeline = Pipeline(
        Settings(quality="fast", recent_region=[0, 0, 120, 80]),
        lambda: capture,
        SameTextOCR,
        lambda: provider,
    )
    pipeline.start()
    try:
        until(provider.started.is_set)
        initial = pipeline.session.stamp()
        capture.color = 200
        until(lambda: pipeline.session.stamp() != initial)
        until(lambda: pipeline.counters["ocr"] >= 2)
        provider.release.set()
        results = []

        def delivered():
            results.extend(event for event in pipeline.poll() if event.result)
            return bool(results)

        until(delivered)
        assert results[-1].source == "A"
        assert results[-1].stamp != initial
        assert pipeline.session.current(results[-1].stamp)
        assert pipeline.counters["stale"] >= 1
    finally:
        pipeline.stop()
        assert pipeline.wait_closed()


def test_context_reset_during_stabilizer_reset_cannot_suppress_redisplay():
    class SameTextOCR(OCR):
        def recognize(self, *args, **kwargs):
            return OCRResult("A", confidence=0.99)

    class BlockedReset(Event):
        def __init__(self):
            super().__init__()
            self.entered, self.release = Event(), Event()
            self.blocked = False

        def clear(self):
            if not self.blocked:
                self.blocked = True
                self.entered.set()
                self.release.wait(5)
            super().clear()

    capture, provider = Capture(), SlowProvider()
    provider.release.set()
    pipeline = Pipeline(
        Settings(quality="fast", recent_region=[0, 0, 120, 80]),
        lambda: capture,
        SameTextOCR,
        lambda: provider,
    )
    flag = BlockedReset()
    pipeline.reset_text = flag
    pipeline.delivered_source = "A"
    pipeline.start()
    try:
        until(flag.entered.is_set)
        captures = pipeline.counters["captures"]
        pipeline.clear_context()
        until(lambda: pipeline.counters["captures"] >= captures + 4)
        until(lambda: not pipeline.frames.queue.empty())
        flag.release.set()
        events = []

        def redisplayed():
            events.extend(event for event in pipeline.poll() if event.result)
            return bool(events)

        until(redisplayed)
        assert events[-1].source == "A"
        assert pipeline.session.current(events[-1].stamp)
    finally:
        flag.release.set()
        pipeline.stop()
        assert pipeline.wait_closed()


def test_static_region_avoids_repeated_ocr():
    capture = Capture()
    provider = SlowProvider()
    provider.release.set()
    pipeline = Pipeline(
        Settings(quality="fast", recent_region=[0, 0, 120, 80]),
        lambda: capture,
        OCR,
        lambda: provider,
    )
    pipeline.start()
    try:
        until(lambda: pipeline.counters["translations"] == 1)
        time.sleep(0.6)
        assert pipeline.counters["captures"] >= 3
        assert pipeline.counters["ocr"] == 1
        assert pipeline.counters["translations"] == 1
    finally:
        pipeline.stop()


def test_stop_does_not_wait_for_network_request():
    provider = SlowProvider()
    pipeline = Pipeline(
        Settings(quality="fast", recent_region=[0, 0, 120, 80]), Capture, OCR, lambda: provider
    )
    pipeline.start()
    until(provider.started.is_set)
    start = time.monotonic()
    pipeline.stop()
    assert time.monotonic() - start < 0.1
    provider.release.set()
    assert pipeline.poll() == []


def test_resume_retries_unchanged_text_invalidated_during_request():
    provider = SlowProvider()
    pipeline = Pipeline(
        Settings(quality="fast", recent_region=[0, 0, 120, 80]), Capture, OCR, lambda: provider
    )
    pipeline.start()
    try:
        until(provider.started.is_set)
        assert pipeline.session.state == SessionState.TRANSLATING
        pipeline.pause()
        provider.release.set()
        pipeline.resume()
        events = []

        def accepted():
            events.extend(e for e in pipeline.poll() if e.result)
            return bool(events)

        until(accepted)
        assert events[-1].result.text == "A translated"
        assert pipeline.session.state == SessionState.WATCHING
    finally:
        pipeline.stop()


def test_failure_of_stale_request_does_not_break_new_generation():
    from desktranslate.errors import ProviderTimeoutError

    class FailingOldProvider(SlowProvider):
        def translate(self, request):
            if request.text == "A":
                self.started.set()
                self.release.wait(3)
                raise ProviderTimeoutError()
            return TranslationResult("C translated")

    capture = Capture()
    provider = FailingOldProvider()
    pipeline = Pipeline(
        Settings(quality="fast", recent_region=[0, 0, 120, 80]),
        lambda: capture,
        OCR,
        lambda: provider,
    )
    pipeline.start()
    try:
        until(provider.started.is_set)
        old = pipeline.session.stamp()
        capture.color = 200
        until(lambda: pipeline.session.stamp() != old)
        provider.release.set()
        events = []

        def accepted():
            events.extend(pipeline.poll())
            return any(event.result for event in events)

        until(accepted)
        assert not any(event.state == SessionState.ERROR for event in events)
        assert events[-1].result.text == "C translated"
    finally:
        pipeline.stop()


def test_stop_is_responsive_while_native_ocr_reaper_holds_join_lock():
    from threading import Lock

    from desktranslate.ocr import IsolatedOCR

    engine = IsolatedOCR.__new__(IsolatedOCR)
    engine.lock = Lock()
    engine.closed = Event()
    engine.closed.set()  # Reaper has terminated IPC and is joining the child.
    engine.cancelled = Event()
    pipeline = Pipeline(Settings(), Capture, OCR, SlowProvider)
    pipeline.ocr = engine
    with engine.lock:
        started = time.monotonic()
        pipeline.stop()
        assert time.monotonic() - started < 0.1


@pytest.mark.parametrize("blank", [False, True])
def test_one_shot_releases_workers_without_invalidating_pending_result(blank):
    class OnceOCR(OCR):
        def recognize(self, *args):
            return OCRResult("" if blank else "Authored text", confidence=0.99)

    provider = SlowProvider()
    provider.release.set()
    pipeline = Pipeline(
        Settings(recent_region=[0, 0, 120, 80]), Capture, OnceOCR, lambda: provider, once=True
    )
    pipeline.start()
    try:
        assert pipeline.wait_closed(3)
        events = pipeline.poll()
        assert (
            any(event.clear for event in events) if blank else any(event.result for event in events)
        )
        assert all(pipeline.session.current(event.stamp) for event in events)
    finally:
        pipeline.stop()


def test_pause_cancels_pending_provider_and_resume_uses_fresh_client():
    from desktranslate.errors import Cancelled

    providers = []

    class Cancellable(SlowProvider):
        def __init__(self):
            super().__init__()
            self.cancelled = Event()
            providers.append(self)

        def translate(self, request):
            self.started.set()
            if len(providers) == 1:
                self.cancelled.wait(2)
                if self.cancelled.is_set():
                    raise Cancelled()
            return TranslationResult("Authored translated result")

        def cancel_pending(self):
            self.cancelled.set()

    pipeline = Pipeline(
        Settings(quality="fast", recent_region=[0, 0, 120, 80]), Capture, OCR, Cancellable
    )
    pipeline.start()
    try:
        until(lambda: providers and providers[0].started.is_set())
        pipeline.pause()
        assert providers[0].cancelled.is_set()
        pipeline.resume()
        accepted = []

        def received():
            accepted.extend(event for event in pipeline.poll() if event.result)
            return bool(accepted)

        until(received)
        assert len(providers) == 2
        assert len(accepted) == 1
    finally:
        pipeline.stop()
        assert pipeline.wait_closed()


def test_continuous_motion_translates_and_new_confirmed_text_rejects_old_request():
    class Moving(Capture):
        tick = 0
        text = 0

        def capture(self, region):
            self.tick += 1
            image = Image.new("RGB", (120, 80), ((self.tick * 31) % 256,) * 3)
            image.putpixel((0, 0), (self.text,) * 3)
            return image

    capture, provider = Moving(), SlowProvider()
    pipeline = Pipeline(
        Settings(quality="fast", recent_region=[0, 0, 120, 80]),
        lambda: capture,
        OCR,
        lambda: provider,
    )
    pipeline.start()
    try:
        until(provider.started.is_set, 5)
        original = pipeline.session.stamp()
        capture.text = 200
        until(lambda: pipeline.session.stamp() != original, 4)
        provider.release.set()
        accepted = []

        def received():
            accepted.extend(event for event in pipeline.poll() if event.result)
            return bool(accepted)

        until(received, 4)
        assert [event.source for event in accepted] == ["C"]
        assert pipeline.counters["ocr"] > 0
        assert pipeline.frames.queue.qsize() <= 1
        assert pipeline.counters["stale"] >= 1
    finally:
        pipeline.stop()
        assert pipeline.wait_closed()


@pytest.mark.parametrize("component", ["ocr", "provider"])
def test_cleanup_failure_is_reported_and_does_not_exhaust_worker_capacity(component):
    class BadOCR(OCR):
        def close(self):
            raise RuntimeError("authored cleanup failure")

    class BadProvider(SlowProvider):
        def close(self):
            raise RuntimeError("authored cleanup failure")

    for _ in range(3):
        provider = BadProvider() if component == "provider" else SlowProvider()
        provider.release.set()
        pipeline = Pipeline(
            Settings(recent_region=[0, 0, 120, 80]),
            Capture,
            BadOCR if component == "ocr" else OCR,
            lambda provider=provider: provider,
            once=True,
        )
        pipeline.start()
        until(lambda pipeline=pipeline: not any(thread.is_alive() for thread in pipeline.threads))
        assert not pipeline.wait_closed()
        assert pipeline.cleanup_failed.is_set()
    provider = SlowProvider()
    provider.release.set()
    healthy = Pipeline(
        Settings(recent_region=[0, 0, 120, 80]), Capture, OCR, lambda: provider, once=True
    )
    healthy.start()
    assert healthy.wait_closed(3)
    assert any(event.result for event in healthy.poll())


def test_overlong_recognition_stops_with_actionable_error_and_sends_no_text():
    class LongOCR(OCR):
        def recognize(self, *args, **kwargs):
            return OCRResult("Authored " + "x" * 5001, confidence=0.99)

    provider = SlowProvider()
    provider.release.set()
    pipeline = Pipeline(
        Settings(recent_region=[0, 0, 120, 80]), Capture, LongOCR, lambda: provider, once=True
    )
    pipeline.start()
    assert pipeline.wait_closed(3)
    assert provider.calls == []
    errors = [event for event in pipeline.poll() if event.category]
    assert len(errors) == 1 and "smaller region" in errors[0].error
    assert pipeline.session.state == SessionState.ERROR
