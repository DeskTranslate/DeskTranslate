"""Opt-in offscreen product journeys: real OCR, owned HTTP, synthetic capture only."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import multiprocessing
import os
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_SCALE_FACTOR"] = "1"

from PIL import Image, ImageDraw
from PySide6.QtGui import QDesktopServices, QScreen
from PySide6.QtWidgets import QApplication
from release_support import runtime_source_hashes

from desktranslate import __version__
from desktranslate.hotkeys import Hotkeys
from desktranslate.models import Rect, SessionState
from desktranslate.ocr import IsolatedOCR, ModelManager
from desktranslate.security import CredentialStore
from desktranslate.settings import Settings, SettingsStore
from desktranslate.ui.window import MainWindow

ROOT = Path(__file__).resolve().parents[1]


class Server(ThreadingHTTPServer):
    daemon_threads = True
    failures = False
    requests = 0
    reply = "Let's meet here again tomorrow."


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        server: Server = self.server
        data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        assert data["messages"] and data["model"] == "authored-fixture"
        server.requests += 1
        status = 503 if server.failures else 200
        body = json.dumps({"choices": [{"message": {"content": server.reply}}]}).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class Capture:
    def __init__(self):
        self.image = Image.open(ROOT / "tests/fixtures/ja-game.png").convert("RGB")
        self.count = 0

    def capture(self, region):
        self.count += 1
        return self.image.copy()

    def close(self):
        pass


def wait_for(app, condition, timeout=25):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if condition():
            return
        time.sleep(0.01)
    raise AssertionError("Product component did not reach its expected state within the deadline")


def negative_images():
    """No copied media/fonts or text: predictable backgrounds that can resemble glyphs."""
    for kind in ("dark", "bright", "gradient", "stripes", "grid", "shapes"):
        image = Image.new("RGB", (660, 160), "#172736" if kind != "bright" else "#f4f6f8")
        draw = ImageDraw.Draw(image)
        if kind == "gradient":
            for x in range(image.width):
                draw.line((x, 0, x, 159), fill=(x % 256, 120, 255 - x % 256))
        elif kind in {"stripes", "grid"}:
            for x in range(0, 660, 22):
                draw.line((x, 0, x, 159), fill="#72869a", width=3)
            if kind == "grid":
                for y in range(0, 160, 22):
                    draw.line((0, y, 659, y), fill="#72869a", width=3)
        elif kind == "shapes":
            for x in range(20, 600, 100):
                draw.ellipse((x, 25, x + 60, 115), outline="#c3d8a5", width=5)
                draw.line((x, 130, x + 70, 40), fill="#b18a76", width=4)
        yield kind, image


def qualify(models: Path) -> dict:
    report = {
        "version": __version__,
        "source_hashes": runtime_source_hashes(ROOT),
        "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "scope": "Offscreen main-window controller, authored captures, actual isolated CPU OCR and owned loopback HTTP. HTTP responses are fixtures, not semantic provider qualification.",
        "desktop_capture": False,
        "global_input": False,
        "system_changes": False,
        "checks": {},
        "negative_ocr": [],
        "passed": False,
    }
    manager = ModelManager(models)
    if not all(manager.installed(code, verify=True) for code in ("ja", "en", "ko", "zh-CN")):
        raise ValueError("Verified Japanese, English, Korean and Chinese packs must already exist")
    app = QApplication.instance() or QApplication([])
    screens = {
        s.name(): Rect(
            s.geometry().x(), s.geometry().y(), s.geometry().width(), s.geometry().height()
        )
        for s in app.screens()
    }
    capture = Capture()
    server = Server(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()

    def forbidden(*args, **kwargs):
        raise AssertionError("Real desktop or browser access is forbidden in this component probe")

    window = None
    try:
        with tempfile.TemporaryDirectory(prefix="desktranslate-authored-product-") as directory:
            store = SettingsStore(Path(directory))
            store.save(
                Settings(
                    onboarding_done=True,
                    quality="fast",
                    reduced_motion=True,
                    recent_region=[0, 0, 660, 160],
                    provider="custom",
                    model="authored-fixture",
                    endpoint=f"http://127.0.0.1:{server.server_port}/v1",
                )
            )
            with contextlib.ExitStack() as boundaries:
                replacements = {
                    "mss.mss": forbidden,
                    "desktranslate.ui.window.MSSCapture": lambda signature: capture,
                    "desktranslate.ui.window.ModelManager": lambda: manager,
                    "desktranslate.ui.window.IsolatedOCR": lambda name, code: IsolatedOCR(
                        name, code, models
                    ),
                    "desktranslate.ui.window.physical_monitors": lambda: screens,
                    "desktranslate.ui.overlay.physical_monitors": lambda: screens,
                }
                for name, replacement in replacements.items():
                    boundaries.enter_context(patch(name, replacement))
                boundaries.enter_context(patch.object(QScreen, "grabWindow", forbidden))
                boundaries.enter_context(patch.object(QDesktopServices, "openUrl", forbidden))
                boundaries.enter_context(patch.object(Hotkeys, "register", return_value=[]))
                boundaries.enter_context(patch.object(CredentialStore, "get", return_value=""))
                window = MainWindow(store, demo=True)
                # A real worker and adapter must deliver through the controller's normal receipt path.
                started = time.perf_counter()
                window.start(True)
                wait_for(app, lambda: window.latest == server.reply and not window.timer.isActive())
                assert window.result_source.text() == "明日、またここで会おう。"
                assert window.overlay.translation.text() == server.reply
                assert "complete" in window.session_status.text()
                report["one_shot_ms"] = round((time.perf_counter() - started) * 1000, 2)
                report["checks"]["one_shot_real_ocr_http_overlay"] = True
                started = time.perf_counter()
                window.start(False)
                serial = window.presentation_serial
                wait_for(app, lambda: window.presentation_serial > serial)
                report["live_first_result_ms"] = round((time.perf_counter() - started) * 1000, 2)
                window.pause_button.click()
                wait_for(app, lambda: window.pipeline.paused.is_set())
                # Allow the last already-started capture to leave the capture boundary.
                time.sleep(0.10)
                count = capture.count
                until = time.monotonic() + 0.35
                while time.monotonic() < until:
                    app.processEvents()
                    time.sleep(0.01)
                assert capture.count == count and window.pause_button.text() == "Resume"
                # Static content is deliberately not retranslated on resume. A new
                # authored line must nevertheless make it through every stage.
                capture.image = Image.open(ROOT / "tests/fixtures/ja-multiline.png").convert("RGB")
                server.reply = "Do you remember this town? Tell me again."
                serial = window.presentation_serial
                started = time.perf_counter()
                window.pause_button.click()
                wait_for(app, lambda: window.presentation_serial > serial)
                report["resume_changed_text_ms"] = round((time.perf_counter() - started) * 1000, 2)
                report["checks"]["live_pause_capture_suppression_resume"] = True
                server.failures = True
                window.start(False)
                wait_for(app, lambda: window.pipeline.session.state == SessionState.ERROR)
                wait_for(app, lambda: window.pause_button.text() == "Retry translation")
                assert window.pause_button.isEnabled()
                server.failures = False
                started = time.perf_counter()
                window.pause_button.click()
                serial = window.presentation_serial
                wait_for(app, lambda: window.presentation_serial > serial)
                report["retry_result_ms"] = round((time.perf_counter() - started) * 1000, 2)
                report["checks"]["http_outage_visible_error_retry"] = True
                capture.image = Image.open(ROOT / "tests/fixtures/en-ui.png").convert("RGB")
                server.reply = "翻訳する領域を選択してください。"
                window.swap_languages()
                assert window.pipeline is None
                started = time.perf_counter()
                window.start(True)
                wait_for(app, lambda: window.latest == server.reply and not window.timer.isActive())
                assert window.result_source.text() == "Select a region to translate."
                report["language_switch_result_ms"] = round(
                    (time.perf_counter() - started) * 1000, 2
                )
                report["checks"]["atomic_language_change_actual_ocr"] = True
                window.stop()
                wait_for(app, lambda: not window.retiring and not window.timer.isActive())
                assert window.pipeline is None and not window.pause_button.isEnabled()
                restored = store.load()
                assert (restored.source, restored.target, restored.provider) == (
                    "en",
                    "ja",
                    "custom",
                )
                assert not any(
                    word in (Path(directory) / "settings.json").read_text(encoding="utf-8")
                    for word in ("明日", "Select a region", server.reply)
                )
                report["checks"]["stop_cleanup_preferences_without_content_retention"] = True
                window.quit()
                wait_for(app, lambda: not window.shutdown_timer.isActive())
                window = None
            for code in ("ja", "en", "ko", "zh-CN"):
                engine = IsolatedOCR("rapidocr", code, models)
                try:
                    for kind, image in negative_images():
                        result = engine.recognize(image, code)
                        report["negative_ocr"].append(
                            {
                                "source": code,
                                "background": kind,
                                "characters": len(result.text.strip()),
                                "text": result.text,
                                "confidence": round(result.confidence, 4),
                                "ocr_ms": round(result.duration_ms, 2),
                                "result": "PASS" if not result.text.strip() else "FAIL",
                            }
                        )
                finally:
                    engine.close()
                    engine.reap()
            report["checks"]["negative_ocr_no_false_text"] = all(
                row["result"] == "PASS" for row in report["negative_ocr"]
            )
            report["requests"] = server.requests
            report["remaining_children"] = len(multiprocessing.active_children())
            report["checks"]["no_remaining_ocr_children"] = report["remaining_children"] == 0
            report["passed"] = all(report["checks"].values())
    except Exception as error:
        report["failure_category"] = type(error).__name__
        if window and window.pipeline:
            report["failure_state"] = window.pipeline.session.state.value
            report["failure_counters"] = dict(window.pipeline.counters)
            report["failure_categories"] = list(window.errors)
    finally:
        if window is not None:
            window.quit()
            wait_for(app, lambda: not window.shutdown_timer.isActive(), timeout=40)
        server.shutdown()
        server.server_close()
        worker.join(5)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--component-test",
        action="store_true",
        help="Opt into CPU OCR; no real desktop or external provider",
    )
    parser.add_argument("--models", type=Path, default=ROOT / ".test-data/models")
    parser.add_argument("--output", type=Path, default=ROOT / ".audit/product-component.json")
    args = parser.parse_args()
    if not args.component_test:
        parser.error(
            "Real OCR component qualification requires --component-test; excluded from routine tests"
        )
    if os.environ.get("DESKTRANSLATE_COMPONENT_CHILD") != str(Path(__file__).resolve()):
        from qualification_policy import run_bounded_probe

        environment = dict(os.environ, DESKTRANSLATE_COMPONENT_CHILD=str(Path(__file__).resolve()))
        return run_bounded_probe(
            [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]],
            environment,
            240,
            ROOT,
            "Product component",
        )
    report = qualify(args.models.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "checks": report["checks"],
                "passed": report["passed"],
                "report": str(args.output),
                "failure_category": report.get("failure_category", ""),
                "negative_ocr_passed": sum(
                    row["result"] == "PASS" for row in report["negative_ocr"]
                ),
                "negative_ocr_total": len(report["negative_ocr"]),
            }
        )
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
