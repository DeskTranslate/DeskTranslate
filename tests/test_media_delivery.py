import time

from PIL import Image

from desktranslate.models import Capabilities, OCRResult, TranslationResult
from desktranslate.pipeline import Pipeline
from desktranslate.settings import Settings


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
