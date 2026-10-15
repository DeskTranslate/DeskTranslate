"""Opt-in real OCR/Google setup probe using only authored bundled samples."""

from __future__ import annotations

import json
from difflib import SequenceMatcher
from pathlib import Path

from PIL import Image

from desktranslate import __version__
from desktranslate.algorithms import normalize_text
from desktranslate.errors import DeskTranslateError
from desktranslate.models import TranslationRequest
from desktranslate.ocr import IsolatedOCR, ModelManager
from desktranslate.providers import create_provider
from desktranslate.ui.onboarding import SAMPLES


def main() -> None:
    manager = ModelManager()
    results = []
    provider = create_provider("google")
    translation_available = True
    try:
        for language, (filename, expected) in SAMPLES.items():
            sample = {"source": language, "ocr": "NOT TESTED", "translation": "NOT TESTED"}
            results.append(sample)
            if not manager.installed(language, verify=True):
                sample["limitation"] = "Verified language pack is not installed"
                continue
            engine = IsolatedOCR("rapidocr", language)
            try:
                image = Image.open(Path("src/desktranslate/assets/samples") / filename).convert(
                    "RGB"
                )
                result = engine.recognize(image, language)
                fidelity = SequenceMatcher(
                    None, normalize_text(expected), normalize_text(result.text)
                ).ratio()
                sample.update(
                    recognition_fidelity=round(fidelity, 3),
                    ocr_ms=round(result.duration_ms, 2),
                    ocr="PASS" if fidelity >= 0.8 else "FAIL",
                )
                if fidelity < 0.8:
                    sample["limitation"] = "Below setup fidelity guard; no text sent"
                    continue
                if not translation_available:
                    sample["limitation"] = "Earlier service failure; further requests skipped"
                    continue
                target = "en" if language != "en" else "es"
                sample["target"] = target
                try:
                    translated = provider.translate(
                        TranslationRequest(result.text, language, target)
                    )
                    sample.update(
                        translation_nonempty=bool(translated.text.strip()),
                        translation_changed=normalize_text(result.text)
                        != normalize_text(translated.text),
                    )
                    sample["translation"] = (
                        "PASS"
                        if sample["translation_nonempty"] and sample["translation_changed"]
                        else "FAIL"
                    )
                except DeskTranslateError as error:
                    sample.update(translation="FAIL", failure_category=type(error).__name__)
                    translation_available = False
            except DeskTranslateError as error:
                sample.update(ocr="FAIL", failure_category=type(error).__name__)
            finally:
                engine.close()
                engine.reap()
    finally:
        provider.close()
    report = {
        "version": __version__,
        "authored_samples_only": True,
        "live_provider": "Google public web endpoint",
        "paid_provider_or_local_llm_qualification": False,
        "samples": results,
        "passed": len(results) == len(SAMPLES)
        and all(sample["ocr"] == "PASS" and sample["translation"] == "PASS" for sample in results),
    }
    Path("docs/sample-qualification.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
