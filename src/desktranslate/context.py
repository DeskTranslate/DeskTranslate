import hashlib
import json
import re
import unicodedata
from collections import OrderedDict, deque
from collections.abc import Mapping

from desktranslate.models import ContextPair, TranslationRequest, TranslationResult


class TranslationContext:
    def __init__(self, entries: int = 8, chars: int = 6000) -> None:
        self.entries = entries
        self.chars = chars
        self.pairs: deque[ContextPair] = deque()

    def token_upper_bound(self) -> int:
        # UTF-8 byte count conservatively bounds byte-fallback tokenizer output.
        # Reserve additional space for serialization of each reference pair.
        payload = [{"source": p.source, "translation": p.translation} for p in self.pairs]
        return len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    def accept(self, source: str, translation: str, replaces_source: str = "") -> None:
        if self.entries == 0 or len(source) + len(translation) > self.chars:
            return
        pair = ContextPair(source, translation)
        if self.pairs and self.pairs[-1].source in {source, replaces_source}:
            self.pairs.pop()  # A corrected/provisional line is one dialogue turn.
        self.pairs.append(pair)
        while (
            len(self.pairs) > self.entries
            or self.token_upper_bound() > 2400
            or sum(len(p.source) + len(p.translation) for p in self.pairs) > self.chars
        ):
            self.pairs.popleft()

    def snapshot(self) -> tuple[ContextPair, ...]:
        return tuple(self.pairs)

    def clear(self) -> None:
        self.pairs.clear()


def cache_key(provider: str, endpoint: str, request: TranslationRequest) -> str:
    from dataclasses import asdict

    data = {"prompt_version": 2, "provider": provider, "endpoint": endpoint, **asdict(request)}
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class TranslationCache:
    def __init__(self, capacity: int = 256) -> None:
        self.capacity = capacity
        self.items: OrderedDict[str, TranslationResult] = OrderedDict()

    def get(self, key: str) -> TranslationResult | None:
        if key not in self.items:
            return None
        self.items.move_to_end(key)
        result = self.items[key]
        return TranslationResult(result.text, cached=True)

    def put(self, key: str, value: TranslationResult) -> None:
        self.items[key] = value
        self.items.move_to_end(key)
        while len(self.items) > self.capacity:
            self.items.popitem(last=False)


def folded(text: str) -> str:
    return unicodedata.normalize("NFC", text).casefold()


def joined_word(character: str) -> bool:
    # Latin/Cyrillic/etc. terms must not match inside another word. Japanese,
    # Chinese and Korean do not require spaces around a matching proper noun.
    return (
        character.isalnum()
        and not any(
            name in unicodedata.name(character, "")
            for name in ("CJK", "HIRAGANA", "KATAKANA", "HANGUL")
        )
        or unicodedata.category(character).startswith("M")
        or character == "_"
    )


def contains_term(text: str, term: str) -> bool:
    at = text.find(term)
    while at >= 0:
        end = at + len(term)
        if (not joined_word(term[0]) or at == 0 or not joined_word(text[at - 1])) and (
            not joined_word(term[-1]) or end == len(text) or not joined_word(text[end])
        ):
            return True
        at = text.find(term, at + 1)
    return False


class Terminology:
    """User-approved terms, retrieved locally; no inferred vocabulary is persisted."""

    def __init__(self, glossary: Mapping[str, str]) -> None:
        self.terms = tuple(
            (source, target, folded(source))
            for source, target in sorted(
                glossary.items(), key=lambda item: (-len(item[0]), item[0])
            )
            if source.strip()
        )

    def relevant(self, text: str, recent: tuple[ContextPair, ...]) -> tuple[tuple[str, str], ...]:
        current = folded(text)
        background = folded("\n".join(pair.source for pair in recent[-2:]))
        ranked = sorted(
            (
                (0 if contains_term(current, normalized) else 1, source, target)
                for source, target, normalized in self.terms
                if contains_term(current, normalized) or contains_term(background, normalized)
            ),
            key=lambda row: (row[0], -len(row[1]), row[1]),
        )
        result: list[tuple[str, str]] = []
        used = 0
        for _, source, target in ranked:
            size = len(json.dumps([source, target], ensure_ascii=False).encode("utf-8"))
            if used + size > 1800 or len(result) == 24:
                continue
            result.append((source, target))
            used += size
        return tuple(result)

    def exact(self, text: str) -> str | None:
        normalized = unicodedata.normalize("NFC", text.strip())
        return next(
            (
                target
                for source, target, _ in self.terms
                if unicodedata.normalize("NFC", source) == normalized
            ),
            None,
        )


class ContextEngine:
    """Explicit story/terminology configuration plus ephemeral recent dialogue.

    Cache remains a separate performance service. Retrieval cannot mutate the
    user's glossary or create an invisible persistent story/history store.
    """

    def __init__(
        self, recent: TranslationContext, glossary: Mapping[str, str], story: str = ""
    ) -> None:
        self.recent = recent
        self.terminology = Terminology(glossary)
        self.story = story

    def request(
        self,
        text: str,
        source: str,
        target: str,
        *,
        contextual: bool,
        model: str = "",
        style: str = "natural",
        instructions: str = "",
        replaces_source: str = "",
    ) -> TranslationRequest:
        recent = self.recent.snapshot() if contextual else ()
        while recent and recent[-1].source in {text, replaces_source}:
            recent = recent[:-1]  # Do not translate a line using itself as its own context.
        speaker = ""
        if contextual and (match := re.match(r"^([^\n:：]{1,40})[:：]\s*\S", text)):
            name = match[1].strip()
            if name and any(folded(name) == term for _, _, term in self.terminology.terms):
                speaker = name
        return TranslationRequest(
            text,
            source,
            target,
            model,
            style,
            recent,
            self.terminology.relevant(text, recent) if contextual else (),
            instructions,
            self.story if contextual else "",
            speaker,
        )
