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
    from PySide6.QtWidgets import QApplication, QComboBox, QScrollArea, QWizard

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
    window.onboarding()
    wizard = window.setup_dialog
    app.processEvents()
    initial_size = [wizard.width(), wizard.height()]
    available = wizard.screen().availableGeometry()
    initial_fits = available.contains(wizard.frameGeometry())
    wizard.resize(560, 320)
    setup_pages = []
    for _ in range(6):
        app.processEvents()
        page = wizard.currentPage()
        assert page is not None
        buttons_fit = all(
            not wizard.button(identifier).isVisible()
            or wizard.rect().contains(
                wizard.button(identifier).mapTo(
                    wizard, wizard.button(identifier).rect().bottomRight()
                )
            )
            for identifier in (
                QWizard.WizardButton.NextButton,
                QWizard.WizardButton.FinishButton,
                QWizard.WizardButton.CancelButton,
                QWizard.WizardButton.CustomButton1,
            )
        )
        setup_pages.append(
            {
                "page": wizard.currentId(),
                "logical_size": [wizard.width(), wizard.height()],
                "horizontal_scroll_max": page.scroll_area.horizontalScrollBar().maximum(),
                "buttons_fit": buttons_fit,
            }
        )
        # Layout-only inspection; this does not perform or complete onboarding.
        page.set_ready(True)
        wizard.next()
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
        "setup_layout_only": {
            "initial_size": initial_size,
            "initial_frame_fits": initial_fits,
            "pages": setup_pages,
            "successful_translation_tested": False,
        },
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
        and initial_fits
        and all(
            page["horizontal_scroll_max"] == 0
            and page["buttons_fit"]
            and page["logical_size"] == [560, 320]
            for page in setup_pages
        )
    )
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
    wizard.reject()
    window.quit()
    app.processEvents()
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
