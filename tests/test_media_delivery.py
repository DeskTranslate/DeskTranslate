import time

import pytest
from PIL import Image

from desktranslate.models import Capabilities, OCRResult, TranslationResult
from desktranslate.pipeline import Pipeline
from desktranslate.settings import Settings


@pytest.mark.parametrize(
    "before,after",
    [("Ready!", "Wait for me!"), ("Wait for me!", "Wait for me?"), ("Wait for me?", "")],
)
def test_short_static_subtitle_and_punctuation_change_are_not_lost(
    before, after, tmp_path, monkeypatch
):
    from pathlib import Path

    from desktranslate.algorithms import FrameGate

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "tools"))
    from fixtures import render_fixture

    frames = []
    for index, text in enumerate((before, after)):
        path = tmp_path / f"subtitle{index}.png"
        render_fixture(
            dict(
                id=path.stem,
                language="en",
                text=text,
                size=30,
                bg="#172736",
                fg="white",
                outline=True,
            ),
            path,
        )
        with Image.open(path) as image:
            frames.append(image.convert("RGB"))
    gate = FrameGate(0.15, motion_interval=0.45)
    gate.observe(frames[0], 0)
    assert gate.observe(frames[0], 0.2).ready
    assert gate.observe(frames[1], 2).changed
    assert gate.observe(frames[1], 2.2).ready
    assert not gate.observe(frames[1], 4).ready


def test_change_detection_ignores_low_amplitude_noise_and_isolated_hot_pixels():
    from desktranslate.algorithms import FrameGate

    gate = FrameGate(0.15)
    base = Image.new("RGB", (256, 128), "black")
    gate.observe(base, 0)
    gate.observe(base, 0.2)
    noise = base.copy()
    noise.putpixel((25, 50), (255, 255, 255))
    noise.putpixel((125, 30), (255, 255, 255))
    assert not gate.observe(noise, 1).changed
    assert not gate.observe(Image.new("RGB", base.size, (1, 1, 1)), 2).changed


def test_numeric_metrics_retain_complete_vertical_pipeline_and_presentation_stages():
    from desktranslate.metrics import LatencyMetrics

    names = (
        "capture",
        "change",
        "preprocess",
        "ocr_layout_detect",
        "ocr_layout_recognize",
        "ocr_detect",
        "ocr_recognize",
        "ocr_reconstruct",
        "ocr",
        "ocr_call",
        "temporal",
        "context",
        "queue",
        "provider",
        "total",
        "gui_delivery",
        "overlay_schedule",
        "presentation",
        "render",
    )
    metrics = LatencyMetrics()
    metrics.observe({name + "_ms": 1.5 for name in names})
    assert set(metrics.snapshot()) == {name + "_ms" for name in names}


def test_media_freshness_counts_dialogue_turns_not_typewriter_frames(monkeypatch):
    from pathlib import Path

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "tools"))
    from qualify_media_pipeline import Cue, semantic_lag

    cues = [
        Cue("prefix", "彼", 0.1, turn="reveal"),
        Cue("complete", "彼女は昨日ここに来た。", 3, turn="reveal"),
        Cue("next", "Wait!", 2),
        Cue("later", "Go!", 2),
    ]
    assert semantic_lag(cues, 0, 1) == 0
    assert semantic_lag(cues, 0, 2) == 1
    assert semantic_lag(cues, 0, 3) == 2


def test_intermittent_animation_does_not_revoke_every_slow_ocr_result():
    started = time.monotonic()

    class Capture:
        def capture(self, region):
            phase = int((time.monotonic() - started) * 5) % 2
            return Image.new("RGB", (120, 80), "#152535" if phase else "#617383")

        def close(self):
            pass

    class OCR:
        def recognize(self, image, language, vertical=False):
            time.sleep(0.55)
            return OCRResult("A complete subtitle.", confidence=0.99)

        def close(self):
            pass

    class Provider:
        capabilities = Capabilities()

        def translate(self, request):
            return TranslationResult("Delivered")

        def close(self):
            pass

    pipeline = Pipeline(
        Settings(quality="fast", recent_region=[0, 0, 120, 80]), Capture, OCR, Provider
    )
    pipeline.start()
    results = []
    try:
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and not results:
            results.extend(event for event in pipeline.poll() if event.result)
            time.sleep(0.01)
        assert results, "Brief quiet gaps in 5Hz animation must not starve slow OCR"
        assert results[-1].source == "A complete subtitle."
        assert pipeline.frames.queue.qsize() <= 1
    finally:
        pipeline.stop()
        assert pipeline.wait_closed(3)
