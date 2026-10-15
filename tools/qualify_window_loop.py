"""Own authored window, real main controller/capture/OCR/live Google; no user content."""

import argparse
import json
import multiprocessing
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path.cwd()
AREA = ROOT / ".audit/window-loop"
TITLE = "DeskTranslate authored end-to-end target"


def main():
    from qualification_policy import require_interactive_desktop

    require_interactive_desktop()
    from desktranslate.capture import enable_dpi_awareness

    enable_dpi_awareness()
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QPixmap
    from PySide6.QtWidgets import QApplication, QLabel, QWidget

    app = QApplication([])
    AREA.mkdir(parents=True, exist_ok=True)
    command_file = AREA / "command.json"
    ready_file = AREA / "ready.json"
    if "--target" in sys.argv:
        widget = QLabel()
        widget.setWindowTitle(TITLE)
        widget.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        widget.setPixmap(QPixmap(str(ROOT / "tests/fixtures/ja-game.png")))
        widget.setScaledContents(True)
        widget.setGeometry(90, 90, 528, 128)
        widget.show()
        widget.raise_()
        ready_file.write_text(
            json.dumps({"handle": int(widget.winId()), "pid": os.getpid()}), encoding="utf-8"
        )
        previous = None

        def poll():
            nonlocal previous
            try:
                command = json.loads(command_file.read_text())
            except (OSError, ValueError):
                return
            if command == previous:
                return
            previous = command
            action = command["action"]
            if action == "move":
                widget.move(270, 170)
            elif action == "resize":
                widget.resize(620, 180)
            elif action == "minimize":
                widget.showMinimized()
            elif action == "restore":
                widget.showNormal()
                widget.raise_()
            elif action == "quit":
                widget.close()
                app.quit()

        timer = QTimer()
        timer.timeout.connect(poll)
        timer.start(80)
        raise SystemExit(app.exec())

    from release_support import git_trace

    from desktranslate import __version__
    from desktranslate.models import SessionState
    from desktranslate.ocr import ModelManager
    from desktranslate.settings import Settings, SettingsStore
    from desktranslate.ui.window import MainWindow
    from desktranslate.window_capture import Win32Windows

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-data-directory", type=Path, default=ROOT / ".test-data/models")
    args = parser.parse_args()
    os.environ["DESKTRANSLATE_DATA_DIR"] = str(AREA / "設定 data")
    models = ModelManager()
    source_models = ModelManager(args.model_data_directory)
    assert source_models.installed("ja", verify=True)
    models.directory.mkdir(parents=True, exist_ok=True)
    for name in source_models.required("ja"):
        shutil.copyfile(source_models.path(name), models.path(name))
    assert models.installed("ja", verify=True)
    for path in (command_file, ready_file):
        path.unlink(missing_ok=True)
    target = subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), "--interactive-desktop", "--target"],
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    window = None
    blocker = None
    started = time.monotonic()
    checks = {}

    def wait(predicate, timeout=90):
        deadline = time.monotonic() + timeout
        while not predicate():
            app.processEvents()
            if time.monotonic() > deadline:
                raise TimeoutError("Authored main-window loop timed out")
            if target.poll() is not None:
                raise RuntimeError("Owned target exited early")
            time.sleep(0.02)
        app.processEvents()

    def command(action):
        command_file.write_text(
            json.dumps({"action": action, "serial": time.monotonic_ns()}), encoding="utf-8"
        )

    def count():
        return window.metrics.snapshot().get("total_ms", {}).get("count", 0)

    def state():
        return window.pipeline.session.state

    try:
        wait(ready_file.exists, 20)
        inspector = Win32Windows()
        ready = json.loads(ready_file.read_text())
        handle = ready["handle"]
        info = inspector.info(handle)
        assert info and info.title == TITLE and info.pid == ready["pid"]
        store = SettingsStore()
        store.save(
            Settings(
                source="ja",
                target="en",
                provider="google",
                quality="fast",
                onboarding_done=True,
                reduced_motion=True,
                capture_mode="window",
                window_target=info.binding(),
                window_region=[0, 0, 1, 1],
                recent_region=[info.client.x, info.client.y, info.client.width, info.client.height],
            )
        )
        window = MainWindow(store, demo=True)
        window.hide()
        window.start(False)
        wait(lambda: count() >= 1)
        checks["actual_ocr_exact"] = window.result_source.text() == "明日、またここで会おう。"
        checks["live_google_result_visible"] = (
            bool(window.latest)
            and window.latest != window.result_source.text()
            and window.overlay.isVisible()
        )
        checks["main_remains_hidden"] = not window.isVisible()
        assert all(checks.values())
        for action in ["move", "resize"]:
            old_count = count()
            old_region = window.pipeline.capture_region
            command(action)
            wait(
                lambda before=old_count, region=old_region: (
                    count() > before and window.pipeline.capture_region != region
                )
            )
            current = inspector.info(handle)
            checks["actual_loop_follows_" + action] = (
                current is not None
                and window.pipeline.capture_region == current.client
                and window.overlay.capture_region == current.client
                and not window.isVisible()
            )
            assert checks["actual_loop_follows_" + action]
        command("minimize")
        wait(lambda: state() == SessionState.WAITING_TARGET, 20)
        checks["minimize_waits_without_main"] = not window.isVisible()
        old_count = count()
        command("restore")
        wait(lambda: count() > old_count and state() == SessionState.WATCHING)
        checks["restore_translates_again"] = not window.isVisible()
        current = inspector.info(handle)
        ratio = app.primaryScreen().devicePixelRatio()
        blocker = QWidget()
        blocker.setWindowTitle("DeskTranslate authored end-to-end occluder")
        blocker.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        blocker.setStyleSheet("background: #fe3355")
        blocker.setGeometry(
            round(current.client.x / ratio),
            round(current.client.y / ratio),
            round(current.client.width / ratio),
            round(current.client.height / ratio),
        )
        blocker.show()
        blocker.raise_()
        wait(lambda: state() == SessionState.WAITING_TARGET, 20)
        checks["occlusion_waits_without_main"] = not window.isVisible()
        old_count = count()
        blocker.close()
        wait(lambda: count() > old_count and state() == SessionState.WATCHING)
        checks["uncover_translates_again"] = not window.isVisible()
        report = {
            "version": __version__,
            "python_version": platform.python_version(),
            "source_sha256": git_trace(ROOT)["source_sha256"],
            "native_qt_platform": app.platformName(),
            "device_pixel_ratios": [screen.devicePixelRatio() for screen in app.screens()],
            "scope": "Authored separate-process window; real MainWindow, Win32/MSS capture, isolated CPU OCR and live Google; no region-picker interaction or real-game/fullscreen qualification",
            "checks": checks,
            "accepted_results": count(),
            "elapsed_s": round(time.monotonic() - started, 2),
        }
    finally:
        if blocker:
            blocker.close()
        if window:
            window.quit()
        command("quit")
        try:
            target.wait(10)
        except subprocess.TimeoutExpired:
            target.terminate()
            target.wait(10)
        deadline = time.monotonic() + 15
        while multiprocessing.active_children() and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.05)
    report["remaining_ocr_children"] = len(multiprocessing.active_children())
    report["owned_target_closed"] = target.returncode == 0
    report["passed"] = (
        all(checks.values())
        and report["remaining_ocr_children"] == 0
        and report["owned_target_closed"]
    )
    (ROOT / "docs/window-loop-qualification.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(report))
    assert report["passed"]


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
