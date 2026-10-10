"""Opt-in real OCR/Google setup probe using only the six authored bundled samples."""

from __future__ import annotations

import json
from difflib import SequenceMatcher
from pathlib import Path

from PIL import Image

from desktranslate import __version__
from desktranslate.algorithms import normalize_text
from desktranslate.models import TranslationRequest
from desktranslate.ocr import IsolatedOCR, ModelManager
from desktranslate.providers import create_provider
from desktranslate.ui.onboarding import SAMPLES


def main() -> None:
    manager = ModelManager()
    results = []
    provider = create_provider("google")
    try:
        for language, (filename, expected) in SAMPLES.items():
            if not manager.installed(language, verify=True):
                raise RuntimeError(
                    "Install and verify the sample language packs before this opt-in test"
                )
            engine = IsolatedOCR("rapidocr", language)
            try:
                image = Image.open(Path("src/desktranslate/assets/samples") / filename).convert(
                    "RGB"
                )
                result = engine.recognize(image, language)
                fidelity = SequenceMatcher(
                    None, normalize_text(expected), normalize_text(result.text)
                ).ratio()
                if fidelity < 0.8:
                    raise RuntimeError(
                        "Authored sample recognition did not meet the setup fidelity guard; no text sent"
                    )
                target = "en" if language != "en" else "es"
                translated = provider.translate(TranslationRequest(result.text, language, target))
                results.append(
                    {
                        "source": language,
                        "target": target,
                        "recognition_fidelity": round(fidelity, 3),
                        "ocr_ms": round(result.duration_ms, 2),
                        "translation_nonempty": bool(translated.text.strip()),
                        "translation_changed": normalize_text(result.text)
                        != normalize_text(translated.text),
                    }
                )
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
        "passed": len(results) == 6
        and all(
            sample["translation_nonempty"] and sample["translation_changed"] for sample in results
        ),
    }
    Path("docs/sample-qualification.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
