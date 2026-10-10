from __future__ import annotations

from PySide6.QtCore import QObject, QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainter, QPaintEvent, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QWidget

from desktranslate.capture import physical_monitors
from desktranslate.models import Monitor, Rect


class SelectionWindow(QWidget):
    accepted = Signal(object)
    cancelled = Signal()

    def __init__(self, monitor: Monitor, screenshot: QPixmap) -> None:
        super().__init__()
        self.monitor = monitor
        self.screenshot = screenshot
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        r = monitor.logical
        self.setGeometry(r.x, r.y, r.width, r.height)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.begin = QPoint()
        self.end = QPoint()
        self.dragging = False
        self.has_region = False
        self.resizing = False

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.drawPixmap(self.rect(), self.screenshot)
        painter.fillRect(self.rect(), QColor(7, 18, 22, 155))
        rect = QRect(self.begin, self.end).normalized()
        if self.has_region or self.dragging:
            painter.save()
            painter.setClipRect(rect)
            painter.drawPixmap(self.rect(), self.screenshot)
            painter.restore()
            painter.setPen(QPen(QColor("#68d8b4"), 2))
            painter.drawRect(rect)
            painter.setBrush(QColor("#68d8b4"))
            for point in (rect.topLeft(), rect.topRight(), rect.bottomLeft(), rect.bottomRight()):
                painter.drawRect(QRect(point - QPoint(4, 4), point + QPoint(4, 4)))
            physical = self.physical_rect()
            painter.drawText(
                rect.left() + 8,
                max(28, rect.top() - 14),
                f"{physical.width} × {physical.height} px",
            )
        painter.setPen(QColor("#eff6f2"))
        painter.drawText(
            28,
            self.height() - 32,
            "Drag to select · Drag a corner to resize · Enter / double-click to translate · Esc to cancel",
        )

    def physical_rect(self) -> Rect:
        r = QRect(self.begin, self.end).normalized()
        logical = Rect(
            r.x() + self.monitor.logical.x,
            r.y() + self.monitor.logical.y,
            max(1, r.width()),
            max(1, r.height()),
        )
        return self.monitor.to_physical(logical)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        point = event.position().toPoint()
        rect = QRect(self.begin, self.end).normalized()
        corners = [
            (rect.topLeft(), rect.bottomRight()),
            (rect.topRight(), rect.bottomLeft()),
            (rect.bottomLeft(), rect.topRight()),
            (rect.bottomRight(), rect.topLeft()),
        ]
        match = next(
            (
                opposite
                for corner, opposite in corners
                if self.has_region and (corner - point).manhattanLength() < 18
            ),
            None,
        )
        self.begin = match if match is not None else point
        self.end = point
        self.dragging = True
        self.has_region = False
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.dragging:
            point = event.position().toPoint()
            self.end = QPoint(
                max(0, min(self.width() - 1, point.x())), max(0, min(self.height() - 1, point.y()))
            )
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self.dragging = False
        rect = QRect(self.begin, self.end).normalized()
        self.has_region = rect.width() >= 4 and rect.height() >= 4
        self.update()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        self.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
        elif event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            self.accept()

    def accept(self) -> None:
        if self.has_region:
            self.accepted.emit(self.physical_rect())


class RegionSelector(QObject):
    selected = Signal(object)
    cancelled = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.windows: list[SelectionWindow] = []
        self.closed = False

    def start(self) -> None:
        if self.closed:
            return
        physical = physical_monitors()
        # Freeze all displays before showing any selection windows.
        screens = [(screen, screen.grabWindow(0)) for screen in QApplication.screens()]
        for screen, screenshot in screens:
            geometry = screen.geometry()
            logical = Rect(geometry.x(), geometry.y(), geometry.width(), geometry.height())
            pixels = physical.get(screen.name())
            if pixels is None:
                import os

                if os.name == "nt":
                    self.cancel()
                    return
                ratio = screen.devicePixelRatio()
                pixels = Rect(
                    round(logical.x * ratio),
                    round(logical.y * ratio),
                    round(logical.width * ratio),
                    round(logical.height * ratio),
                )
            window = SelectionWindow(Monitor(screen.name(), logical, pixels), screenshot)
            window.accepted.connect(self.finish)
            window.cancelled.connect(self.cancel)
            self.windows.append(window)
        for window in self.windows:
            window.show()
        if self.windows:
            self.windows[0].activateWindow()

    def cleanup(self) -> None:
        self.closed = True
        for window in self.windows:
            window.close()
            window.deleteLater()
        self.windows.clear()

    def finish(self, region: Rect) -> None:
        self.cleanup()
        self.selected.emit(region)

    def cancel(self) -> None:
        self.cleanup()
        self.cancelled.emit()
