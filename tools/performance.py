"""Opt-in bounded synthetic soak and overlay paint measurements; no external services."""

from __future__ import annotations

import json
import statistics
import time
import tracemalloc
from pathlib import Path

from PIL import Image
from PySide6.QtWidgets import QApplication

from desktranslate.models import Capabilities, OCRResult, TranslationResult
from desktranslate.pipeline import Pipeline
from desktranslate.settings import Settings
from desktranslate.ui.overlay import Overlay
from desktranslate.ui.theme import apply_theme


def main() -> None:
    app = QApplication([])
    apply_theme(app, "dark")
    overlay = Overlay(Settings(reduced_motion=True))
    overlay.display("Original", "Let's meet here again tomorrow.")
    app.processEvents()
    overlay.grab()
    measures = []
    for _ in range(200):
        start = time.perf_counter()
        overlay.grab()
        measures.append((time.perf_counter() - start) * 1000)

    class Capture:
        color = 0

        def capture(self, region):
            return Image.new("RGB", (120, 80), (self.color,) * 3)

        def close(self):
            pass

    class OCR:
        def recognize(self, image, language, vertical=False):
            return OCRResult(str(image.getpixel((0, 0))[0]), confidence=0.99)

        def close(self):
            pass

    class Provider:
        capabilities = Capabilities(context=True)

        def translate(self, request):
            time.sleep(0.06)
            return TranslationResult("Translated " + request.text)

        def close(self):
            pass

    capture = Capture()
    pipeline = Pipeline(
        Settings(quality="fast", recent_region=[0, 0, 120, 80]), lambda: capture, OCR, Provider
    )
    tracemalloc.start()
    pipeline.start()
    accepted = 0
    max_events = 0
    start = time.monotonic()
    while time.monotonic() - start < 30:
        elapsed = time.monotonic() - start
        # First ten seconds are idle. Then a new stable synthetic frame every 0.5 s.
        if elapsed > 10:
            capture.color = int((elapsed - 10) * 2) * 5 % 250
        max_events = max(max_events, pipeline.events.qsize())
        for event in pipeline.poll():
            if event.result:
                accepted += 1
                overlay.display(event.source, event.result.text)
        app.processEvents()
        time.sleep(0.02)
    memory, peak = tracemalloc.get_traced_memory()
    pipeline.stop()
    report = {
        "duration_s": 30,
        "synthetic_inference": True,
        "overlay_cached_paint_median_ms": statistics.median(measures),
        "overlay_cached_paint_p95_ms": sorted(measures)[190],
        "accepted": accepted,
        "counters": pipeline.counters,
        "max_event_queue": max_events,
        "frame_queue": pipeline.frames.queue.qsize(),
        "text_queue": pipeline.texts.queue.qsize(),
        "context_pairs": len(pipeline.context.snapshot()),
        "cache_entries": len(pipeline.cache.items),
        "python_memory_bytes": memory,
        "python_peak_bytes": peak,
    }
    Path("docs/performance.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    overlay.close()
    print("Synthetic soak complete; see docs/performance.json")


if __name__ == "__main__":
    main()
