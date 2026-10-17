"""Region geometry and reading order; no image engine, Qt or persistence."""

from __future__ import annotations

from desktranslate.algorithms import reconstruct
from desktranslate.models import OCRLine, Rect


def intersection_area(left: Rect, right: Rect) -> int:
    return max(0, min(left.right, right.right) - max(left.x, right.x)) * max(
        0, min(left.bottom, right.bottom) - max(left.y, right.y)
    )


def from_counterclockwise(box: Rect, width: int, height: int) -> Rect | None:
    """Map a half-open ROI from a 90° CCW image back to the original pixels."""
    left, top = max(0, width - box.bottom), max(0, box.x)
    right, bottom = min(width, width - box.y), min(height, box.right)
    return Rect(left, top, right - left, bottom - top) if right > left and bottom > top else None


def uncovered_lines(lines: tuple[OCRLine, ...], columns: tuple[Rect, ...]) -> tuple[OCRLine, ...]:
    # Original detection may join same-height glyphs across multiple columns.
    # A second orientation's actual column ROIs own those overlapping pixels.
    return tuple(
        line
        for line in lines
        if sum(intersection_area(line.box, column) for column in columns)
        < line.box.width * line.box.height * 0.35
    )


def is_kana(text: str) -> bool:
    return bool(text) and all("\u3040" <= character <= "\u30ff" for character in text)


def has_kanji(text: str) -> bool:
    return any("\u3400" <= character <= "\u9fff" for character in text)


def japanese_word_region(line: OCRLine) -> bool:
    """Select longer Japanese text crops; retain the original path for short
    text, counters and shape-like single-glyph detections. This selects a model,
    never filters a line out of the recognition result.
    """
    return (
        len("".join(line.text.split())) >= 4
        and line.box.width >= line.box.height * 2
        and sum("\u3040" <= c <= "\u30ff" or "\u3400" <= c <= "\u9fff" for c in line.text) >= 2
    )


def resolve_layout(
    horizontal: tuple[OCRLine, ...], columns: tuple[OCRLine, ...]
) -> tuple[str, tuple[OCRLine, ...], tuple[OCRLine, ...]]:
    """Keep nearby narrow kana readings as annotations rather than duplicate speech.

    Size alone never removes text. A reading must be kana beside a larger kanji
    column, with most of its height aligned. Numbers, Latin and distant small
    columns remain body text. This deliberately does not infer every ruby style.
    """
    annotations = tuple(
        line
        for line in columns
        if is_kana(line.text)
        and any(
            has_kanji(other.text)
            and other.box.width >= line.box.width * 1.8
            and 0 <= line.box.x - other.box.right <= other.box.width * 0.75
            and min(line.box.bottom, other.box.bottom) - max(line.box.y, other.box.y)
            >= line.box.height * 0.7
            for other in columns
            if other is not line
        )
    )
    body = tuple(line for line in columns if line not in annotations)
    if not body:
        return reconstruct(horizontal), horizontal, annotations
    top = min(line.box.y for line in body)
    before = tuple(line for line in horizontal if line.box.y < top)
    after = tuple(line for line in horizontal if line not in before)
    text = "\n".join(
        part
        for part in (reconstruct(before), reconstruct(body, vertical=True), reconstruct(after))
        if part
    )
    return text, before + body + after, annotations
