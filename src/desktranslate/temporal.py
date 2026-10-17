"""Bounded dialogue evidence across frames, independent of capture and provider IO."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from difflib import SequenceMatcher

from desktranslate.algorithms import normalize_text
from desktranslate.models import OCRResult, Rect


@dataclass(frozen=True)
class Observation:
    text: str
    confidence: float
    at: float
    bounds: Rect | None


def text_bounds(result: OCRResult) -> Rect | None:
    if not result.lines:
        return None
    left = min(line.box.x for line in result.lines)
    top = min(line.box.y for line in result.lines)
    right = max(line.box.right for line in result.lines)
    bottom = max(line.box.bottom for line in result.lines)
    return Rect(left, top, right - left, bottom - top)


def continuous(previous: Rect | None, current: Rect | None) -> bool:
    if previous is None or current is None:
        return True  # Optional engines may not supply word geometry.
    width = max(0, min(previous.right, current.right) - max(previous.x, current.x))
    height = max(0, min(previous.bottom, current.bottom) - max(previous.y, current.y))
    return (
        width * height
        >= min(previous.width * previous.height, current.width * current.height) * 0.45
    )


def small_change(left: str, right: str) -> bool:
    # Bound quadratic matching; long/new paragraphs are independent candidates.
    if not 4 <= max(len(left), len(right)) <= 256 or abs(len(left) - len(right)) > 2:
        return False
    changes = sum(
        max(i2 - i1, j2 - j1)
        for op, i1, i2, j1, j2 in SequenceMatcher(None, left, right, autojunk=False).get_opcodes()
        if op != "equal"
    )
    return changes <= max(1, min(2, len(left) // 12))


def complete_sentence(text: str) -> bool:
    return text.rstrip("\"'」』”’）) ").endswith(("。", "！", "？", "!", "?", "."))


class TemporalTextTracker:
    """Immediate complete subtitles; adaptive quiet-time for progressive dialogue.

    Pixel revisions may invalidate a request without erasing text evidence. Only
    lifecycle/region changes reset this tracker. It never invents characters:
    consensus selects an actually observed string, with consecutive confirmation
    allowing a genuine small change to replace the previous dialogue.
    """

    def __init__(self, settle: float = 0.25) -> None:
        self.settle = settle
        self.history: deque[Observation] = deque(maxlen=6)
        self.candidate = ""
        self.accepted = ""
        self.confidence = 0.0
        self.changed_at = 0.0
        self.repeated = 0
        self.growing = False
        self.needs_confirmation = False
        self.reason = "empty"
        self.replaces_source = ""

    def rebase_delivery(self, delivered: str) -> None:
        """Retry invalidated work while retaining recent recognition evidence."""
        self.accepted = delivered

    def observe(self, result: OCRResult, now: float, settled_frame: bool = False) -> str | None:
        self.replaces_source = ""
        text = normalize_text(result.text)
        bounds = text_bounds(result)
        while self.history and now - self.history[0].at > 2.5:
            self.history.popleft()
        previous = self.history[-1] if self.history else None
        connected = bool(
            previous and now - previous.at <= 1.5 and continuous(previous.bounds, bounds)
        )
        if not text:
            self.history.clear()
            self.candidate = self.accepted = ""
            self.repeated = 0
            self.growing = self.needs_confirmation = False
            self.reason = "blank"
            return None
        if not connected:
            self.history.clear()
            self.growing = False
        growth = bool(
            connected
            and previous
            and text.startswith(previous.text)
            and len(text) > len(previous.text)
        )
        if text != self.candidate:
            self.changed_at = now
            self.repeated = 1
        else:
            self.repeated += 1
        if growth:
            self.growing = True
        elif previous and text != previous.text and not small_change(text, previous.text):
            self.growing = False
        self.candidate, self.confidence = text, result.confidence
        self.history.append(Observation(text, result.confidence, now, bounds))
        agreement = sum(item.text == text for item in self.history) >= 2
        self.needs_confirmation = text != self.accepted
        if text == self.accepted:
            self.reason = "unchanged"
            self.needs_confirmation = False
            return None
        spacing_change = bool(
            self.accepted and "".join(text.split()) == "".join(self.accepted.split())
        )
        if (
            connected
            and (small_change(text, self.accepted) or spacing_change)
            and self.repeated < 2
        ):
            self.reason = "possible-noise"
            return None
        # A strong complete subtitle needs no duplicate OCR. Progressive reveal
        # waits only while characters keep arriving; the final punctuation wins
        # immediately, and a punctuation-free ending needs a short quiet period.
        quiet = now - self.changed_at >= min(0.35, max(0.12, self.settle))
        if self.growing and not complete_sentence(text) and not quiet:
            self.reason = "progressive"
            return None
        if (
            self.repeated >= 2
            or (agreement and not growth)
            or self.settle == 0
            or (settled_frame and result.confidence >= 0.85)
            or (complete_sentence(text) and result.confidence >= 0.85)
            or (result.confidence >= 0.85 and now - self.changed_at >= self.settle)
        ):
            if connected and self.growing and self.accepted and text.startswith(self.accepted):
                self.replaces_source = self.accepted
            self.accepted = text
            self.needs_confirmation = False
            self.reason = "complete" if complete_sentence(text) else "confirmed"
            return text
        self.reason = "confirming"
        return None
