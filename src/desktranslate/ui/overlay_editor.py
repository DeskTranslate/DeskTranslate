from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFontComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from desktranslate.settings import Settings
from desktranslate.ui.subtitles import PRESETS


class OverlayEditor(QWidget):
    def __init__(self, settings: Settings, apply: Callable[[], None]) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.controls: dict[str, Any] = {}
        row = QHBoxLayout()
        self.presets = QComboBox()
        self.presets.setAccessibleName("Subtitle appearance preset")
        self.presets.addItems(list(PRESETS))
        row.addWidget(self.presets, 1)
        preset = QPushButton("Use preset")
        preset.clicked.connect(lambda: self.use_preset(apply))
        row.addWidget(preset)
        layout.addLayout(row)
        group = QGroupBox("Customize typography and effects")
        group.setCheckable(True)
        group.setChecked(False)
        outer = QVBoxLayout(group)
        content = QWidget()
        form = QFormLayout(content)
        widget: Any
        font = QFontComboBox()
        self.controls["overlay_font"] = font
        form.addRow("Font family", font)
        for key, title, low, high in [
            ("weight", "Weight", 100, 900),
            ("text_opacity", "Text opacity %", 30, 100),
            ("source_size", "Original text size", 10, 48),
            ("background_opacity", "Background opacity %", 0, 100),
            ("gradient_angle", "Gradient direction °", 0, 360),
            ("outline_width", "Outline thickness", 0, 6),
            ("shadow_opacity", "Shadow opacity %", 0, 100),
            ("shadow_x", "Shadow horizontal offset", -12, 12),
            ("shadow_y", "Shadow vertical offset", -12, 12),
            ("line_spacing", "Line spacing %", 90, 200),
            ("letter_spacing", "Letter spacing", -2, 8),
            ("padding", "Padding", 4, 60),
            ("radius", "Corner radius", 0, 40),
            ("max_lines", "Maximum visible lines", 1, 12),
        ]:
            widget = QSpinBox()
            widget.setRange(low, high)
            widget.setAccessibleName(title)
            self.controls["overlay_" + key] = widget
            form.addRow(title, widget)
        for key, title in [
            ("color", "Translation color"),
            ("source_color", "Original color"),
            ("background", "Background start"),
            ("gradient", "Background end"),
            ("outline", "Outline color"),
        ]:
            row = QHBoxLayout()
            value = QLineEdit()
            value.setMaxLength(7)
            value.setAccessibleName(title)
            choose = QPushButton("Choose…")
            choose.setAccessibleName("Choose " + title.lower())
            choose.clicked.connect(lambda checked=False, edit=value: self.choose_color(edit))
            row.addWidget(value, 1)
            row.addWidget(choose)
            self.controls["overlay_" + key] = value
            form.addRow(title, row)
        for key, title in [
            ("overlay_italic", "Italic"),
            ("overlay_shadow", "Text shadow"),
            ("overlay_locked", "Lock position & size"),
            ("overlay_fade", "Gentle appearance fade"),
            ("reduced_motion", "Reduce motion"),
        ]:
            widget = QCheckBox(title)
            self.controls[key] = widget
            form.addRow(widget)
        for key, title, options in [
            ("overlay_alignment", "Alignment", ["left", "center", "right"]),
            ("overlay_source_position", "Original text position", ["above", "below"]),
        ]:
            widget = QComboBox()
            widget.addItems(options)
            self.controls[key] = widget
            form.addRow(title, widget)
        hint = QLabel(
            "Long output shrinks to 12 px before clipping at the line limit. Copy retains the complete translation."
        )
        hint.setWordWrap(True)
        form.addRow(hint)
        content.setVisible(False)
        group.toggled.connect(content.setVisible)
        outer.addWidget(content)
        layout.addWidget(group)
        self.sync(settings)

    def choose_color(self, edit: QLineEdit) -> None:
        color = QColorDialog.getColor(QColor(edit.text()), self, "Choose overlay color")
        if color.isValid():
            edit.setText(color.name())

    def sync(self, settings: Settings) -> None:
        for key, widget in self.controls.items():
            value = getattr(settings, key)
            if isinstance(widget, QFontComboBox):
                widget.setCurrentFont(QFont(value))
            elif isinstance(widget, QSpinBox):
                widget.setValue(value)
            elif isinstance(widget, QCheckBox):
                widget.setChecked(value)
            elif isinstance(widget, QLineEdit):
                widget.setText(value)
            else:
                widget.setCurrentText(value)

    def apply_to(self, settings: Settings) -> None:
        value: Any
        for key, widget in self.controls.items():
            if isinstance(widget, QFontComboBox):
                value = widget.currentFont().family()
            elif isinstance(widget, QSpinBox):
                value = widget.value()
            elif isinstance(widget, QCheckBox):
                value = widget.isChecked()
            elif isinstance(widget, QLineEdit):
                value = widget.text()
            else:
                value = widget.currentText()
            setattr(settings, key, value)
        settings.validate()

    def use_preset(self, apply: Callable[[], None]) -> None:
        for key, value in PRESETS[self.presets.currentText()].items():
            widget = self.controls.get(key)
            if widget is None:
                continue
            if isinstance(widget, QSpinBox):
                widget.setValue(int(str(value)))
            elif isinstance(widget, QCheckBox):
                widget.setChecked(bool(value))
            elif isinstance(widget, QLineEdit):
                widget.setText(str(value))
            else:
                widget.setCurrentText(value)
        apply()
