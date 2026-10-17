"""Opt-in CPU OCR benchmark on authored fixtures; no desktop capture/playback.

Excluded from routine validation. A supervisor bounds the owned process tree;
partial reports survive failure/timeout. Only one model family stays loaded.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import platform
import statistics
import sys
import time
from pathlib import Path
from threading import Event

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from fixtures import EXTRA_SAMPLES, render_fixture
from PIL import Image, ImageDraw, ImageFont
from release_support import runtime_source_hashes

from desktranslate import __version__
from desktranslate.algorithms import FrameGate, preprocess
from desktranslate.languages import REGISTRY
from desktranslate.ocr import ModelManager, RapidEngine, TesseractEngine

SAMPLES = [
    {
        "id": "ja-game",
        "language": "ja",
        "text": "明日、またここで会おう。",
        "font": "YuGothM.ttc",
        "size": 32,
        "bg": "#14262e",
        "fg": "white",
    },
    {
        "id": "ja-multiline",
        "language": "ja",
        "text": "この町の名前を覚えている？\nもう一度、教えて。",
        "font": "YuGothM.ttc",
        "size": 30,
        "bg": "#fff4db",
        "fg": "#17252e",
    },
    {
        "id": "ko-subtitle",
        "language": "ko",
        "text": "내일 다시 만나요.",
        "font": "malgun.ttf",
        "size": 30,
        "bg": "#172736",
        "fg": "white",
        "outline": True,
    },
    {
        "id": "zh-dialogue",
        "language": "zh-CN",
        "text": "明天我们在这里见面。",
        "font": "msjh.ttc",
        "size": 32,
        "bg": "#f6f7f1",
        "fg": "#111e25",
    },
    {
        "id": "zh-traditional",
        "language": "zh-TW",
        "text": "明天我們在這裡見面。",
        "font": "msjh.ttc",
        "size": 32,
        "bg": "#111e25",
        "fg": "white",
    },
    {
        "id": "en-ui",
        "language": "en",
        "text": "Select a region to translate.",
        "font": "segoeui.ttf",
        "size": 26,
        "bg": "#f5f8f6",
        "fg": "#111e25",
    },
    {
        "id": "en-small",
        "language": "en",
        "text": "The door is locked. Find another way.",
        "font": "segoeui.ttf",
        "size": 13,
        "bg": "#17252e",
        "fg": "white",
    },
    {
        "id": "en-outlined",
        "language": "en",
        "text": "Where did you hide the key?",
        "font": "segoeui.ttf",
        "size": 28,
        "bg": "#87a29b",
        "fg": "white",
        "outline": True,
    },
    {
        "id": "es-ui",
        "language": "es",
        "text": "Selecciona una región para traducir.",
        "font": "segoeui.ttf",
        "size": 28,
        "bg": "white",
        "fg": "black",
    },
] + EXTRA_SAMPLES
ROOT = Path(__file__).resolve().parents[1]


def generate(directory: Path, font_dir: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for sample in SAMPLES:
        if sample.get("render") == "qt":
            render_fixture(sample, directory / (str(sample["id"]) + ".png"))
            continue
        font = ImageFont.truetype(str(font_dir / str(sample["font"])), int(sample["size"]))
        image = Image.new("RGB", (660, 160), str(sample["bg"]))
        ImageDraw.Draw(image).multiline_text(
            (24, 40),
            str(sample["text"]),
            font=font,
            fill=str(sample["fg"]),
            spacing=12,
            stroke_width=2 if sample.get("outline") else 0,
            stroke_fill="black",
        )
        image.save(directory / (str(sample["id"]) + ".png"))
    (directory / "samples.json").write_text(
        json.dumps(SAMPLES, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def distance(a: str, b: str) -> int:
    previous = list(range(len(b) + 1))
    for i, left in enumerate(a, 1):
        row = [i]
        for j, right in enumerate(b, 1):
            row.append(min(row[-1] + 1, previous[j] + 1, previous[j - 1] + (left != right)))
        previous = row
    return previous[-1]


def benchmark(
    directory: Path,
    engine_name: str,
    install: bool,
    repeats: int = 3,
    *,
    models: Path | None = None,
    cases: list[str] | None = None,
    output: Path | None = None,
) -> dict:
    samples = [sample for sample in SAMPLES if not cases or sample["id"] in cases]
    if not samples or (cases and set(cases) - {sample["id"] for sample in samples}):
        raise ValueError("Choose existing authored fixture identifiers")
    report: dict = {
        "engine": engine_name,
        "repeats_per_variant": repeats,
        "authored_fixtures_only": True,
        "fixtures": [],
        "completed": False,
        "cleanup_completed": False,
        "version": __version__,
        "python_version": platform.python_version(),
        "system": platform.platform(),
        "logical_processors": os.cpu_count(),
        "source_hashes": runtime_source_hashes(ROOT),
        "fixture_hashes": {
            str(sample["id"]) + ".png": hashlib.sha256(
                (directory / (str(sample["id"]) + ".png")).read_bytes()
            ).hexdigest()
            for sample in samples
        },
    }
    manager = ModelManager(models)
    engine = None

    def checkpoint() -> None:
        report["source_unchanged"] = report["source_hashes"] == runtime_source_hashes(ROOT)
        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            partial = output.with_suffix(output.suffix + ".part")
            partial.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(partial, output)

    def family(sample: dict) -> str:
        code = str(sample["language"])
        return (
            manager.catalog[REGISTRY[code].recognition]["filename"]
            if engine_name == "rapidocr"
            else code
        )

    checkpoint()
    try:
        current = ""
        # Grouping permits native session reuse without retaining every language
        # model in memory. Inference failure still closes the active family.
        for sample in sorted(samples, key=family):
            language = str(sample["language"])
            if family(sample) != current:
                if engine:
                    engine.close()
                    engine = None
                    gc.collect()  # Native wrapper cycles belong to this probe only.
                if install:
                    manager.install(language, Event(), lambda model, done, total: None)
                start = time.perf_counter()
                engine = (
                    RapidEngine(language, manager.directory)
                    if engine_name == "rapidocr"
                    else TesseractEngine()
                )
                report.setdefault("startup_ms", {})[language] = (time.perf_counter() - start) * 1000
                current = family(sample)
            assert engine is not None
            with Image.open(directory / (str(sample["id"]) + ".png")) as source:
                image = source.convert("RGB")
            variants = []
            for mode in ("original", "contrast", "subtitle"):
                measurements = []
                for _ in range(repeats):
                    result = engine.recognize(
                        preprocess(image, mode), language, bool(sample.get("vertical"))
                    )
                    measurements.append(result.duration_ms)
                expected = "".join(str(sample["text"]).split())
                actual = "".join(result.text.split())
                variants.append(
                    {
                        "mode": mode,
                        "cer": distance(expected, actual) / max(1, len(expected)),
                        "latency_ms_median": statistics.median(measurements),
                        "text": result.text,
                    }
                )
            report["fixtures"].append(
                {
                    "id": sample["id"],
                    "language": language,
                    "vertical": bool(sample.get("vertical")),
                    "variants": variants,
                }
            )
            checkpoint()
        gate = FrameGate()
        start = time.perf_counter()
        for n in range(1000):
            gate.observe(image, n * 0.2)
        report["static_gate_ms_per_frame"] = (time.perf_counter() - start) * 1000 / 1000
        report["completed"] = True
    except BaseException as error:
        report["failure_category"] = type(error).__name__
        raise
    finally:
        try:
            if engine:
                engine.close()
                engine = None
                gc.collect()
            report["cleanup_completed"] = True
        finally:
            checkpoint()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ocr-experiment", action="store_true")
    parser.add_argument("--generate", action="store_true")
    parser.add_argument(
        "--install", action="store_true", help="Explicitly download missing OCR models"
    )
    parser.add_argument("--engine", choices=["rapidocr", "tesseract"], default="rapidocr")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--cases", nargs="+", help="Optional authored fixture IDs")
    parser.add_argument("--models", type=Path, default=ROOT / ".test-data/models")
    parser.add_argument(
        "--benchmark-timeout", type=int, default=300, help="Owned deadline,30–1800s"
    )
    parser.add_argument("--fixtures", type=Path, default=Path("tests/fixtures"))
    parser.add_argument("--fonts", type=Path, default=Path("C:/Windows/Fonts"))
    parser.add_argument("--output", type=Path, default=ROOT / ".audit/ocr-benchmark.json")
    args = parser.parse_args()
    if not args.ocr_experiment:
        parser.error("CPU OCR requires --ocr-experiment; excluded from routine validation")
    if not 1 <= args.repeats <= 20:
        parser.error("Use between one and twenty repetitions")
    if not 30 <= args.benchmark_timeout <= 1800:
        parser.error("--benchmark-timeout must be between30 and1800 seconds")
    script = str(Path(__file__).resolve())
    if os.environ.get("DESKTRANSLATE_BENCHMARK_CHILD") != script:
        from qualification_policy import run_bounded_probe

        return run_bounded_probe(
            [sys.executable, script, *sys.argv[1:]],
            dict(os.environ, DESKTRANSLATE_BENCHMARK_CHILD=script),
            args.benchmark_timeout,
            ROOT,
            "Authored OCR benchmark",
        )
    if args.generate:
        generate(args.fixtures, args.fonts)
        from PySide6.QtWidgets import QApplication

        if app := QApplication.instance():
            app.shutdown()
    report = benchmark(
        args.fixtures,
        args.engine,
        args.install,
        args.repeats,
        models=args.models,
        cases=args.cases,
        output=args.output,
    )
    print(f"Evaluated {len(report['fixtures'])} synthetic fixtures. Report: {args.output}")
    return (
        0
        if report["completed"] and report["cleanup_completed"] and report["source_unchanged"]
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
