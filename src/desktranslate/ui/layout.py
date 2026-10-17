"""Initial dialog bounds in Qt logical coordinates on the parent's screen."""

from PySide6.QtWidgets import QApplication, QWidget


def fit_to_screen(widget: QWidget, width: int, height: int) -> None:
    screen = widget.screen() or QApplication.primaryScreen()
    if screen is None:
        widget.resize(width, height)
        return
    bounds = screen.availableGeometry()
    widget.resize(
        max(240, min(width, bounds.width() - 40)),
        max(200, min(height, bounds.height() - 40)),
    )
