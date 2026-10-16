import json
import logging
from dataclasses import replace
from itertools import pairwise

import pytest
from PIL import Image, ImageDraw

from desktranslate.algorithms import FrameGate, normalize_text, reconstruct
from desktranslate.context import TranslationCache, TranslationContext, cache_key
from desktranslate.errors import ConfigurationError
from desktranslate.hotkeys import Hotkeys, parse_hotkey, validate_hotkeys
from desktranslate.languages import REGISTRY
from desktranslate.logging import PrivateFormatter
from desktranslate.models import (
    ContextPair,
    Monitor,
    OCRLine,
    OCRResult,
    Rect,
    TranslationRequest,
    TranslationResult,
)
from desktranslate.security import validate_endpoint
from desktranslate.settings import Settings, SettingsStore
from desktranslate.temporal import TemporalTextTracker


@pytest.mark.parametrize(
    "logical,physical,region,expected",
    [
        (
            Rect(0, 0, 1920, 1080),
            Rect(0, 0, 1920, 1080),
            Rect(10, 20, 500, 100),
            Rect(10, 20, 500, 100),
        ),
        (
            Rect(1920, 0, 1280, 720),
            Rect(1920, 0, 1920, 1080),
            Rect(2000, 40, 200, 100),
            Rect(2040, 60, 300, 150),
        ),
        (
            Rect(-1280, -720, 1280, 720),
            Rect(-1920, -1080, 1920, 1080),
            Rect(-1200, -680, 200, 100),
            Rect(-1800, -1020, 300, 150),
        ),
    ],
)
def test_per_monitor_coordinates(logical, physical, region, expected):
    assert Monitor("test", logical, physical).to_physical(region) == expected


def test_cross_monitor_region_rejected():
    with pytest.raises(ValueError):
        Monitor("test", Rect(0, 0, 100, 100), Rect(0, 0, 150, 150)).to_physical(
            Rect(50, 0, 100, 40)
        )


@pytest.mark.parametrize(
    "width,height",
    [(1280, 720), (1920, 1080), (2560, 1440), (3840, 2160), (3440, 1440), (1080, 1920)],
)
@pytest.mark.parametrize("scale", [1, 1.25, 1.5, 1.75, 2])
@pytest.mark.parametrize("negative", [False, True])
def test_display_partitions_preserve_edges_without_real_monitor_changes(
    width, height, scale, negative
):
    logical_width, logical_height = round(width / scale), round(height / scale)
    # Qt islands need not be a simple scaled copy of the physical desktop.
    logical = Rect(
        -1700 if negative else 200, -900 if negative else 100, logical_width, logical_height
    )
    physical = Rect(-width - 300 if negative else 1920, -height if negative else 0, width, height)
    monitor = Monitor("authored layout", logical, physical)
    assert monitor.to_physical(logical) == physical
    cuts = [0, logical_width // 3, 2 * logical_width // 3, logical_width]
    tiles = [
        monitor.to_physical(Rect(logical.x + left, logical.y, right - left, logical.height))
        for left, right in pairwise(cuts)
    ]
    assert tiles[0].x == physical.x and tiles[-1].right == physical.right
    assert all(left.right == right.x for left, right in pairwise(tiles))
    assert sum(tile.width for tile in tiles) == width
    assert all(physical.contains(tile) and tile.height == height for tile in tiles)


def test_change_detection_debounce_noise_and_static():
    gate = FrameGate(settle=0.3)
    image = Image.new("RGB", (640, 240), "black")
    assert gate.observe(image, 0).changed
    assert not gate.observe(image, 0.1).ready
    assert gate.observe(image, 0.4).ready
    for n in range(100):
        assert not gate.observe(image, n + 1).ready
    noise = Image.new("RGB", image.size, (1, 1, 1))
    assert not gate.observe(noise, 102).changed
    new = image.copy()
    ImageDraw.Draw(new).rectangle((20, 100, 200, 140), fill="white")
    assert gate.observe(new, 103).changed
    assert gate.observe(new, 103.4).ready


def test_animation_never_queues_intermediate_frames():
    gate = FrameGate(0.3)
    for n in range(30):
        image = Image.new("RGB", (100, 100), (n * 7, n * 7, n * 7))
        assert not gate.observe(image, n * 0.1).ready
    assert gate.observe(image, 3.4).ready


def test_live_motion_sampling_is_bounded_and_returns_to_static_suppression():
    gate = FrameGate(0.3, motion_interval=1.5)
    times = []
    for index in range(100):
        image = Image.new("RGB", (120, 80), ((index * 31) % 256,) * 3)
        decision = gate.observe(image, index * 0.1)
        if decision.ready:
            assert decision.moving
            times.append(index * 0.1)
    assert len(times) >= 5
    assert all(right - left >= 1.49 for left, right in zip(times, times[1:], strict=False))
    settled = gate.observe(image, 10.4)
    assert settled.ready and not settled.moving
    assert not gate.observe(image, 11).ready


def test_confirmed_text_can_change_by_one_character_at_lower_confidence():
    stabilizer = TemporalTextTracker()
    assert (
        stabilizer.observe(
            OCRResult("Dialogue line abc100", confidence=0.99), 0, settled_frame=True
        )
        == "Dialogue line abc100"
    )
    assert stabilizer.observe(OCRResult("Dialogue line abc101", confidence=0.93), 1) is None
    assert (
        stabilizer.observe(OCRResult("Dialogue line abc101", confidence=0.93), 1.5)
        == "Dialogue line abc101"
    )


def test_normalization_preserves_lines_and_japanese():
    assert normalize_text("  私は\t学生。\r\n\n Hello   world  ") == "私は 学生。\nHello world"


def test_reconstruction_reading_order():
    lines = (
        OCRLine("world", Rect(80, 0, 70, 20), 0.9),
        OCRLine("Second", Rect(0, 40, 80, 20), 0.9),
        OCRLine("Hello", Rect(0, 0, 60, 20), 0.9),
    )
    assert reconstruct(lines) == "Hello world\nSecond"
    assert reconstruct(lines, vertical=True).startswith("world")


def test_stabilization_corrects_fluctuation_and_suppresses_duplicates():
    stabilizer = TemporalTextTracker()
    assert stabilizer.observe(OCRResult("I don't kn0w.", confidence=0.6), 0) is None
    assert stabilizer.observe(OCRResult("I don't know.", confidence=0.95), 0.2) == "I don't know."
    assert stabilizer.observe(OCRResult("I don't know.", confidence=0.95), 0.5) is None
    assert stabilizer.observe(OCRResult("I don't know.", confidence=0.95), 0.9) is None


def test_high_confidence_settled_frame_needs_no_duplicate_inference():
    stabilizer = TemporalTextTracker()
    assert (
        stabilizer.observe(OCRResult("Stable dialogue", confidence=0.95), 0, settled_frame=True)
        == "Stable dialogue"
    )
    assert (
        stabilizer.observe(OCRResult("Stable dialogue", confidence=0.95), 1, settled_frame=True)
        is None
    )


def test_context_is_bounded_and_cleared():
    context = TranslationContext(2, 20)
    for n in range(10):
        context.accept(str(n), "translation")
    assert len(context.snapshot()) <= 2
    assert sum(len(p.source) + len(p.translation) for p in context.snapshot()) <= 20
    context.clear()
    assert context.snapshot() == ()


@pytest.mark.parametrize(
    "change",
    [
        {"target": "ja"},
        {"source": "ko"},
        {"model": "new-model"},
        {"style": "literal"},
        {"context": (ContextPair("previous", "translation"),)},
        {"glossary": (("name", "Name"),)},
        {"instructions": "Use honorifics"},
    ],
)
def test_cache_identity_includes_translation_configuration(change):
    request = TranslationRequest("Hello", "en", "ko")
    assert cache_key("openai", "https://api.example/v1", request) != cache_key(
        "openai", "https://api.example/v1", replace(request, **change)
    )


def test_cache_bounded_lru():
    cache = TranslationCache(2)
    cache.put("a", TranslationResult("A"))
    cache.put("b", TranslationResult("B"))
    assert cache.get("a").cached
    cache.put("c", TranslationResult("C"))
    assert cache.get("b") is None


def test_retired_unimplemented_speech_field_does_not_discard_existing_preferences(tmp_path):
    import json

    from desktranslate.settings import SettingsStore

    store = SettingsStore(tmp_path)
    store.path.write_text(
        json.dumps({"version": 2, "source": "ko", "target": "es", "speak": True}), encoding="utf-8"
    )
    settings = store.load()
    assert not store.recovered and (settings.source, settings.target) == ("ko", "es")
    store.save(settings)
    assert "speak" not in json.loads(store.path.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://example.com",
        "https://user:secret@example.com",
        "https://example.com/?key=abc",
        "https://example.com/#fragment",
        "https://example.com:99999",
        "https://example.com\\@evil.com",
        " https://example.com/a b",
    ],
)
def test_unsafe_endpoints_rejected(url):
    with pytest.raises(ConfigurationError):
        validate_endpoint(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://api.example/v1",
        "http://localhost:11434",
        "http://127.0.0.1:8080/v1",
        "http://[::1]:1234/v1",
    ],
)
def test_safe_endpoints(url):
    assert validate_endpoint(url) == url


def test_remote_cannot_masquerade_as_local():
    with pytest.raises(ConfigurationError):
        validate_endpoint("https://remote.example", local=True)


def test_settings_round_trip_corruption_and_migration(tmp_path):
    store = SettingsStore(tmp_path / "Unicode 日本語 path")
    settings = Settings(source="es", model="test")
    store.save(settings)
    assert store.load() == settings
    assert "api_key" not in store.path.read_text()
    store.path.write_text("{broken", encoding="utf-8")
    assert store.load() == Settings()
    assert store.recovered
    store.path.write_text(json.dumps({"version": 1, "source": "ko", "api_key": "secret"}))
    migrated = store.load()
    store.save(migrated)
    assert migrated.source == "ko"
    assert "secret" not in store.path.read_text()


@pytest.mark.parametrize(
    "change",
    [
        {"target": "auto"},
        {"overlay_size": -1},
        {"provider": "unknown"},
        {"recent_region": [0, 0, 0, 1]},
        {"hotkeys": []},
        {"onboarding_done": "true"},
    ],
)
def test_invalid_settings_rejected(change):
    with pytest.raises(ValueError):
        replace(Settings(), **change).validate()


def test_logging_discards_content_secrets_and_traceback():
    record = logging.LogRecord(
        "desktranslate",
        logging.ERROR,
        "private/path",
        10,
        "screen content %s",
        ("sk-secret",),
        (ValueError, ValueError("private dialogue"), None),
    )
    record.component = "pipeline"
    record.authorization = "Bearer sk-secret"
    record.category = "ProviderTimeoutError"
    formatted = PrivateFormatter().format(record)
    assert "sk-secret" not in formatted
    assert "private" not in formatted
    assert "screen content" not in formatted
    assert json.loads(formatted)["category"] == "ProviderTimeoutError"


def test_hotkey_validation():
    assert parse_hotkey("Ctrl+Alt+T") == (0x4003, ord("T"))
    with pytest.raises(ValueError):
        validate_hotkeys({"one": "Ctrl+Alt+T", "two": "Alt+Ctrl+T"})
    with pytest.raises(ValueError):
        parse_hotkey("Ctrl+Ctrl+T")
    assert REGISTRY["es"].tesseract == "spa"


def test_first_run_finds_alternative_without_mutating_defaults(monkeypatch):
    hotkeys = Hotkeys({"once": lambda: None})
    monkeypatch.setattr(
        hotkeys,
        "register",
        lambda values: [value for value in values.values() if "Shift" not in value],
    )
    defaults = {"once": "Ctrl+Alt+T"}
    assigned, conflicts = hotkeys.register_first_run(defaults)
    assert assigned == {"once": "Ctrl+Alt+Shift+T"}
    assert defaults == {"once": "Ctrl+Alt+T"}
    assert conflicts == []


def test_context_byte_budget_and_oversized_capture_are_bounded():
    context = TranslationContext(8, 12000)
    for _ in range(20):
        context.accept("あ" * 300, "가" * 300)
    assert context.token_upper_bound() <= 2400
    with pytest.raises(ValueError, match="too large"):
        Rect(0, 0, 16000, 16000)


def test_translation_targets_preserve_v1_coverage_without_claiming_managed_ocr():
    from desktranslate.languages import LANGUAGES, source_languages

    assert len([language for language in LANGUAGES if language.code != "auto"]) >= 133
    assert REGISTRY["he"].direction == "rtl"
    assert REGISTRY["th"].name == "Thai"
    assert "he" not in {language.code for language in source_languages("rapidocr")}
    assert "he" in {language.code for language in source_languages("tesseract")}


@pytest.mark.parametrize("values", [(2**40, 0, 10, 10), (0, -(2**40), 10, 10), (0, 0, True, 10)])
def test_native_coordinate_overflow_is_rejected(values):
    with pytest.raises(ValueError):
        Rect(*values)


def test_vertical_columns_tolerate_detection_jitter_and_rtl_reads_right_to_left():
    vertical = (
        OCRLine("上", Rect(101, 0, 20, 20), 0.9),
        OCRLine("下", Rect(103, 30, 20, 20), 0.9),
        OCRLine("左", Rect(40, 0, 20, 20), 0.9),
    )
    assert reconstruct(vertical, vertical=True) == "上\n下\n左"
    horizontal = (
        OCRLine("العالم", Rect(0, 0, 70, 20), 0.9),
        OCRLine("مرحبا", Rect(80, 0, 70, 20), 0.9),
    )
    assert reconstruct(horizontal, direction="rtl") == "مرحبا العالم"
    latin = (OCRLine("Hello", Rect(0, 0, 60, 20), 0.9), OCRLine("world", Rect(80, 0, 70, 20), 0.9))
    assert reconstruct(latin, direction="rtl") == "Hello world"


def test_damaged_settings_cannot_be_overwritten_by_automatic_save(tmp_path):
    store = SettingsStore(tmp_path)
    original = '{"version":2,"profiles":{"Keep me":{}}BROKEN'
    store.path.write_text(original)
    settings = store.load()
    with pytest.raises(ValueError, match="retained"):
        store.save(settings)
    assert store.path.read_text() == original


def test_portable_data_isolated_from_installed_app(tmp_path, monkeypatch):
    import sys

    from desktranslate.settings import data_dir

    monkeypatch.delenv("DESKTRANSLATE_DATA_DIR", raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "DeskTranslate.exe"))
    (tmp_path / "portable-mode").write_text("portable")
    assert data_dir() == tmp_path / "DeskTranslateData"
    (tmp_path / "portable-mode").unlink()
    assert data_dir() != tmp_path / "DeskTranslateData"


@pytest.mark.parametrize("notification", [2, 4, 7])
def test_windows_session_lock_and_disconnect_stop_capture(notification):
    import ctypes
    from ctypes import wintypes

    stopped = []
    hotkeys = Hotkeys({}, lambda: stopped.append(True))
    message = wintypes.MSG()
    message.message = 0x02B1
    message.wParam = notification
    assert hotkeys.nativeEventFilter(b"windows_generic_MSG", ctypes.addressof(message)) == (
        False,
        0,
    )
    assert stopped == [True]
