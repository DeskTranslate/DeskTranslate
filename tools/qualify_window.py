"""Opt-in native capture qualification over authored solid-color windows only."""

from __future__ import annotations

import json
import time
from pathlib import Path

from desktranslate import __version__
from desktranslate.capture import enable_dpi_awareness
from desktranslate.errors import TargetUnavailableError
from desktranslate.window_capture import Win32Windows, WindowCapture, project_region


def main() -> None:
    enable_dpi_awareness()
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QWidget

    app = QApplication([])
    inspector = Win32Windows(include_own=True)
    checks: dict[str, bool] = {}
    widgets: list[QWidget] = []

    def settle() -> None:
        for _ in range(12):
            app.processEvents()
            time.sleep(0.025)

    def target() -> QWidget:
        widget = QWidget()
        widget.setWindowTitle("DeskTranslate authored capture qualification")
        widget.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)
        widget.setStyleSheet("background: #26bfa3")
        widget.setGeometry(90, 90, 380, 200)
        widget.show()
        widget.raise_()
        widgets.append(widget)
        settle()
        return widget

    first = target()
    info = inspector.info(int(first.winId()))
    if info is None:
        raise RuntimeError("Native synthetic window could not be inspected")
    relative = [0.15, 0.25, 0.7, 0.5]
    capture = WindowCapture(info.binding(), relative, inspector=inspector)
    reconnect = WindowCapture(info.binding(), relative, follow_restart=True, inspector=inspector)

    def pixels(name: str, reader: WindowCapture = capture) -> None:
        current = inspector.info(int(widgets[-1].winId()))
        assert current is not None
        region = project_region(current.client, relative)
        image = reader.capture(region)
        checks[name] = (
            image.getpixel((image.width // 2, image.height // 2)) == (38, 191, 163)
            and reader.region == region
        )

    def rejected(name: str, reader: WindowCapture = capture) -> None:
        try:
            reader.capture(info.client)
        except TargetUnavailableError:
            checks[name] = True
        else:
            checks[name] = False

    try:
        pixels("initial_client_crop")
        reconnect.capture(info.client)
        first.move(260, 180)
        settle()
        pixels("follows_move")
        first.resize(470, 280)
        settle()
        pixels("follows_resize")
        first.showMinimized()
        settle()
        rejected("minimized_rejected")
        first.showNormal()
        first.raise_()
        settle()
        pixels("restore_recovers")
        blocker = QWidget()
        blocker.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)
        blocker.setWindowTitle("DeskTranslate authored occluder")
        blocker.setStyleSheet("background: #fe3355")
        blocker.setGeometry(first.geometry())
        blocker.show()
        blocker.raise_()
        settle()
        rejected("occlusion_rejected_before_pixels")
        blocker.close()
        settle()
        first.close()
        settle()
        rejected("closed_rejected")
        replacement = target()
        rejected("replacement_requires_consent")
        pixels("explicit_reconnect_recovers", reconnect)
        replacement.close()
        settle()
        second = target()
        duplicate = target()
        rejected("ambiguous_reconnect_rejected", reconnect)
        second.close()
        duplicate.close()
    finally:
        capture.close()
        reconnect.close()
        for widget in widgets:
            widget.close()
        settle()
    report = {
        "version": __version__,
        "synthetic_windows_only": True,
        "device_pixel_ratios": [screen.devicePixelRatio() for screen in app.screens()],
        "checks": checks,
        "passed": all(checks.values()),
    }
    output = Path("docs/window-qualification.json")
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
