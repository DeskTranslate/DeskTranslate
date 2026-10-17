"""Owned authored desktop scene, native picker/MSS/OCR and loopback translation."""

from __future__ import annotations

import argparse
import json
import multiprocessing
import platform
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from PIL import Image, ImageChops, ImageStat

from desktranslate import __version__
from desktranslate.capture import MSSCapture, enable_dpi_awareness, physical_monitors
from desktranslate.models import Monitor, Rect, Stamp
from desktranslate.ocr import IsolatedOCR, ModelManager
from desktranslate.pipeline import Pipeline
from desktranslate.providers import create_provider
from desktranslate.settings import Settings


def main() -> None:
    from qualification_policy import require_interactive_desktop

    require_interactive_desktop()
    parser = argparse.ArgumentParser()
    parser.add_argument("--quality", choices=["fast", "balanced", "accuracy"], default="balanced")
    args = parser.parse_args()
    enable_dpi_awareness()
    from PySide6.QtCore import QPoint, QRect, Qt
    from PySide6.QtGui import QColor, QFont, QPainter, QPen
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QWidget

    from desktranslate.ui.selection import RegionSelector
    from desktranslate.ui.theme import apply_theme

    if not ModelManager().installed("en", verify=True):
        raise RuntimeError("Install verified English models before this opt-in qualification")
    app = QApplication([])
    apply_theme(app, "dark")
    report: dict[str, object] = {
        "version": __version__,
        "system": platform.platform(),
        "authored_content_only": True,
        "provider": "Real loopback HTTP, not cloud/model qualification",
        "quality": args.quality,
        "checks": {},
    }
    checks = report["checks"]

    class Scene(QWidget):
        moving = False
        sequence = 0
        text = "Tomorrow we meet again."

        def paintEvent(self, event):
            painter = QPainter(self)
            if self.moving:
                shade = 30 + (self.sequence % 6) * 15
                painter.fillRect(self.rect(), QColor(shade, shade + 20, shade + 35))
                painter.setFont(QFont("Segoe UI", 24))
                painter.setPen(QPen(QColor("white")))
                painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text)
            else:
                for y in range(0, self.height(), 30):
                    for x in range(0, self.width(), 30):
                        painter.fillRect(x, y, 30, 30, QColor(40 + x % 150, 40 + y % 150, 80))

    target = Scene()
    target.setWindowTitle("DeskTranslate authored selection/motion qualification")
    target.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
    target.showFullScreen()

    def events(seconds=0.2):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.01)

    pipeline = None
    server = None
    server_thread = None
    picker = None
    capture = None
    try:
        events(0.5)
        screen = target.screen()
        logical = screen.geometry()
        physical = physical_monitors()[screen.name()]
        monitor = Monitor(
            screen.name(),
            Rect(logical.x(), logical.y(), logical.width(), logical.height()),
            physical,
        )
        report["display"] = {
            "physical": [physical.x, physical.y, physical.width, physical.height],
            "logical": [logical.x(), logical.y(), logical.width(), logical.height()],
            "dpr": screen.devicePixelRatio(),
            "logical_dpi": screen.logicalDotsPerInch(),
            "physical_monitor_count": len(physical_monitors()),
        }
        picker = RegionSelector()
        selected = []
        picker.selected.connect(selected.append)
        picker.start()
        events()
        window = next(window for window in picker.windows if window.monitor.name == screen.name())
        frozen = window.screenshot.toImage()
        QTest.mousePress(window, Qt.MouseButton.LeftButton, pos=QPoint(40, 60))
        QTest.mouseMove(window, QPoint(240, 160), 30)
        QTest.mouseRelease(window, Qt.MouseButton.LeftButton, pos=QPoint(240, 160))
        checks["drag_selection"] = window.has_region
        QTest.mousePress(window, Qt.MouseButton.LeftButton, pos=QPoint(240, 160))
        QTest.mouseMove(window, QPoint(280, 200), 30)
        QTest.mouseRelease(window, Qt.MouseButton.LeftButton, pos=QPoint(280, 200))
        expected = monitor.to_physical(Rect(logical.x() + 40, logical.y() + 60, 241, 141))
        checks["corner_resize"] = window.physical_rect() == expected
        QTest.keyClick(window, Qt.Key.Key_Return)
        events()
        checks["enter_accepts_and_closes"] = (
            selected == [expected] and picker.closed and not picker.windows
        )
        # The only persisted output is numeric. Frozen pixels and captures stay in memory.
        crop = frozen.copy(
            QRect(expected.x - physical.x, expected.y - physical.y, expected.width, expected.height)
        )
        crop = crop.convertToFormat(crop.Format.Format_RGB888)
        frozen_image = Image.frombytes(
            "RGB",
            (crop.width(), crop.height()),
            bytes(crop.bits()),
            "raw",
            "RGB",
            crop.bytesPerLine(),
        )
        capture = MSSCapture()
        actual = capture.capture(expected)
        difference = sum(ImageStat.Stat(ImageChops.difference(actual, frozen_image)).mean) / 3
        report["selection_capture_mean_pixel_difference"] = difference
        checks["physical_capture_matches_frozen_selection"] = difference < 4
        picker = RegionSelector()
        cancelled = []
        picker.cancelled.connect(lambda: cancelled.append(True))
        picker.start()
        events()
        QTest.keyClick(picker.windows[0], Qt.Key.Key_Escape)
        events()
        checks["escape_cancels_and_closes"] = (
            cancelled == [True] and picker.closed and not picker.windows
        )

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0"))
                self.rfile.read(min(length, 20_000))
                body = b'{"choices":[{"message":{"content":"Authored translated result"}}]}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.daemon_threads = True
        server_thread = Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        target.showNormal()
        target.setGeometry(logical.x() + 100, logical.y() + 80, 528, 128)
        target.moving = True
        events()
        geometry = target.geometry()
        region = monitor.to_physical(
            Rect(geometry.x(), geometry.y(), geometry.width(), geometry.height())
        )
        settings = Settings(
            source="en",
            provider="custom",
            quality=args.quality,
            recent_region=[region.x, region.y, region.width, region.height],
        )
        pipeline = Pipeline(
            settings,
            MSSCapture,
            lambda: IsolatedOCR("rapidocr", "en"),
            lambda: create_provider("custom", endpoint=f"http://127.0.0.1:{server.server_port}/v1"),
        )
        pipeline.start()
        started = time.monotonic()
        results = []
        blank = False
        while (elapsed := time.monotonic() - started) < 36:
            target.sequence += 1
            target.text = (
                "Tomorrow we meet again."
                if elapsed < 11 or elapsed >= 27
                else ("" if elapsed >= 22 else "Good morning, Mika.")
            )
            target.update()
            for event in pipeline.poll():
                if event.category:
                    raise RuntimeError("Authored native motion pipeline failed: " + event.category)
                if event.clear:
                    blank = True
                    pipeline.delivered_source = ""
                if event.result:
                    with pipeline.session.lock:
                        if event.stamp != Stamp(
                            pipeline.session.serial, pipeline.session.generation
                        ):
                            continue
                        pipeline.delivered_source = event.source
                        results.append(
                            {
                                "elapsed_s": round(elapsed, 3),
                                "source": event.source,
                                "total_ms": event.timings.get("total_ms"),
                            }
                        )
            events(0.05)
        texts = [row["source"] for row in results]
        checks["continuously_moving_background_translates"] = any(
            "Tomorrow" in text for text in texts
        )
        checks["changed_dialogue_translates"] = any("Good morning" in text for text in texts)
        checks["blank_interval_recognized"] = blank
        checks["same_dialogue_returns_after_blank"] = sum("Tomorrow" in text for text in texts) >= 2
        report["motion_results"] = results
        report["motion_counters"] = dict(pipeline.counters)
    finally:
        if picker:
            picker.cleanup()
        if capture:
            capture.close()
        if pipeline:
            pipeline.stop()
            checks["pipeline_workers_closed"] = pipeline.wait_closed(10)
        if server:
            server.shutdown()
            server.server_close()
        if server_thread:
            server_thread.join(2)
        target.close()
        events()
        checks["ocr_children_closed"] = not multiprocessing.active_children()
        report["passed"] = all(value is True for value in checks.values()) and len(checks) >= 11
        Path("docs/selection-motion-qualification.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        print(json.dumps(report))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
