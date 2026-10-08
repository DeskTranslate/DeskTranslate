import hashlib
import json
from collections import OrderedDict, deque

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

    def accept(self, source: str, translation: str) -> None:
        if self.entries == 0 or len(source) + len(translation) > self.chars:
            return
        self.pairs.append(ContextPair(source, translation))
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

    data = {"prompt_version": 1, "provider": provider, "endpoint": endpoint, **asdict(request)}
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
