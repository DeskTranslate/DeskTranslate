"""Synthetic, redistributable OCR fixtures and repeatable engine benchmarks."""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path
from threading import Event

from PIL import Image, ImageDraw, ImageFont

from desktranslate.algorithms import FrameGate, preprocess
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
]


def generate(directory: Path, font_dir: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for sample in SAMPLES:
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


def benchmark(directory: Path, engine_name: str, install: bool) -> dict:
    report: dict = {"engine": engine_name, "fixtures": []}
    engines: dict = {}
    manager = ModelManager()
    for sample in SAMPLES:
        language = str(sample["language"])
        if language not in engines:
            if install:
                manager.install(language, Event(), lambda model, done, total: None)
            start = time.perf_counter()
            engines[language] = (
                RapidEngine(language) if engine_name == "rapidocr" else TesseractEngine()
            )
            report.setdefault("startup_ms", {})[language] = (time.perf_counter() - start) * 1000
        engine = engines[language]
        image = Image.open(directory / (str(sample["id"]) + ".png")).convert("RGB")
        variants = []
        for mode in ("original", "contrast", "subtitle"):
            measurements = []
            for _ in range(3):
                result = engine.recognize(preprocess(image, mode), language)
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
        report["fixtures"].append({"id": sample["id"], "language": language, "variants": variants})
    for engine in engines.values():
        engine.close()
    gate = FrameGate()
    start = time.perf_counter()
    for n in range(1000):
        gate.observe(image, n * 0.2)
    report["static_gate_ms_per_frame"] = (time.perf_counter() - start) * 1000 / 1000
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate", action="store_true")
    parser.add_argument(
        "--install", action="store_true", help="Explicitly download missing OCR models"
    )
    parser.add_argument("--engine", choices=["rapidocr", "tesseract"], default="rapidocr")
    parser.add_argument("--fixtures", type=Path, default=Path("tests/fixtures"))
    parser.add_argument("--fonts", type=Path, default=Path("C:/Windows/Fonts"))
    parser.add_argument("--output", type=Path, default=Path("docs/ocr-benchmark.json"))
    args = parser.parse_args()
    if args.generate:
        generate(args.fixtures, args.fonts)
    report = benchmark(args.fixtures, args.engine, args.install)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Evaluated {len(report['fixtures'])} synthetic fixtures. Report: {args.output}")


if __name__ == "__main__":
    main()
