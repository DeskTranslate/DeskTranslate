"""Opt-in background OCR stage/quality experiment; never captures the desktop.

Natural-scale detection is experimental, applied only to this owned engine.
This command does not change the product's detector or assert media readiness.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import platform
import sys
import tempfile
import time
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from evaluate import SAMPLES, distance
from evaluate_confidence import SHORT_TEXT
from fixtures import render_fixture
from PIL import Image
from release_support import runtime_source_hashes

from desktranslate.metrics import process_resources
from desktranslate.ocr import ModelManager, RapidEngine

ROOT = Path(__file__).resolve().parents[1]


def evaluate(models: Path, selected: list[str] | None = None) -> dict:
    source_before = runtime_source_hashes(ROOT)
    cases = list(SAMPLES) + [
        {"id": name, "language": code, "text": text, "size": size}
        for name, code, text, size in SHORT_TEXT
    ]
    if selected:
        if set(selected) - {case["id"] for case in cases}:
            raise ValueError("Unknown authored case identifier")
        cases = [case for case in cases if case["id"] in selected]
    manager = ModelManager(models)
    rows, initialized = [], []
    with tempfile.TemporaryDirectory(prefix="desktranslate-authored-stages-") as temporary:
        paths = {}
        for case in cases:
            path = ROOT / "tests/fixtures" / (case["id"] + ".png")
            if not path.exists():
                path = Path(temporary) / (case["id"] + ".png")
                render_fixture(dict(case, bg="#172736", fg="white"), path)
            paths[case["id"]] = path
        # Explicitly retire the offscreen font renderer before native inference;
        # neither Qt nor engine resources are left for interpreter finalization.
        from PySide6.QtWidgets import QApplication

        if app := QApplication.instance():
            app.shutdown()
        for code in sorted({case["language"] for case in cases}):
            if not manager.installed(code, verify=True):
                raise ValueError(
                    f"Verified local models required for {code}; no automatic downloads"
                )
            start = time.perf_counter()
            engine = RapidEngine(code, models)
            initialized.append(
                {"language": code, "model_load_ms": (time.perf_counter() - start) * 1000}
            )
            try:
                for case in (case for case in cases if case["language"] == code):
                    path = paths[case["id"]]
                    image = Image.open(path).convert("RGB")
                    variants = {}
                    for label, scaling in (("baseline", "min"), ("natural", "max")):
                        # Local instance override only. Reset for every observation.
                        engine.engine.text_det.limit_type = scaling
                        result = engine.recognize(image, code, bool(case.get("vertical")))
                        variants[label] = {
                            "text": result.text,
                            "confidence": result.confidence,
                            "cer": distance(
                                "".join(case["text"].split()), "".join(result.text.split())
                            )
                            / max(1, len("".join(case["text"].split()))),
                            "total_ms": result.duration_ms,
                            "timings": result.timings,
                            "lines": [
                                {
                                    "text": line.text,
                                    "confidence": line.confidence,
                                    "box": [
                                        line.box.x,
                                        line.box.y,
                                        line.box.width,
                                        line.box.height,
                                    ],
                                }
                                for line in result.lines
                            ],
                        }
                    rows.append(
                        {
                            "id": case["id"],
                            "language": code,
                            "expected": case["text"],
                            "image_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                            "variants": variants,
                        }
                    )
            finally:
                engine.close()
                del engine
                gc.collect()
    return {
        "scope": "Authored still/short-text stage profiling, one observation per variant; not a warm median or physical media test",
        "authored_only": True,
        "physical_media": False,
        "product_detector_changed": False,
        "python_version": platform.python_version(),
        "source_hashes": runtime_source_hashes(ROOT),
        "source_hashes_before": source_before,
        "source_unchanged": source_before == runtime_source_hashes(ROOT),
        "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "resources_at_exit": process_resources(),
        "initialization": initialized,
        "fixtures": rows,
        "comparison": {
            verdict: [
                r["id"]
                for r in rows
                if (
                    r["variants"]["natural"]["cer"] < r["variants"]["baseline"]["cer"]
                    if verdict == "improved"
                    else r["variants"]["natural"]["cer"] > r["variants"]["baseline"]["cer"]
                )
            ]
            for verdict in ("improved", "regressed")
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ocr-experiment", action="store_true")
    parser.add_argument("--models", type=Path, default=ROOT / ".test-data/models")
    parser.add_argument("--cases", nargs="+", help="Optional authored case IDs for a short probe")
    parser.add_argument("--output", type=Path, default=ROOT / ".audit/ocr-stage-experiment.json")
    args = parser.parse_args()
    if not args.ocr_experiment:
        parser.error("Real OCR requires --ocr-experiment; excluded from routine validation")
    script = str(Path(__file__).resolve())
    if os.environ.get("DESKTRANSLATE_OCR_STAGES_CHILD") != script:
        from qualification_policy import run_bounded_probe

        return run_bounded_probe(
            [sys.executable, script, *sys.argv[1:]],
            dict(os.environ, DESKTRANSLATE_OCR_STAGES_CHILD=script),
            300,
            ROOT,
            "OCR stage experiment",
        )
    report = evaluate(args.models.resolve(), args.cases)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["comparison"]))
    return 0 if report["source_unchanged"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
