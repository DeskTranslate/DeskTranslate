"""Opt-in actual OCR qualification of authored Japanese layouts and backgrounds.

No desktop capture or media playback. Tests upright captions, vertical columns,
ruby, short text and switching orientations in one owned native worker.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing
import os
import platform
import sys
import tempfile
import time
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from evaluate import SAMPLES, distance
from fixtures import render_fixture
from PIL import Image
from qualify_product import negative_images
from release_support import runtime_source_hashes

from desktranslate import __version__
from desktranslate.ocr import IsolatedOCR, ModelManager

ROOT = Path(__file__).resolve().parents[1]


def compact(text: str) -> str:
    return "".join(text.split())


def evaluate(models: Path) -> dict:
    before = runtime_source_hashes(ROOT)
    manager = ModelManager(models)
    if not manager.installed("ja", verify=True):
        raise ValueError("The complete verified Japanese pack must already exist; no downloads")
    cases = [case for case in SAMPLES if case["language"] == "ja"] + [
        {"id": "ja-single-kana", "text": "の", "language": "ja", "size": 22},
        {"id": "ja-short-question", "text": "え？", "language": "ja", "size": 30},
    ]
    rows, negative = [], []
    with tempfile.TemporaryDirectory(prefix="desktranslate-authored-layout-") as temporary:
        paths = {}
        for case in cases:
            path = Path(temporary) / (case["id"] + ".png")
            if (ROOT / "tests/fixtures" / path.name).exists():
                path = ROOT / "tests/fixtures" / path.name
            else:
                render_fixture(
                    dict(case, bg=case.get("bg", "#172736"), fg=case.get("fg", "white")), path
                )
            paths[case["id"]] = path
        from PySide6.QtWidgets import QApplication

        if app := QApplication.instance():
            app.shutdown()
        engine = IsolatedOCR("rapidocr", "ja", models)
        try:
            # Interleave modes: a detection-only layout pass must never disable
            # recognition on a subsequent upright frame in the same worker.
            vertical = [case for case in cases if case.get("vertical")]
            horizontal = [case for case in cases if not case.get("vertical")]
            ordered = []
            while vertical or horizontal:
                if vertical:
                    ordered.append(vertical.pop(0))
                if horizontal:
                    ordered.append(horizontal.pop(0))
            for case in ordered:
                path = paths[case["id"]]
                image = Image.open(path).convert("RGB")
                calls = []
                for _ in range(2):
                    start = time.perf_counter()
                    result = engine.recognize(image, "ja", bool(case.get("vertical")))
                    calls.append(
                        {
                            "ocr_call_ms": (time.perf_counter() - start) * 1000,
                            "native_ms": result.duration_ms,
                            "timings": result.timings,
                            "text": result.text,
                            "confidence": result.confidence,
                            "annotations": [line.text for line in result.annotations],
                            "cer": distance(compact(case["text"]), compact(result.text))
                            / max(1, len(compact(case["text"]))),
                            "exact": compact(case["text"]) == compact(result.text),
                        }
                    )
                rows.append(
                    {
                        "id": case["id"],
                        "expected": case["text"],
                        "vertical": bool(case.get("vertical")),
                        "image_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "calls": calls,
                    }
                )
            for kind, image in negative_images():
                for vertical_mode in (False, True):
                    result = engine.recognize(image, "ja", vertical_mode)
                    negative.append(
                        {
                            "background": kind,
                            "vertical": vertical_mode,
                            "text": result.text,
                            "confidence": result.confidence,
                            "empty": not result.text,
                            "native_ms": result.duration_ms,
                        }
                    )
        finally:
            engine.close()
            engine.reap()
    children = [child.pid for child in multiprocessing.active_children()]
    return {
        "version": __version__,
        "scope": __doc__,
        "python_version": platform.python_version(),
        "physical_media": False,
        "provider_tested": False,
        "source_hashes": before,
        "source_unchanged": before == runtime_source_hashes(ROOT),
        "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "fixture_renderer_sha256": hashlib.sha256(
            (ROOT / "tools/fixtures.py").read_bytes()
        ).hexdigest(),
        "models": {key: manager.catalog[key] for key in manager.required("ja")},
        "fixtures": rows,
        "negative": negative,
        "remaining_children": len(children),
        "all_positive_exact": all(call["exact"] for row in rows for call in row["calls"]),
        "vertical_exact": all(
            call["exact"] for row in rows if row["vertical"] for call in row["calls"]
        ),
        "all_negative_empty": all(row["empty"] for row in negative),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ocr-experiment", action="store_true")
    parser.add_argument("--models", type=Path, default=ROOT / ".test-data/models")
    parser.add_argument(
        "--output", type=Path, default=ROOT / ".audit/ocr-layout-qualification.json"
    )
    args = parser.parse_args()
    if not args.ocr_experiment:
        parser.error("Real OCR requires --ocr-experiment; excluded from routine validation")
    script = str(Path(__file__).resolve())
    if os.environ.get("DESKTRANSLATE_LAYOUT_CHILD") != script:
        from qualification_policy import run_bounded_probe

        return run_bounded_probe(
            [sys.executable, script, *sys.argv[1:]],
            dict(os.environ, DESKTRANSLATE_LAYOUT_CHILD=script),
            240,
            ROOT,
            "Authored layout qualification",
        )
    report = evaluate(args.models.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "all_positive_exact",
                    "vertical_exact",
                    "all_negative_empty",
                    "remaining_children",
                    "source_unchanged",
                )
            }
        )
    )
    return (
        0
        if (
            report["all_positive_exact"]
            and report["all_negative_empty"]
            and report["source_unchanged"]
            and not report["remaining_children"]
        )
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
