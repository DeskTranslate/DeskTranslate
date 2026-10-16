"""Opt-in authored sequence OCR/reconciliation benchmark, without desktop playback.

Frame timestamps are replayed, not paced. This measures recognition and proposal
behavior, not real-time capture, provider meaning, full-pipeline latency or media
qualification. Only authored text/images may appear in the output report.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import statistics
import sys
import tempfile
import time
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from evaluate import distance
from fixtures import render_fixture
from PIL import Image
from release_support import runtime_source_hashes

from desktranslate.ocr import IsolatedOCR, ModelManager
from desktranslate.temporal import TemporalTextTracker

ROOT = Path(__file__).resolve().parents[1]
WORKLOADS = (
    (
        "ja-progressive",
        "ja",
        False,
        [
            (0, "彼"),
            (0.08, "彼女"),
            (0.16, "彼女は"),
            (0.24, "彼女は昨日"),
            (0.32, "彼女は昨日ここに来た。"),
            (0.7, "彼女は昨日ここに来た。"),
        ],
        ["彼女は昨日ここに来た。"],
    ),
    (
        "ja-moving-name",
        "ja",
        False,
        [(0, "アルトリア"), (0.2, "アルトリア"), (0.4, "アルトリア"), (0.6, "アルトリア")],
        ["アルトリア"],
    ),
    (
        "en-brief-subtitles",
        "en",
        False,
        [(0, "Wait for me!"), (0.5, "Wait for us!"), (0.9, ""), (1.1, "Go!"), (1.5, "")],
        ["Wait for me!", "Wait for us!", "Go!"],
    ),
    (
        "ko-dialogue",
        "ko",
        False,
        [
            (0, "미카, 문이 열렸어요!"),
            (0.3, "미카, 문이 열렸어요!"),
            (1.2, "내일 오후 3시에 만나요."),
            (1.5, "내일 오후 3시에 만나요."),
        ],
        ["미카, 문이 열렸어요!", "내일 오후 3시에 만나요."],
    ),
    (
        "ja-vertical",
        "ja",
        True,
        [
            (0, "明日また\n会おう"),
            (0.4, "明日また\n会おう"),
            (1.0, "この町の\n名前を\n覚えている"),
            (1.4, "この町の\n名前を\n覚えている"),
        ],
        ["明日また\n会おう", "この町の\n名前を\n覚えている"],
    ),
)


def compact(text: str) -> str:
    return "".join(text.split())


def evaluate(models: Path) -> dict:
    before = runtime_source_hashes(ROOT)
    manager = ModelManager(models)
    rows = []
    with tempfile.TemporaryDirectory(prefix="desktranslate-authored-media-") as temporary:
        paths = {}
        for name, code, vertical, frames, _ in WORKLOADS:
            for index, (_, text) in enumerate(frames):
                path = Path(temporary) / f"{name}-{index}.png"
                render_fixture(
                    {
                        "id": path.stem,
                        "language": code,
                        "text": text,
                        "size": 30,
                        "bg": "#172736",
                        "fg": "white",
                        "gradient": not vertical,
                        "outline": not vertical,
                        "vertical": vertical,
                        "background_phase": index * 7,
                        "offset_x": index % 2,
                    },
                    path,
                )
                paths[name, index] = path
        from PySide6.QtWidgets import QApplication

        if app := QApplication.instance():
            app.shutdown()
        for code in sorted({workload[1] for workload in WORKLOADS}):
            if not manager.installed(code, verify=True):
                raise ValueError(
                    f"Verified local models required for {code}; no automatic downloads"
                )
            engine = IsolatedOCR("rapidocr", code, models)
            try:
                for name, language, vertical, frames, expected in WORKLOADS:
                    if language != code:
                        continue
                    tracker, observations, proposals = TemporalTextTracker(), [], []
                    raw_changes, previous = 0, ""
                    for index, (captured, text) in enumerate(frames):
                        path = paths[name, index]
                        start = time.perf_counter()
                        result = engine.recognize(Image.open(path).convert("RGB"), code, vertical)
                        call_ms = (time.perf_counter() - start) * 1000
                        if result.text and result.text != previous:
                            raw_changes += 1
                        previous = result.text
                        proposal = tracker.observe(result, captured, settled_frame=vertical)
                        if proposal:
                            proposals.append(
                                {
                                    "at_s": captured,
                                    "text": proposal,
                                    "replaces_source": tracker.replaces_source,
                                }
                            )
                        observations.append(
                            {
                                "at_s": captured,
                                "expected": text,
                                "recognized": result.text,
                                "confidence": result.confidence,
                                "cer": distance(compact(text), compact(result.text))
                                / max(1, len(compact(text))),
                                "ocr_call_ms": call_ms,
                                "timings": result.timings,
                                "temporal_reason": tracker.reason,
                                "image_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                            }
                        )
                    missing = [
                        text
                        for text in expected
                        if not any(compact(p["text"]) == compact(text) for p in proposals)
                    ]
                    rows.append(
                        {
                            "id": name,
                            "language": code,
                            "expected_complete_lines": expected,
                            "observations": observations,
                            "proposals": proposals,
                            "raw_ocr_changes": raw_changes,
                            "proposals_per_complete_line": len(proposals) / len(expected),
                            "missing_exact_complete_lines": missing,
                            "exact_complete_lines_passed": not missing,
                        }
                    )
            finally:
                engine.close()
                engine.reap()
    times = [f["ocr_call_ms"] for r in rows for f in r["observations"]]
    return {
        "scope": __doc__,
        "python_version": platform.python_version(),
        "physical_media": False,
        "replay_not_realtime": True,
        "provider_tested": False,
        "source_hashes": before,
        "source_unchanged": before == runtime_source_hashes(ROOT),
        "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "fixture_renderer_sha256": hashlib.sha256(
            (ROOT / "tools/fixtures.py").read_bytes()
        ).hexdigest(),
        "ocr_call_ms_median": statistics.median(times),
        "ocr_call_ms_max": max(times),
        "workloads": rows,
        "exact_complete_lines_passed": all(r["exact_complete_lines_passed"] for r in rows),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ocr-experiment", action="store_true")
    parser.add_argument("--models", type=Path, default=ROOT / ".test-data/models")
    parser.add_argument(
        "--output", type=Path, default=ROOT / ".audit/media-sequence-experiment.json"
    )
    args = parser.parse_args()
    if not args.ocr_experiment:
        parser.error("Real OCR requires --ocr-experiment; excluded from routine validation")
    script = str(Path(__file__).resolve())
    if os.environ.get("DESKTRANSLATE_MEDIA_SEQUENCE_CHILD") != script:
        from qualification_policy import run_bounded_probe

        return run_bounded_probe(
            [sys.executable, script, *sys.argv[1:]],
            dict(os.environ, DESKTRANSLATE_MEDIA_SEQUENCE_CHILD=script),
            240,
            ROOT,
            "Authored media sequence experiment",
        )
    report = evaluate(args.models.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "complete_lines_passed": report["exact_complete_lines_passed"],
                "workloads": [
                    {
                        "id": r["id"],
                        "proposals": len(r["proposals"]),
                        "missing": len(r["missing_exact_complete_lines"]),
                    }
                    for r in report["workloads"]
                ],
            }
        )
    )
    return 0 if report["exact_complete_lines_passed"] and report["source_unchanged"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
