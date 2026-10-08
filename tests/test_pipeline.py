import time
from queue import Empty
from threading import Event

import pytest
from PIL import Image

from desktranslate.models import Capabilities, OCRResult, SessionState, TranslationResult
from desktranslate.pipeline import LatestMailbox, Pipeline, Session
from desktranslate.settings import Settings


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
