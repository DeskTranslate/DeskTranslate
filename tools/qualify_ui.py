"""Opt-in native Qt scaling, keyboard and accessibility interface checks."""

from __future__ import annotations

import json
import time
from pathlib import Path

from desktranslate import __version__
from desktranslate.capture import enable_dpi_awareness


def main() -> None:
    enable_dpi_awareness()
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QAccessible
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QComboBox, QScrollArea

    from desktranslate.settings import Settings, SettingsStore
    from desktranslate.ui import theme
    from desktranslate.ui.window import MainWindow

    app = QApplication([])
    store = SettingsStore(Path(".test-data/ui-qualification"))
    store.save(Settings())
    window = MainWindow(store, demo=True)
    window.show()
    pages = []
    for index in range(window.navigation.count()):
        window.navigation.setCurrentRow(index)
        for _ in range(3):
            app.processEvents()
            time.sleep(0.02)
        scroll = window.pages.currentWidget()
        assert isinstance(scroll, QScrollArea)
        pages.append(
            {
                "page": window.navigation.item(index).text(),
                "horizontal_scroll_max": scroll.horizontalScrollBar().maximum(),
                "viewport_width": scroll.viewport().width(),
            }
        )
    window.navigation.setCurrentRow(0)
    window.source_combo.setFocus()
    app.processEvents()
    focused = set()
    for _ in range(35):
        QTest.keyClick(window, Qt.Key.Key_Tab)
        app.processEvents()
        if widget := app.focusWidget():
            focused.add(id(widget))
    controls = []
    for control in window.findChildren(QComboBox):
        interface = QAccessible.queryAccessibleInterface(control)
        controls.append(bool(interface and interface.text(QAccessible.Text.Name)))
    output = Path("docs/ui-qualification.json")
    report = {
        "version": __version__,
        "device_pixel_ratios": [screen.devicePixelRatio() for screen in app.screens()],
        "logical_window_size": [window.width(), window.height()],
        "pages": pages,
        "keyboard_focus_targets": len(focused),
        "combobox_accessible_names": {"named": sum(controls), "total": len(controls)},
        "screen_reader_tested": False,
        "physical_mixed_dpi_tested": False,
    }
    high_contrast = theme.high_contrast_enabled
    theme.high_contrast_enabled = lambda: True
    try:
        theme.apply_theme(app, "dark")
        report["high_contrast_native_style_branch"] = app.styleSheet() == ""
    finally:
        theme.high_contrast_enabled = high_contrast
    report["passed"] = (
        all(page["horizontal_scroll_max"] == 0 for page in pages)
        and len(focused) >= 8
        and all(controls)
        and report["high_contrast_native_style_branch"]
    )
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
    window.quit()
    app.processEvents()
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
