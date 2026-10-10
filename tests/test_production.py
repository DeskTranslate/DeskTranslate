import copy
import json
import random

import httpx
import pytest
from PIL import Image
from test_pipeline import OCR, Capture, SlowProvider, until

from desktranslate.errors import (
    ConfigurationError,
    OCRInferenceError,
    ProviderUnavailableError,
    TargetUnavailableError,
)
from desktranslate.models import Rect, SessionState
from desktranslate.pipeline import Pipeline, Session
from desktranslate.profiles import (
    apply_profile,
    export_profile,
    import_glossary,
    import_profile,
    profile_values,
)
from desktranslate.settings import Settings, SettingsStore
from desktranslate.updates import check_release, choose_release
from desktranslate.window_capture import (
    WindowCapture,
    WindowInfo,
    normalized_region,
    project_region,
)


def test_ocr_crash_recovery_has_a_restart_budget():
    instances = []

    class Crashing(OCR):
        def __init__(self):
            instances.append(self)

        def recognize(self, *args):
            raise OCRInferenceError()

    provider = SlowProvider()
    provider.release.set()
    pipeline = Pipeline(
        Settings(quality="fast", recent_region=[0, 0, 120, 80]), Capture, Crashing, lambda: provider
    )
    pipeline.start()
    try:
        until(lambda: pipeline.session.state == SessionState.ERROR)
        assert len(instances) == 3
        assert pipeline.counters["ocr_restarts"] == 2
        assert not pipeline.context.snapshot()
    finally:
        pipeline.stop()
        assert pipeline.wait_closed()


def test_ocr_recovers_without_restarting_the_session():
    count = 0

    def factory():
        nonlocal count
        count += 1
        if count == 1:

            class Crashing(OCR):
                def recognize(self, *args):
                    raise OCRInferenceError()

            return Crashing()
        return OCR()

    provider = SlowProvider()
    provider.release.set()
    pipeline = Pipeline(
        Settings(quality="fast", recent_region=[0, 0, 120, 80]), Capture, factory, lambda: provider
    )
    pipeline.start()
    try:
        results = []

        def translated():
            results.extend(e for e in pipeline.poll() if e.result)
            return bool(results)

        until(translated)
        assert results[-1].result.text == "A translated"
        assert pipeline.session.serial == 1
        assert pipeline.counters["ocr_restarts"] == 1
    finally:
        pipeline.stop()
        assert pipeline.wait_closed()


@pytest.mark.parametrize("seed", range(10))
def test_session_randomized_stale_invariants(seed):
    rng, session, past = random.Random(seed), Session(), []
    for _ in range(300):
        action = rng.choice(["start", "stop", "change", "pause", "resume", "fail"])
        if action == "start" and session.state in {SessionState.IDLE, SessionState.ERROR}:
            past.append(session.start())
        elif action == "stop":
            session.stop()
        elif action == "change":
            past.append(session.changed())
        elif action == "pause" and session.state in {SessionState.STARTING, SessionState.WATCHING}:
            session.transition(SessionState.PAUSED)
        elif action == "resume" and session.state == SessionState.PAUSED:
            session.transition(SessionState.WATCHING)
        elif action == "fail" and past:
            session.failure(rng.choice(past))
        current = session.stamp()
        assert not any(session.current(stamp) for stamp in past if stamp != current)
        if session.state == SessionState.IDLE:
            assert not session.current(current)


def test_profiles_are_bounded_and_never_import_credentials_or_capture_consent():
    settings = Settings(
        instructions="Preserve names", glossary={"Mika": "ミカ"}, recent_region=[10, 20, 50, 80]
    )
    payload = json.loads(export_profile("Anime", profile_values(settings)))
    assert "recent_region" not in payload["settings"]
    payload["settings"].update(api_key="DO_NOT_PERSIST", profiles={"nested": {}})
    name, values = import_profile(json.dumps(payload))
    assert name == "Anime" and "api_key" not in values and "profiles" not in values
    assert values["recent_region"] is None
    assert apply_profile(Settings(), values).glossary == settings.glossary
    payload["version"] = 999
    with pytest.raises(ValueError):
        import_profile(json.dumps(payload))
    with pytest.raises(ValueError):
        import_profile(" " * 80_001)


def test_profiles_reject_invalid_nested_values_and_unsafe_endpoints(tmp_path):
    with pytest.raises(ValueError):
        Settings(profiles={"Bad": {"glossary": {"x": {"secret": "x"}}}}).validate()
    with pytest.raises(ConfigurationError):
        Settings(profiles={"Bad": {"endpoint": "http://remote.example"}}).validate()
    store = SettingsStore(tmp_path)
    store.save(Settings(profiles={"Anime": profile_values(Settings())}))
    assert "Anime" in store.load().profiles
    assert import_glossary("source,translation\nMika,ミカ\n", True) == {"Mika": "ミカ"}


@pytest.mark.parametrize(
    "client", [Rect(-3840, -2160, 3840, 2160), Rect(0, 0, 1920, 1080), Rect(-1920, 0, 1440, 2560)]
)
def test_normalized_regions_follow_move_resize_and_negative_origins(client):
    crop = Rect(
        client.x + client.width // 4,
        client.y + client.height // 2,
        client.width // 2,
        client.height // 4,
    )
    relative = normalized_region(client, crop)
    assert project_region(client, relative) == crop
    moved = Rect(client.x + 537, client.y - 211, client.width * 2, client.height * 2)
    assert project_region(moved, relative) == Rect(
        moved.x + client.width // 2, moved.y + client.height, client.width, client.height // 2
    )


@pytest.mark.parametrize(
    "relative", [[0, 0, float("nan"), 1], [0, 0, 2, 1], [-1, 0, 1, 1], [0, 0, 0, 1], ["0", 0, 1, 1]]
)
def test_invalid_client_regions_fail_closed(relative):
    with pytest.raises(ValueError):
        project_region(Rect(0, 0, 1920, 1080), relative)


class Inspector:
    def __init__(self):
        self.items = [
            WindowInfo(
                100, 200, "game.exe", "a" * 64, "Game", Rect(0, 0, 800, 600), Rect(0, 0, 820, 640)
            )
        ]
        self.visible = True

    def windows(self):
        return self.items

    def unobscured(self, target, region):
        return self.visible and not target.minimized


class ScreenBackend:
    calls = 0

    def capture(self, region):
        self.calls += 1
        return Image.new("RGB", (region.width, region.height))

    def close(self):
        pass


def test_missing_covered_ambiguous_and_replaced_windows_never_read_pixels():
    inspector, backend = Inspector(), ScreenBackend()
    capture = WindowCapture(
        inspector.items[0].binding(), [0, 0.5, 1, 0.5], inspector=inspector, backend=backend
    )
    capture.capture(Rect(0, 0, 1, 1))
    assert backend.calls == 1
    inspector.visible = False
    with pytest.raises(TargetUnavailableError):
        capture.capture(Rect(0, 0, 1, 1))
    assert backend.calls == 1
    inspector.visible = True
    item = inspector.items[0]
    inspector.items = [
        WindowInfo(
            101, 201, item.executable, item.executable_hash, item.title, item.client, item.bounds
        )
    ]
    with pytest.raises(TargetUnavailableError):
        capture.capture(Rect(0, 0, 1, 1))
    assert backend.calls == 1
    capture.follow_restart = True
    capture.capture(Rect(0, 0, 1, 1))
    assert capture.rebound
    inspector.items *= 2
    capture.identity = None
    with pytest.raises(TargetUnavailableError):
        capture.capture(Rect(0, 0, 1, 1))
    assert backend.calls == 2


def release(version, prerelease=False):
    return {
        "tag_name": "v" + version,
        "html_url": "https://github.com/DeskTranslate/DeskTranslate/releases/tag/v" + version,
        "prerelease": prerelease,
        "assets": [{"name": f"DeskTranslate-{version}-Setup-x64.exe"}],
    }


def test_updates_use_semantic_order_and_reject_downgrades_and_bad_origins():
    releases = [
        release("2.0.0b10", True),
        release("2.0.0b2", True),
        release("2.0.0rc1", True),
        release("2.0.0"),
    ]
    assert choose_release(releases, "beta", "2.0.0b1")[0] == "v2.0.0"
    assert choose_release(releases[:3], "beta", "2.0.0b1")[0] == "v2.0.0rc1"
    assert choose_release(releases[:3], "stable", "2.0.0b1") is None
    assert choose_release(releases, "stable", "2.0.0") is None
    invalid = copy.deepcopy(releases[-1])
    invalid["html_url"] = (
        "https://github.com.evil.example/DeskTranslate/DeskTranslate/releases/tag/v2.0.0"
    )
    assert choose_release([invalid], "stable", "2.0.0b1") is None
    with pytest.raises(ProviderUnavailableError):
        check_release(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})))
