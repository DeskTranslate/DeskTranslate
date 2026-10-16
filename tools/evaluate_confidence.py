"""Opt-in OCR confidence tradeoff experiment; authored inputs, one background worker."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from evaluate import SAMPLES, distance
from fixtures import render_fixture
from PIL import Image
from release_support import runtime_source_hashes

from desktranslate.algorithms import reconstruct
from desktranslate.languages import REGISTRY
from desktranslate.ocr import IsolatedOCR

SHORT_TEXT = [
    ("ja-single-question", "ja", "え？", 30),
    ("ja-single-glyph", "ja", "の", 22),
    ("ko-single-glyph", "ko", "문", 24),
    ("en-single-pronoun", "en", "I", 20),
    ("en-number", "en", "7", 22),
    ("en-punctuation", "en", "?", 26),
    ("es-short-answer", "es", "¡Sí!", 24),
    ("zh-single-glyph", "zh-CN", "一", 26),
    ("en-tiny-ui", "en", "HP 7 / MP 3", 12),
]
ROOT = Path(__file__).resolve().parents[1]


def evaluate(models: Path) -> dict:
    cases = list(SAMPLES) + [
        {"id": name, "language": code, "text": text, "size": size}
        for name, code, text, size in SHORT_TEXT
    ]
    rows = []
    engine, current = None, ""
    with tempfile.TemporaryDirectory(prefix="desktranslate-authored-confidence-") as temporary:
        try:
            for case in sorted(cases, key=lambda case: case["language"]):
                code = case["language"]
                if code != current:
                    if engine:
                        engine.close()
                        engine.reap()
                    engine = IsolatedOCR("rapidocr", code, models)
                    current = code
                path = ROOT / "tests/fixtures" / (case["id"] + ".png")
                if not path.exists():
                    path = Path(temporary) / (case["id"] + ".png")
                    render_fixture(dict(case, bg="#172736", fg="white"), path)
                assert engine is not None
                result = engine.recognize(
                    Image.open(path).convert("RGB"), code, bool(case.get("vertical"))
                )
                expected = "".join(case["text"].split())
                values = {}
                for cutoff in (0.5, 0.7, 0.8, 0.9):
                    text = reconstruct(
                        tuple(line for line in result.lines if line.confidence >= cutoff),
                        bool(case.get("vertical")),
                        REGISTRY[code].direction,
                    )
                    values[str(cutoff)] = {
                        "cer": round(
                            distance(expected, "".join(text.split())) / max(1, len(expected)), 4
                        ),
                        "text": text,
                    }
                rows.append(
                    {
                        "id": case["id"],
                        "source": code,
                        "expected": case["text"],
                        "variants": values,
                        "image_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "line_confidences": [round(line.confidence, 5) for line in result.lines],
                    }
                )
        finally:
            if engine:
                engine.close()
                engine.reap()
    return {
        "authored_only": True,
        "physical_media": False,
        "scope": "Post-recognition confidence filtering on original RGB: 35 existing positives plus nine short-text cases. No application threshold changed.",
        "source_hashes": runtime_source_hashes(ROOT),
        "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "fixtures": rows,
        "comparison": {
            cutoff: {
                "improved": [
                    r["id"]
                    for r in rows
                    if r["variants"][cutoff]["cer"] < r["variants"]["0.5"]["cer"]
                ],
                "regressed": [
                    r["id"]
                    for r in rows
                    if r["variants"][cutoff]["cer"] > r["variants"]["0.5"]["cer"]
                ],
            }
            for cutoff in ("0.7", "0.8", "0.9")
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ocr-experiment", action="store_true")
    parser.add_argument("--models", type=Path, default=ROOT / ".test-data/models")
    parser.add_argument(
        "--output", type=Path, default=ROOT / ".audit/ocr-confidence-experiment.json"
    )
    args = parser.parse_args()
    if not args.ocr_experiment:
        parser.error("Real OCR requires --ocr-experiment; excluded from routine validation")
    if os.environ.get("DESKTRANSLATE_CONFIDENCE_CHILD") != str(Path(__file__).resolve()):
        from qualification_policy import run_bounded_probe

        environment = dict(os.environ, DESKTRANSLATE_CONFIDENCE_CHILD=str(Path(__file__).resolve()))
        return run_bounded_probe(
            [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]],
            environment,
            300,
            ROOT,
            "OCR confidence experiment",
        )
    report = evaluate(args.models.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["comparison"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
