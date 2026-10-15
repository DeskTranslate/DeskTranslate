"""Real picker event/transform logic on authored pixmaps, never a desktop grab."""

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from desktranslate.models import Monitor, Rect
from desktranslate.ui.selection import RegionSelector, SelectionWindow

pytestmark = pytest.mark.headless_ui


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def picker(app):
    assert app.platformName() == "offscreen"
    monitor = Monitor(
        "authored negative monitor", Rect(-800, -450, 800, 450), Rect(-1600, -900, 1600, 900)
    )
    authored = QPixmap(800, 450)
    authored.fill(QColor("#14262e"))
    controller = RegionSelector()
    window = SelectionWindow(monitor, authored)
    window.accepted.connect(controller.finish)
    window.cancelled.connect(controller.cancel)
    controller.windows.append(window)
    window.show()
    app.processEvents()
    return controller, window


def test_picker_drag_corner_resize_and_enter_use_physical_negative_coordinates(app):
    controller, window = picker(app)
    accepted = []
    controller.selected.connect(accepted.append)
    try:
        QTest.mousePress(window, Qt.MouseButton.LeftButton, pos=QPoint(40, 60))
        QTest.mouseMove(window, QPoint(240, 160))
        QTest.mouseRelease(window, Qt.MouseButton.LeftButton, pos=QPoint(240, 160))
        assert window.has_region
        assert window.physical_rect() == Rect(-1520, -780, 402, 202)
        QTest.mousePress(window, Qt.MouseButton.LeftButton, pos=QPoint(240, 160))
        QTest.mouseMove(window, QPoint(280, 200))
        QTest.mouseRelease(window, Qt.MouseButton.LeftButton, pos=QPoint(280, 200))
        QTest.keyClick(window, Qt.Key.Key_Return)
        assert accepted == [Rect(-1520, -780, 482, 282)]
        assert controller.closed and not controller.windows
    finally:
        controller.cleanup()
        app.processEvents()


def test_picker_escape_cleans_up_without_capture_or_input_hooks(app):
    controller, window = picker(app)
    cancelled, accepted = [], []
    controller.cancelled.connect(lambda: cancelled.append(True))
    controller.selected.connect(accepted.append)
    try:
        QTest.keyClick(window, Qt.Key.Key_Escape)
        assert cancelled == [True] and not accepted
        assert controller.closed and not controller.windows
    finally:
        controller.cleanup()
        app.processEvents()
