import math

from PySide6.QtCore import QPoint, QPointF, QPropertyAnimation, Qt, Signal
from PySide6.QtGui import QColor, QLinearGradient, QMouseEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizeGrip,
    QVBoxLayout,
    QWidget,
)

from desktranslate.capture import physical_monitors
from desktranslate.models import Monitor, Rect
from desktranslate.settings import Settings
from desktranslate.ui.subtitles import SubtitleText


class Overlay(QWidget):
    pause_requested = Signal()
    geometry_changed = Signal(object)
    edit_requested = Signal()

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.settings = settings
        self.drag: QPoint | None = None
        self.latest = ""
        self.capture_region: Rect | None = None
        self.suppressed = False
        self.user_hidden = False
        self.editing = False
        self.presentation = ""
        self.setWindowTitle("DeskTranslate · translation")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(720, 210)
        self.setMinimumSize(280, 110)
        self.setMaximumSize(3840, 2160)
        layout = QVBoxLayout(self)
        self.layout_box = layout
        layout.setContentsMargins(22, 14, 22, 14)
        row = QHBoxLayout()
        self.status = QLabel("DESKTRANSLATE  /  READY")
        row.addWidget(self.status)
        row.addStretch()
        self.pause_button = QPushButton("Pause")
        self.pause_button.clicked.connect(self.pause_requested)
        row.addWidget(self.pause_button)
        copy = QPushButton("Copy")
        copy.clicked.connect(self.copy)
        row.addWidget(copy)
        hide = QPushButton("Hide")
        hide.clicked.connect(self.hide_by_user)
        row.addWidget(hide)
        edit = QPushButton("Edit")
        edit.clicked.connect(self.edit_requested)
        row.addWidget(edit)
        layout.addLayout(row)
        self.source = SubtitleText(settings, source=True)
        layout.addWidget(self.source)
        self.translation = SubtitleText(settings)
        self.translation.setText("Your translation appears here.")
        layout.addWidget(self.translation, 1)
        self.grip = QSizeGrip(self)
        layout.addWidget(self.grip, alignment=Qt.AlignmentFlag.AlignRight)
        self.fade = QPropertyAnimation(self, b"windowOpacity", self)
        self.configure(settings)
        self.place()

    def place(self) -> None:
        if self.settings.overlay_geometry:
            x, y, width, height = self.settings.overlay_geometry
            for display in QApplication.screens():
                bounds = display.availableGeometry()
                if bounds.contains(QPoint(x, y)):
                    width, height = min(width, bounds.width()), min(height, bounds.height())
                    x = min(x, bounds.right() - width + 1)
                    y = min(y, bounds.bottom() - height + 1)
                    self.setGeometry(x, y, width, height)
                    return
        screen = QApplication.primaryScreen().availableGeometry()
        self.resize(
            min(self.width(), screen.width() - 20), min(self.height(), screen.height() - 20)
        )
        self.move(screen.center().x() - self.width() // 2, screen.bottom() - self.height() - 40)

    def configure(self, settings: Settings) -> None:
        was_visible = self.isVisible()
        if settings.overlay_mode != self.presentation:
            if settings.overlay_mode == "compact":
                self.resize(480, 130)
            elif settings.overlay_mode == "subtitle":
                self.resize(880, 150)
            elif self.presentation in {"compact", "subtitle"}:
                self.resize(720, 210)
            self.presentation = settings.overlay_mode
        self.settings = settings
        self.setWindowOpacity(settings.overlay_opacity / 100)
        self.setWindowFlag(
            Qt.WindowType.WindowTransparentForInput,
            settings.overlay_click_through and not self.editing,
        )
        self.source.setVisible(settings.overlay_mode == "bilingual")
        self.layout_box.setContentsMargins(
            settings.overlay_padding, 12, settings.overlay_padding, 10
        )
        self.layout_box.removeWidget(self.source)
        self.layout_box.insertWidget(
            1 if settings.overlay_source_position == "above" else 2, self.source
        )
        self.grip.setVisible(not settings.overlay_locked or self.editing)
        self.setStyleSheet("""
            QLabel { color: #f5faf7; background: transparent; }
            QPushButton { background: #233b42; color: #d2e9e2; padding: 5px 9px; border: none; }
        """)
        self.translation.configure(settings)
        self.source.configure(settings)
        self.status.setStyleSheet("color: #68d8b4; font-size: 10px; font-weight: 600;")
        if was_visible and not self.user_hidden and not self.suppressed:
            self.show()

    def display(self, source: str, translation: str) -> None:
        changed = translation != self.latest
        self.source.setText(source)
        self.translation.setText(translation)
        self.latest = translation
        if not self.suppressed and not self.user_hidden:
            appearing = not self.isVisible()
            self.show()
            if (
                changed
                and appearing
                and self.settings.overlay_fade
                and not self.settings.reduced_motion
            ):
                self.fade.stop()
                self.fade.setDuration(120)
                self.fade.setStartValue(0.0)
                self.fade.setEndValue(self.settings.overlay_opacity / 100)
                self.fade.start()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        angle = math.radians(self.settings.overlay_gradient_angle)
        center = QPointF(self.width() / 2, self.height() / 2)
        direction = QPointF(math.cos(angle) * self.width() / 2, math.sin(angle) * self.height() / 2)
        gradient = QLinearGradient(center - direction, center + direction)
        for point, color in (
            (0, self.settings.overlay_background),
            (1, self.settings.overlay_gradient),
        ):
            ink = QColor(color)
            ink.setAlphaF(self.settings.overlay_background_opacity / 100)
            gradient.setColorAt(point, ink)
        painter.setPen(QColor("#50746a"))
        painter.setBrush(gradient)
        painter.drawRoundedRect(
            self.rect().adjusted(1, 1, -1, -1),
            self.settings.overlay_radius,
            self.settings.overlay_radius,
        )
        painter.end()

    def toggle_edit(self) -> None:
        self.editing = not self.editing
        self.configure(self.settings)
        self.status.setText(
            "DESKTRANSLATE  /  EDIT OVERLAY" if self.editing else "DESKTRANSLATE  /  READY"
        )
        self.show()
        self.user_hidden = False

    def hide_by_user(self) -> None:
        self.user_hidden = True
        self.fade.stop()
        self.hide()

    def toggle_visibility(self) -> None:
        self.user_hidden = self.isVisible()
        if self.user_hidden:
            self.hide()
        elif not self.suppressed:
            self.show()

    def anchor(self, position: str) -> None:
        bounds = (self.screen() or QApplication.primaryScreen()).availableGeometry()
        if position == "reset":
            self.resize(min(720, bounds.width() - 40), 210)
            position = "bottom"
        x = bounds.center().x() - self.width() // 2
        y = bounds.top() + 24 if position == "top" else bounds.bottom() - self.height() - 24
        self.move(x, y)
        if self.capture_region:
            self.avoid_capture(self.capture_region)
        r = self.geometry()
        self.geometry_changed.emit([r.x(), r.y(), r.width(), r.height()])

    def avoid_capture(self, region: Rect) -> bool:
        """Keep the overlay outside OCR pixels, including after a user drags it."""
        self.capture_region = region
        physical = physical_monitors()
        for screen in QApplication.screens():
            bounds = screen.geometry()
            pixels = physical.get(screen.name())
            if pixels is None:
                import os

                if os.name == "nt":
                    # A mismatched monitor origin is unsafe, especially at mixed DPI.
                    continue
                ratio = screen.devicePixelRatio()
                pixels = Rect(
                    round(bounds.x() * ratio),
                    round(bounds.y() * ratio),
                    round(bounds.width() * ratio),
                    round(bounds.height() * ratio),
                )
            monitor = Monitor(
                screen.name(), Rect(bounds.x(), bounds.y(), bounds.width(), bounds.height()), pixels
            )
            candidates = [
                (self.x(), self.y()),
                (bounds.left() + 20, bounds.top() + 20),
                (bounds.right() - self.width() - 20, bounds.top() + 20),
                (bounds.left() + 20, bounds.bottom() - self.height() - 20),
                (bounds.right() - self.width() - 20, bounds.bottom() - self.height() - 20),
            ]
            for x, y in candidates:
                logical = Rect(x, y, self.width(), self.height())
                if monitor.logical.contains(logical) and not monitor.to_physical(
                    logical
                ).intersects(region):
                    self.move(x, y)
                    self.suppressed = False
                    return True
        self.suppressed = True
        self.hide()
        return False

    def copy(self) -> None:
        QApplication.clipboard().setText(self.latest)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and (
            self.editing or not self.settings.overlay_locked
        ):
            self.drag = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.drag is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self.drag = None
        if self.capture_region:
            self.avoid_capture(self.capture_region)
        r = self.geometry()
        self.geometry_changed.emit([r.x(), r.y(), r.width(), r.height()])
