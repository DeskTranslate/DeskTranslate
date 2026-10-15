from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

from PIL import Image, ImageChops, ImageEnhance, ImageStat

from desktranslate.errors import ConfigurationError
from desktranslate.models import OCRLine, OCRResult


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(
        re.sub(r"[^\S\n]+", " ", line).strip() for line in text.split("\n") if line.strip()
    )


def reconstruct(lines: tuple[OCRLine, ...], vertical: bool = False, direction: str = "ltr") -> str:
    if vertical:
        columns: list[list[OCRLine]] = []
        for line in sorted(lines, key=lambda line: -(line.box.x + line.box.width / 2)):
            center = line.box.x + line.box.width / 2
            column = next(
                (
                    column
                    for column in columns
                    if abs(center - (column[0].box.x + column[0].box.width / 2))
                    <= min(line.box.width, column[0].box.width) * 0.5
                ),
                None,
            )
            if column is None:
                columns.append([line])
            else:
                column.append(line)
        ordered = [
            line for column in columns for line in sorted(column, key=lambda line: line.box.y)
        ]
        return normalize_text("\n".join(line.text for line in ordered))
    rows: list[list[OCRLine]] = []
    for line in sorted(lines, key=lambda line: (line.box.y + line.box.height / 2, line.box.x)):
        center = line.box.y + line.box.height / 2
        row = next(
            (
                r
                for r in rows
                if abs(center - (r[0].box.y + r[0].box.height / 2))
                <= min(line.box.height, r[0].box.height) * 0.5
            ),
            None,
        )
        if row is None:
            rows.append([line])
        else:
            row.append(line)
    return normalize_text(
        "\n".join(
            " ".join(
                line.text
                for line in sorted(
                    row,
                    key=lambda line: line.box.x,
                    reverse=direction == "rtl"
                    and any(
                        unicodedata.bidirectional(character) in {"R", "AL"}
                        for item in row
                        for character in item.text
                    ),
                )
            )
            for row in rows
        )
    )


def preprocess(image: Image.Image, mode: str) -> Image.Image:
    if mode == "original":
        return image
    # User-selectable variants: thresholding is deliberately absent from the default path.
    enhanced = ImageEnhance.Contrast(image).enhance(1.5)
    if mode == "subtitle":
        if image.width * image.height > 10_000_000 or max(image.size) > 8192:
            raise ConfigurationError(
                "This area is too large for subtitle enlargement. Select a tighter region or use Original colors."
            )
        enhanced = enhanced.resize((image.width * 2, image.height * 2), Image.Resampling.LANCZOS)
    return enhanced


@dataclass(frozen=True)
class QualityPreset:
    cadence: float
    frame_settle: float
    text_settle: float
    idle_cadence: float


PRESETS = {
    "fast": QualityPreset(0.15, 0.15, 0.0, 0.30),
    "balanced": QualityPreset(0.20, 0.30, 0.25, 0.50),
    "accuracy": QualityPreset(0.30, 0.50, 0.50, 0.80),
}


@dataclass(frozen=True)
class FrameDecision:
    changed: bool
    ready: bool
    moving: bool = False


class FrameGate:
    def __init__(
        self, settle: float = 0.3, threshold: float = 1.2, motion_interval: float = 0.0
    ) -> None:
        self.settle = settle
        self.threshold = threshold
        self.candidate: Image.Image | None = None
        self.since = 0.0
        self.emitted = False
        self.motion_interval = motion_interval
        self.unstable_since: float | None = None
        self.last_sample = float("-inf")
        self.moving = False

    def observe(self, image: Image.Image, now: float) -> FrameDecision:
        # The thumbnail retains aspect ratio, reducing work to at most ~32K pixels.
        sample = image.convert("L")
        sample.thumbnail((256, 128))
        changed = self.candidate is None or sample.size != self.candidate.size
        if not changed and self.candidate is not None:
            diff = ImageChops.difference(sample, self.candidate)
            stats = ImageStat.Stat(diff)
            # Mean alone misses a changed short subtitle in a large crop.
            histogram = diff.histogram()
            significant = sum(histogram[20:]) / (sample.width * sample.height)
            changed = stats.mean[0] > self.threshold or significant > 0.008
        if changed:
            if self.unstable_since is None:
                self.unstable_since = now
            self.candidate = sample
            self.since = now
            self.emitted = False
        quiet = now - self.since >= self.settle
        ready = quiet and (not self.emitted or self.moving)
        if quiet:
            self.moving = False
            self.unstable_since = None
        elif (
            self.motion_interval
            and self.unstable_since is not None
            and now - self.unstable_since >= self.motion_interval
        ):
            self.moving = True
            ready = now - self.last_sample >= self.motion_interval
        if ready:
            self.emitted = True
            self.last_sample = now
        return FrameDecision(changed, ready, self.moving)


class TextStabilizer:
    def __init__(self, settle: float = 0.25) -> None:
        self.settle = settle
        self.candidate = ""
        self.since = 0.0
        self.count = 0
        self.accepted = ""
        self.confidence = 0.0

    def observe(self, result: OCRResult, now: float, settled_frame: bool = False) -> str | None:
        text = normalize_text(result.text)
        if not text:
            self.candidate = ""
            self.count = 0
            self.accepted = ""
            return None
        if text != self.candidate:
            similar = (
                self.candidate != self.accepted
                and SequenceMatcher(None, text, self.candidate).ratio() >= 0.94
            )
            if not similar:
                self.since = now
                self.count = 0
            if not similar or result.confidence >= self.confidence:
                self.candidate = text
                self.confidence = result.confidence
        self.count += 1
        if self.candidate == self.accepted:
            return None
        if (
            self.count >= 2
            or self.settle == 0
            or (settled_frame and result.confidence >= 0.85)
            or (result.confidence >= 0.85 and now - self.since >= self.settle)
        ):
            self.accepted = self.candidate
            return self.candidate
        return None
