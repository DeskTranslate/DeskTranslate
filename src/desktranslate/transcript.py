"""Opt-in bounded session text. This module performs no persistence."""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class TranscriptEntry:
    time: str
    source: str
    translation: str


class SessionTranscript:
    def __init__(self, capacity: int = 200, chars: int = 100_000) -> None:
        self.enabled = False
        self.capacity, self.chars = capacity, chars
        self.entries: deque[TranscriptEntry] = deque()
        self.size = 0

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        if not enabled:
            self.clear()

    def append(self, source: str, translation: str) -> None:
        if not self.enabled or len(source) + len(translation) > self.chars:
            return
        if self.entries and (self.entries[-1].source, self.entries[-1].translation) == (
            source,
            translation,
        ):
            return
        self.entries.append(
            TranscriptEntry(datetime.now(UTC).isoformat(timespec="seconds"), source, translation)
        )
        self.size += len(source) + len(translation)
        while len(self.entries) > self.capacity or self.size > self.chars:
            old = self.entries.popleft()
            self.size -= len(old.source) + len(old.translation)

    def clear(self) -> None:
        self.entries.clear()
        self.size = 0

    def snapshot(self) -> list[dict[str, str]]:
        return [asdict(entry) for entry in self.entries]
