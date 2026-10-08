"""Opt-in runtime probes on synthetic input; no screen content or credentials printed."""

from __future__ import annotations

import json
import sys
import time
from threading import Event

from PIL import Image

from desktranslate.algorithms import preprocess
from desktranslate.models import TranslationRequest
from desktranslate.ocr import IsolatedOCR, ModelManager, RapidEngine
from desktranslate.providers import create_provider


def main() -> None:
    mode = sys.argv[1]
    if mode == "korean":
        ModelManager().install("ko", Event(), lambda *args: None)
        engine = RapidEngine("ko")
        image = Image.open("tests/fixtures/ko-subtitle.png").convert("RGB")
        for variant in ("original", "contrast", "subtitle"):
            result = engine.recognize(preprocess(image, variant), "ko")
            print(
                json.dumps(
                    {
                        "mode": variant,
                        "result": result.text,
                        "confidence": result.confidence,
                        "ms": result.duration_ms,
                    },
                    ensure_ascii=True,
                )
            )
    elif mode == "isolated":
        engine = IsolatedOCR("rapidocr", "ja")
        try:
            result = engine.recognize(Image.open("tests/fixtures/ja-game.png").convert("RGB"), "ja")
            print(
                json.dumps(
                    {
                        "recognized": bool(result.text),
                        "correct": result.text == "明日、またここで会おう。",
                        "ms": result.duration_ms,
                    }
                )
            )
        finally:
            engine.close()
        engine = IsolatedOCR("rapidocr", "ja")
        start = time.monotonic()
        engine.close()
        engine.process.join(3)
        print(
            json.dumps(
                {
                    "shutdown_ms": (time.monotonic() - start) * 1000,
                    "terminated": not engine.process.is_alive(),
                }
            )
        )
    elif mode == "translation":
        provider = create_provider("google")
        try:
            result = provider.translate(TranslationRequest("明日、またここで会おう。", "ja", "en"))
            print(
                json.dumps(
                    {
                        "nonempty_translation": bool(result.text),
                        "different_from_source": result.text != "明日、またここで会おう。",
                    }
                )
            )
        finally:
            provider.close()
    else:
        raise SystemExit("Choose korean, isolated or translation")


if __name__ == "__main__":
    main()
