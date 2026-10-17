"""Authored text-only fixtures. System fonts are rendered, never redistributed."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QFontMetrics,
    QImage,
    QLinearGradient,
    QPainter,
    QPen,
    QTextCursor,
    QTextDocument,
)
from PySide6.QtWidgets import QApplication

SETUP_TEXT = {
    "fr": "Sélectionnez une région à traduire.",
    "de": "Wähle einen Bereich zum Übersetzen.",
    "it": "Seleziona una regione da tradurre.",
    "pt": "Selecione uma região para traduzir.",
    "nl": "Selecteer een gebied om te vertalen.",
    "pl": "Wybierz obszar do tłumaczenia.",
    "vi": "Chọn một vùng để dịch.",
    "id": "Pilih wilayah untuk diterjemahkan.",
    "tr": "Çevirmek için bir alan seçin.",
    "ru": "Выберите область для перевода.",
    "uk": "Виберіть область для перекладу.",
    "ar": "مرحبا بالعالم",
    "hi": "नमस्ते दुनिया",
}
EXTRA_SAMPLES = [
    {
        "id": code + "-setup",
        "language": code,
        "text": text,
        "render": "qt",
        "size": 32,
        "bg": "#172736",
        "fg": "white",
    }
    for code, text in SETUP_TEXT.items()
] + [
    {
        "id": "ar-mixed-digits",
        "language": "ar",
        "text": "مرحبا مريم 42\nHP 120 / MP 45",
        "size": 32,
    },
    {
        "id": "ar-multiline",
        "language": "ar",
        "text": "مرحبا بالعالم\nنلتقي غدا",
        "size": 32,
        "shadow": True,
    },
    {
        "id": "ja-vertical-dialogue",
        "language": "ja",
        "text": "この町の\n名前を\n覚えている",
        "vertical": True,
        "size": 30,
    },
    {
        "id": "ja-vertical",
        "language": "ja",
        "text": "明日また\n会おう",
        "vertical": True,
        "size": 32,
    },
    {
        "id": "ja-katakana-pixel",
        "language": "ja",
        "text": "ドラゴンの城へ行こう！",
        "size": 24,
        "pixelated": True,
    },
    {
        "id": "ja-mixed-names",
        "language": "ja",
        "text": "ミカ：HP 120 / MP 45\nレベル 7 — QUEST 03",
        "size": 30,
        "gradient": True,
    },
    {
        "id": "en-large-shadow",
        "language": "en",
        "text": "Mika, wait! 42 seconds.",
        "size": 42,
        "shadow": True,
        "gradient": True,
    },
    {
        "id": "en-low-contrast",
        "language": "en",
        "text": "The gate opens at 07:30.",
        "size": 22,
        "bg": "#65757e",
        "fg": "#8b999f",
    },
    {
        "id": "en-translucent",
        "language": "en",
        "text": "We can meet tomorrow.",
        "size": 26,
        "alpha": 170,
        "gradient": True,
    },
    {
        "id": "es-punctuation",
        "language": "es",
        "text": "¿Dónde está Lucía? ¡Aquí! 2026.",
        "size": 30,
        "outline": True,
        "gradient": True,
    },
    {
        "id": "zh-punctuation",
        "language": "zh-CN",
        "text": "你好，明天见！\n时间：12:30。",
        "size": 32,
        "outline": True,
    },
    {
        "id": "zh-traditional-characters",
        "language": "zh-TW",
        "text": "這裡的門還沒開。\n請記住我們的名字！",
        "size": 32,
        "gradient": True,
    },
    {
        "id": "ko-multiline-shadow",
        "language": "ko",
        "text": "미카, 문이 열렸어요!\n내일 오후 3시에 만나요.",
        "size": 30,
        "shadow": True,
    },
]
EXTRA_SAMPLES += [
    {
        "id": "ja-region-outline",
        "language": "ja",
        "text": "ミカ、鍵を見つけた？",
        "size": 24,
        "outline": True,
        "gradient": True,
    },
    {
        "id": "ja-region-translucent",
        "language": "ja",
        "text": "彼女の名前はアウレリア。",
        "size": 26,
        "alpha": 170,
        "gradient": True,
    },
    {
        "id": "ja-region-low-contrast",
        "language": "ja",
        "text": "明日の朝に出発します。",
        "size": 22,
        "bg": "#65757e",
        "fg": "#8b999f",
    },
    {
        "id": "ja-region-small",
        "language": "ja",
        "text": "魔導炉の出力は120です。",
        "size": 14,
        "gradient": True,
    },
    {
        "id": "ja-region-counter",
        "language": "ja",
        "text": "ミカ：HP 120 / MP 45",
        "size": 26,
        "shadow": True,
    },
    {
        "id": "ja-region-punctuation",
        "language": "ja",
        "text": "「えっ、もう終わり？」",
        "size": 32,
        "bg": "white",
        "fg": "black",
    },
    {
        "id": "ja-columns-names",
        "language": "ja",
        "text": "アルトリア\n魔導炉",
        "size": 30,
        "vertical": True,
    },
    {
        "id": "ja-columns-kanji",
        "language": "ja",
        "text": "約束を\n忘れないで",
        "size": 28,
        "vertical": True,
    },
    {
        "id": "ja-columns-small",
        "language": "ja",
        "text": "この世界\n明日の光",
        "size": 20,
        "vertical": True,
    },
    {
        "id": "ja-columns-light",
        "language": "ja",
        "text": "時間を\n覚えている",
        "size": 30,
        "vertical": True,
        "bg": "#f6f7f1",
        "fg": "#111e25",
    },
    {
        "id": "ja-columns-mixed",
        "language": "ja",
        "text": "ミカ：待って！\nアルトリア\n魔導炉",
        "columns": ["アルトリア", "魔導炉"],
        "caption": "ミカ：待って！",
        "size": 30,
        "vertical": True,
    },
    {
        "id": "ja-columns-ruby",
        "language": "ja",
        "text": "魔導炉\n明日の光",
        "ruby": "まどうろ",
        "size": 30,
        "vertical": True,
    },
]
for sample in EXTRA_SAMPLES:
    sample.setdefault("render", "qt")
    sample.setdefault("bg", "#172736")
    sample.setdefault("fg", "white")

FIXTURE_APP: QApplication | None = None


def render_fixture(sample: dict, destination: Path) -> None:
    global FIXTURE_APP
    if FIXTURE_APP is None:
        FIXTURE_APP = QApplication.instance() or QApplication([])  # type: ignore[assignment]
        # The Qt offscreen plugin has no Windows system font database. Load
        # explicit OS fonts so test assets contain real text rather than tofu.
        for filename in (
            "segoeui.ttf",
            "YuGothM.ttc",
            "malgun.ttf",
            "msyh.ttc",
            "msjh.ttc",
            "Nirmala.ttf",
            "tahoma.ttf",
        ):
            QFontDatabase.addApplicationFont(str(Path("C:/Windows/Fonts") / filename))
    image = QImage(660, 260 if sample.get("vertical") else 160, QImage.Format.Format_RGB32)
    image.fill(QColor(sample["bg"]))
    painter = QPainter(image)
    if sample.get("gradient"):
        gradient = QLinearGradient(0, 0, 660, 160)
        gradient.setColorAt(0, QColor("#879c74"))
        gradient.setColorAt(0.5, QColor("#294158"))
        gradient.setColorAt(1, QColor("#dda262"))
        painter.fillRect(image.rect(), gradient)
        for x in range(int(sample.get("background_phase", 0)) % 35, 660, 35):
            painter.fillRect(QRectF(x, 0, 8, 160), QColor(240, 160, 80, 35))
    font = QFont(
        {
            "ja": "Yu Gothic",
            "ko": "Malgun Gothic",
            "zh-CN": "Microsoft YaHei",
            "zh-TW": "Microsoft JhengHei",
            "hi": "Nirmala UI",
            "ar": "Tahoma",
        }.get(sample["language"], "Segoe UI")
    )
    font.setPixelSize(sample["size"])
    metrics = QFontMetrics(font)
    if any(
        not character.isspace() and not metrics.inFontUcs4(ord(character))
        for character in sample["text"]
    ):
        raise RuntimeError(
            f"Fixture font lacks glyphs for {sample['id']}; do not publish an invalid corpus"
        )
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    painter.translate(int(sample.get("offset_x", 0)), int(sample.get("offset_y", 0)))
    if sample.get("vertical"):
        painter.setFont(font)
        painter.setPen(QColor(sample["fg"]))
        for column, text in enumerate(sample.get("columns", sample["text"].splitlines())):
            for row, character in enumerate(text):
                painter.drawText(QPointF(420 - column * 60 + row % 2, 50 + row * 43), character)
        if caption := sample.get("caption"):
            caption_font = QFont(font)
            caption_font.setPixelSize(22)
            painter.setFont(caption_font)
            painter.drawText(QPointF(24, 24), caption)
        if ruby := sample.get("ruby"):
            ruby_font = QFont(font)
            ruby_font.setPixelSize(12)
            if any(not QFontMetrics(ruby_font).inFontUcs4(ord(character)) for character in ruby):
                raise RuntimeError("Fixture ruby font lacks glyphs")
            painter.setFont(ruby_font)
            for index, character in enumerate(ruby):
                painter.drawText(QPointF(452, 40 + index * 18), character)
    else:
        document = QTextDocument()
        document.setDocumentMargin(0)
        document.setDefaultFont(font)
        document.setPlainText(sample["text"])
        document.setTextWidth(612)
        cursor = QTextCursor(document)
        cursor.select(QTextCursor.SelectionType.Document)
        ink = QColor(sample["fg"])
        ink.setAlpha(sample.get("alpha", 255))
        style = cursor.charFormat()
        if sample.get("shadow"):
            style.setForeground(QColor("#080b0f"))
            cursor.mergeCharFormat(style)
            painter.save()
            painter.translate(27, 43)
            document.drawContents(painter)
            painter.restore()
        style.setForeground(ink)
        if sample.get("outline"):
            style.setTextOutline(QPen(QColor("black"), 2))
        cursor.mergeCharFormat(style)
        painter.translate(24, 40)
        document.drawContents(painter)
    painter.end()
    if sample.get("pixelated"):
        image = image.scaled(
            330, 80, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation
        ).scaled(
            660, 160, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation
        )
    if not image.save(str(destination)):
        raise OSError("Could not write authored fixture")
    assert FIXTURE_APP is not None
