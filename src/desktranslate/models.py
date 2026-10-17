from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from PIL import Image


@dataclass(frozen=True)
class Rect:
    """A half-open rectangle; capture rectangles always use physical desktop pixels."""

    x: int
    y: int
    width: int
    height: int

    def __post_init__(self) -> None:
        if any(type(value) is not int for value in (self.x, self.y, self.width, self.height)):
            raise ValueError("Rectangle coordinates must be integers")
        if not all(
            -(2**31) <= value < 2**31 for value in (self.x, self.y, self.right, self.bottom)
        ):
            raise ValueError("Rectangle coordinates exceed the native desktop range")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Rectangle dimensions must be positive")
        if self.width > 16384 or self.height > 16384 or self.width * self.height > 40_000_000:
            raise ValueError("The region is too large. Select a smaller text area.")

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    def contains(self, other: Rect) -> bool:
        return (
            self.x <= other.x
            and self.y <= other.y
            and self.right >= other.right
            and self.bottom >= other.bottom
        )

    def intersects(self, other: Rect) -> bool:
        return (
            self.x < other.right
            and other.x < self.right
            and self.y < other.bottom
            and other.y < self.bottom
        )


@dataclass(frozen=True)
class Monitor:
    name: str
    logical: Rect
    physical: Rect

    def to_physical(self, region: Rect) -> Rect:
        """Scale offsets from this monitor's origin, never the virtual desktop origin."""
        if not self.logical.contains(region):
            raise ValueError("Select a region contained in one monitor")
        sx = self.physical.width / self.logical.width
        sy = self.physical.height / self.logical.height
        left = round((region.x - self.logical.x) * sx) + self.physical.x
        top = round((region.y - self.logical.y) * sy) + self.physical.y
        right = round((region.right - self.logical.x) * sx) + self.physical.x
        bottom = round((region.bottom - self.logical.y) * sy) + self.physical.y
        return Rect(left, top, max(1, right - left), max(1, bottom - top))


@dataclass(frozen=True)
class OCRLine:
    text: str
    box: Rect
    confidence: float


@dataclass(frozen=True)
class OCRResult:
    text: str
    lines: tuple[OCRLine, ...] = ()
    confidence: float = 0.0
    language: str = "auto"
    duration_ms: float = 0.0
    timings: dict[str, float] = field(default_factory=dict)
    annotations: tuple[OCRLine, ...] = ()


@dataclass(frozen=True)
class ModelInfo:
    id: str
    name: str
    context_length: int | None = None
    input_price: str | None = None
    output_price: str | None = None
    size_bytes: int | None = None
    text_support: str = "unverified"

    def __post_init__(self) -> None:
        for value, limit in ((self.id, 200), (self.name, 500)):
            if (
                not isinstance(value, str)
                or not value.strip()
                or len(value) > limit
                or any(ord(character) < 32 for character in value)
            ):
                raise ValueError("Invalid model identity")
        for numeric, maximum in ((self.context_length, 100_000_000), (self.size_bytes, 10**15)):
            if numeric is not None and (type(numeric) is not int or not 0 <= numeric <= maximum):
                raise ValueError("Invalid model metadata")
        for price in (self.input_price, self.output_price):
            if price is not None and (not isinstance(price, str) or len(price) > 100):
                raise ValueError("Invalid model pricing")


@dataclass(frozen=True)
class Capabilities:
    local: bool = False
    requires_key: bool = True
    context: bool = True
    model_discovery: bool = True
    token_usage: bool = True
    images: bool = False
    streaming: bool = False
    structured_output: bool = False
    text_generation: bool = True
    reasoning: bool = False


@dataclass(frozen=True)
class ContextPair:
    source: str
    translation: str


@dataclass(frozen=True)
class TranslationRequest:
    text: str
    source: str
    target: str
    model: str = ""
    style: str = "natural"
    context: tuple[ContextPair, ...] = ()
    glossary: tuple[tuple[str, str], ...] = ()
    instructions: str = ""
    story_context: str = ""
    speaker: str = ""


@dataclass(frozen=True)
class TranslationResult:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    cached: bool = False


class CaptureProvider(Protocol):
    def capture(self, region: Rect) -> Image.Image: ...
    def close(self) -> None: ...


class OCREngine(Protocol):
    def recognize(self, image: Image.Image, language: str, vertical: bool = False) -> OCRResult: ...
    def close(self) -> None: ...


class TranslationProvider(Protocol):
    capabilities: Capabilities

    def translate(self, request: TranslationRequest) -> TranslationResult: ...
    def models(self) -> list[ModelInfo]: ...
    def close(self) -> None: ...


class SessionState(StrEnum):
    IDLE = "idle"
    SELECTING = "selecting"
    STARTING = "starting"
    WATCHING = "watching"
    WAITING_TARGET = "waiting for window"
    RECOGNIZING = "recognizing"
    TRANSLATING = "translating"
    PAUSED = "paused"
    ERROR = "error"
    STOPPING = "stopping"


@dataclass(frozen=True)
class Stamp:
    session: int
    generation: int


@dataclass(frozen=True)
class PipelineEvent:
    stamp: Stamp
    state: SessionState
    source: str = ""
    result: TranslationResult | None = None
    error: str = ""
    category: str = ""
    timings: dict[str, float] = field(default_factory=dict)
    clear: bool = False
    region: Rect | None = None
    created: float = field(default_factory=time.monotonic)
    replaces_source: str = ""
