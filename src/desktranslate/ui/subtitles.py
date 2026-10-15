from __future__ import annotations

import math

from PySide6.QtCore import QEvent, QPointF, QRectF, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPaintEvent,
    QPixmap,
    QResizeEvent,
    QTextBlockFormat,
    QTextCursor,
    QTextDocument,
    QTextOption,
)
from PySide6.QtWidgets import QLabel

from desktranslate.settings import Settings


class SubtitleText(QLabel):
    """Qt shapes Unicode once per text/style/size change. Paints reuse cached glyphs."""

    def __init__(self, settings: Settings, source: bool = False) -> None:
        super().__init__()
        self.settings = settings
        self.is_source = source
        self.value = ""
        self.glyphs: QPixmap | None = None
        self.ink: QPixmap | None = None
        self.outline: QPixmap | None = None
        self.shadow: QPixmap | None = None
        self.raster_origin = QPointF()
        self.effective_size = settings.overlay_size
        self.setMinimumHeight(30)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setWordWrap(True)
        self.setAccessibleName("Original text" if source else "Translated text")

    def text(self) -> str:
        return self.value

    def setText(self, value: str) -> None:
        if value == self.value:
            return
        self.value = value
        super().setText(value)
        self.setAccessibleDescription(value)
        self.glyphs = None
        self.update()

    def configure(self, settings: Settings) -> None:
        self.settings = settings
        self.glyphs = None
        self.updateGeometry()
        self.update()

    def sizeHint(self) -> QSize:
        size = self.settings.overlay_source_size if self.is_source else self.settings.overlay_size
        return QSize(400, size * 2 if self.is_source else size * 4)

    def minimumSizeHint(self) -> QSize:
        return QSize(1, 30)

    def resizeEvent(self, event: QResizeEvent) -> None:
        self.glyphs = None
        super().resizeEvent(event)

    def event(self, event: QEvent) -> bool:
        if event.type() == QEvent.Type.DevicePixelRatioChange:
            self.glyphs = None
            self.update()
        return super().event(event)

    @staticmethod
    def tint(glyphs: QPixmap, color: str) -> QPixmap:
        output = glyphs.copy()
        painter = QPainter(output)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(output.rect(), QColor(color))
        painter.end()
        return output

    def prepare(self) -> None:
        settings = self.settings
        size = settings.overlay_source_size if self.is_source else settings.overlay_size
        margin = (
            settings.overlay_outline_width
            + max(abs(settings.overlay_shadow_x), abs(settings.overlay_shadow_y))
            + 2
        )
        width = max(1, self.width() - 2 * margin)
        height = max(1, self.height() - 2 * margin)
        document = QTextDocument()
        document.setDocumentMargin(0)
        option = QTextOption()
        option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        option.setAlignment(
            {
                "left": Qt.AlignmentFlag.AlignLeft,
                "center": Qt.AlignmentFlag.AlignHCenter,
                "right": Qt.AlignmentFlag.AlignRight,
            }[settings.overlay_alignment]
        )
        document.setDefaultTextOption(option)
        document.setUndoRedoEnabled(False)
        document.setPlainText(self.value)
        cursor = QTextCursor(document)
        cursor.select(QTextCursor.SelectionType.Document)
        char = cursor.charFormat()
        char.setForeground(QColor("white"))
        cursor.mergeCharFormat(char)
        block = QTextBlockFormat()
        block.setLineHeight(
            settings.overlay_line_spacing, QTextBlockFormat.LineHeightTypes.ProportionalHeight.value
        )
        cursor.mergeBlockFormat(block)
        document.setTextWidth(width)

        def layout_at(candidate: int) -> tuple[bool, float]:
            font = QFont(settings.overlay_font)
            font.setPixelSize(candidate)
            font.setWeight(QFont.Weight(round(settings.overlay_weight / 100) * 100))
            font.setItalic(settings.overlay_italic)
            font.setLetterSpacing(
                QFont.SpacingType.AbsoluteSpacing, settings.overlay_letter_spacing
            )
            document.setDefaultFont(font)
            allowed = min(
                height, candidate * settings.overlay_line_spacing / 100 * settings.overlay_max_lines
            )
            return document.size().height() <= allowed, allowed

        fits, allowed = layout_at(size)
        if not fits and not self.is_source:
            low, high, best = 12, size - 1, 12
            while low <= high:
                candidate = (low + high) // 2
                fits, _ = layout_at(candidate)
                if fits:
                    best, low = candidate, candidate + 1
                else:
                    high = candidate - 1
            size = best
            _, allowed = layout_at(size)
        self.effective_size = size
        visible_height = min(allowed, document.size().height())
        raster_height = min(self.height(), math.ceil(visible_height + 2 * margin))
        # Four RGBA masks share this budget. Cache only the painted text band,
        # not the entire empty overlay canvas at a large monitor scale.
        ratio = min(
            self.devicePixelRatioF(), math.sqrt(4_000_000 / max(1, self.width() * raster_height))
        )
        glyphs = QPixmap(math.ceil(self.width() * ratio), math.ceil(raster_height * ratio))
        glyphs.setDevicePixelRatio(ratio)
        glyphs.fill(Qt.GlobalColor.transparent)
        painter = QPainter(glyphs)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        y = margin + max(0, (height - visible_height) / 2)
        self.raster_origin = QPointF(0, y - margin)
        painter.translate(margin, margin)
        painter.setClipRect(QRectF(0, 0, width, allowed))
        document.drawContents(painter)
        painter.end()
        self.glyphs = glyphs
        self.ink = self.tint(
            glyphs, settings.overlay_source_color if self.is_source else settings.overlay_color
        )
        self.outline = self.tint(glyphs, settings.overlay_outline)
        self.shadow = self.tint(glyphs, "#000000")

    def paintEvent(self, event: QPaintEvent) -> None:
        if self.glyphs is None:
            self.prepare()
        painter = QPainter(self)
        settings = self.settings
        if settings.overlay_shadow and self.shadow:
            painter.setOpacity(settings.overlay_shadow_opacity / 100)
            painter.drawPixmap(
                self.raster_origin + QPointF(settings.overlay_shadow_x, settings.overlay_shadow_y),
                self.shadow,
            )
        painter.setOpacity(settings.overlay_text_opacity / 100)
        if settings.overlay_outline_width and self.outline:
            radius = settings.overlay_outline_width
            for index in range(24):
                angle = index * math.pi / 12
                painter.drawPixmap(
                    self.raster_origin
                    + QPointF(math.cos(angle) * radius, math.sin(angle) * radius),
                    self.outline,
                )
        if self.ink:
            painter.drawPixmap(self.raster_origin, self.ink)
        painter.end()


PRESETS: dict[str, dict[str, object]] = {
    "Midnight mint": {
        "overlay_background": "#13262e",
        "overlay_gradient": "#24473e",
        "overlay_color": "#f5faf7",
        "overlay_background_opacity": 92,
        "overlay_outline_width": 1,
        "overlay_size": 22,
    },
    "Anime subtitles": {
        "overlay_background_opacity": 0,
        "overlay_color": "#ffffff",
        "overlay_outline": "#000000",
        "overlay_outline_width": 3,
        "overlay_size": 30,
        "overlay_alignment": "center",
        "overlay_shadow": True,
    },
    "Cinematic": {
        "overlay_background": "#090d15",
        "overlay_gradient": "#090d15",
        "overlay_background_opacity": 70,
        "overlay_color": "#fff3d6",
        "overlay_outline_width": 1,
        "overlay_size": 28,
        "overlay_alignment": "center",
    },
    "Paper & ink": {
        "overlay_background": "#f7fbf8",
        "overlay_gradient": "#e3f2ec",
        "overlay_background_opacity": 96,
        "overlay_color": "#162b32",
        "overlay_source_color": "#345e59",
        "overlay_outline_width": 0,
        "overlay_shadow": False,
    },
    "High contrast": {
        "overlay_background": "#000000",
        "overlay_gradient": "#000000",
        "overlay_color": "#ffffff",
        "overlay_background_opacity": 100,
        "overlay_outline_width": 0,
        "overlay_size": 32,
        "overlay_weight": 700,
    },
}
