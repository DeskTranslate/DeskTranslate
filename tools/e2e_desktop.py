"""Opt-in live desktop probe displaying only a synthetic fixture; no user content saved."""

from __future__ import annotations

import json
import time
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

from desktranslate.capture import (
    MSSCapture,
    enable_dpi_awareness,
    physical_monitors,
    topology_signature,
)
from desktranslate.errors import CaptureError, TranslationError
from desktranslate.models import Monitor, Rect
from desktranslate.ocr import IsolatedOCR
from desktranslate.pipeline import Pipeline
from desktranslate.providers import create_provider
from desktranslate.settings import Settings


def main() -> None:
    enable_dpi_awareness()
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QPixmap
    from PySide6.QtWidgets import QApplication, QLabel

    app = QApplication([])
    window = QLabel()
    window.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
    window.setPixmap(QPixmap("tests/fixtures/ja-game.png"))
    window.resize(660, 160)
    window.move(80, 80)
    window.show()
    report: dict[str, object] = {}
    pipeline: Pipeline | None = None
    started = time.monotonic()

    def begin() -> None:
        nonlocal pipeline
        screen = window.screen()
        logical = screen.geometry()
        pixels = physical_monitors()[screen.name()]
        monitor = Monitor(
            screen.name(), Rect(logical.x(), logical.y(), logical.width(), logical.height()), pixels
        )
        frame = window.geometry()
        crop = monitor.to_physical(Rect(frame.x(), frame.y(), frame.width(), frame.height()))
        report["crop"] = [crop.x, crop.y, crop.width, crop.height]

        class SyntheticCapture(MSSCapture):
            def capture(self, region: Rect) -> Image.Image:
                image = super().capture(region)
                expected = (
                    Image.open("tests/fixtures/ja-game.png").convert("RGB").resize(image.size)
                )
                difference = sum(ImageStat.Stat(ImageChops.difference(image, expected)).mean) / 3
                report["fixture_difference"] = difference
                if difference > 4:
                    raise CaptureError(
                        "Synthetic fixture was obstructed. Retry with no windows covering it."
                    )
                return image

        class SyntheticProvider:
            def __init__(self) -> None:
                self.provider = create_provider("google")
                self.capabilities = self.provider.capabilities

            def translate(self, request):
                if request.text != "明日、またここで会おう。":
                    report["recognized_length"] = len(request.text)
                    raise TranslationError(
                        "Synthetic OCR did not match the reference. No text was sent."
                    )
                return self.provider.translate(request)

            def close(self) -> None:
                self.provider.close()

        settings = Settings(
            quality="fast",
            recent_region=[crop.x, crop.y, crop.width, crop.height],
            display_signature=topology_signature(),
        )
        pipeline = Pipeline(
            settings,
            lambda: SyntheticCapture(settings.display_signature),
            lambda: IsolatedOCR("rapidocr", "ja"),
            SyntheticProvider,
            once=True,
        )
        pipeline.start()

    def poll() -> None:
        if pipeline:
            for event in pipeline.poll():
                if event.error:
                    report["error_category"] = event.category
                    finish()
                    return
                if event.result:
                    report.update(
                        {
                            "source_exact": event.source == "明日、またここで会おう。",
                            "translation_nonempty": bool(event.result.text),
                            "translation_different": event.result.text != event.source,
                            "timings_ms": event.timings,
                        }
                    )
                    finish()
                    return
        if time.monotonic() - started > 35:
            report["timeout"] = True
            finish()

    def finish() -> None:
        if pipeline:
            pipeline.stop()
        Path(".audit/desktop-e2e.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        window.close()
        app.quit()

    QTimer.singleShot(700, begin)
    timer = QTimer()
    timer.timeout.connect(poll)
    timer.start(60)
    app.exec()


if __name__ == "__main__":
    main()
