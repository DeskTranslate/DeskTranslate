"""Opt-in paced authored media → real OCR/HTTP → offscreen overlay qualification.

No desktop capture, input, playback, credentials or external provider. Generation
and timing assertions exercise the application pipeline; HTTP replies are authored
echoes and do not qualify semantic translation. Owns a five-minute deadline.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing
import os
import platform
import statistics
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_SCALE_FACTOR"] = "1"

from evaluate import distance
from fixtures import render_fixture
from PIL import Image
from PySide6.QtWidgets import QApplication
from release_support import runtime_source_hashes

from desktranslate import __version__
from desktranslate.models import SessionState, Stamp
from desktranslate.ocr import IsolatedOCR, ModelManager
from desktranslate.pipeline import Pipeline
from desktranslate.providers import create_provider
from desktranslate.settings import Settings
from desktranslate.ui.overlay import Overlay

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Cue:
    name: str
    text: str
    duration: float
    moving: bool = False
    required: bool = True
    sample: dict | None = None
    turn: str = ""


def semantic_lag(cues: list[Cue], index: int, active: int) -> int:
    # Typewriter prefixes and their completion are revisions of one turn.
    # Count unrelated dialogue, not animation frames, when judging backlog.
    return max(0, len({cue.turn or cue.name for cue in cues[index : active + 1]}) - 1)


def compact(text: str) -> str:
    return "".join(text.split())


def percentiles(values: list[float]) -> dict:
    ordered = sorted(values)
    return (
        {
            "count": len(values),
            "p50": round(statistics.median(values), 3),
            "p95": round(ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))], 3),
        }
        if values
        else {"count": 0}
    )


class Server(ThreadingHTTPServer):
    daemon_threads = True
    requests: list[dict]
    delay = 0.12


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        user = json.loads(payload["messages"][-1]["content"])
        self.server.requests.append(
            {
                "at": time.monotonic(),
                "text": user["current_text"],
                "recent": len(user["previous_lines"]),
                "terms": len(user["glossary"]),
            }
        )
        time.sleep(self.server.delay)
        body = json.dumps(
            {"choices": [{"message": {"content": "Translated: " + user["current_text"]}}]}
        ).encode()
        try:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def log_message(self, *args):
        pass


class Capture:
    def __init__(self, cues: list[Cue], images: list[list[Image.Image]]):
        self.cues, self.images = cues, images
        self.origin = time.monotonic()
        self.playing = False

    def index_at(self, at: float) -> tuple[int, float]:
        elapsed, offset = max(0, at - self.origin), 0.0
        for index, cue in enumerate(self.cues):
            if elapsed < offset + cue.duration:
                return index, offset
            offset += cue.duration
        return len(self.cues) - 1, offset - self.cues[-1].duration

    def capture(self, region):
        index = self.index_at(time.monotonic())[0] if self.playing else 0
        frames = self.images[index]
        return frames[int(time.monotonic() * 5) % len(frames)].copy()

    def close(self):
        pass


def render(
    cues: list[Cue], language: str, vertical: bool, directory: Path
) -> list[list[Image.Image]]:
    images = []
    for index, cue in enumerate(cues):
        variants = []
        for phase in (0, 11, 22) if cue.moving else (0,):
            path = directory / f"{language}-{vertical}-{index}-{phase}.png"
            sample = dict(
                id=path.stem,
                language=language,
                text=cue.text,
                size=30,
                bg="#172736",
                fg="white",
                vertical=vertical,
                gradient=cue.moving,
                outline=not vertical,
                background_phase=phase,
            )
            sample.update(cue.sample or {})
            render_fixture(sample, path)
            with Image.open(path) as image:
                variants.append(image.convert("RGB"))
        images.append(variants)
    return images


def journey(
    app,
    models: Path,
    server: Server,
    name: str,
    language: str,
    vertical: bool,
    cues: list[Cue],
    images: list[list[Image.Image]],
) -> dict:
    server.delay = 1.8 if name == "slow-provider-freshness" else 0.12
    settings = Settings(
        source=language,
        quality="fast",
        vertical=vertical,
        recent_region=[0, 0, *images[0][0].size],
        reduced_motion=True,
    )
    capture = Capture(cues, images)
    pipeline = Pipeline(
        settings,
        lambda: capture,
        lambda: IsolatedOCR("rapidocr", language, models),
        lambda: create_provider(
            "custom", endpoint=f"http://127.0.0.1:{server.server_port}/v1", timeout=8
        ),
    )
    overlay = Overlay(settings)
    records, stages, checks = [], {}, {}
    first_request = len(server.requests)
    maximum = {"frames": 0, "texts": 0, "events": 0, "children": 0}
    cold = time.monotonic()
    pipeline.start()
    cold_ms = None
    try:
        deadline = cold + 35
        end = float("inf")
        while time.monotonic() < min(deadline, end):
            app.processEvents()
            maximum["frames"] = max(maximum["frames"], pipeline.frames.queue.qsize())
            maximum["texts"] = max(maximum["texts"], pipeline.texts.queue.qsize())
            maximum["events"] = max(maximum["events"], pipeline.events.qsize())
            maximum["children"] = max(maximum["children"], len(multiprocessing.active_children()))
            if pipeline.session.state == SessionState.ERROR:
                raise AssertionError("Paced pipeline entered an error state")
            for event in pipeline.poll():
                if not event.result:
                    continue
                before = time.monotonic()
                with pipeline.session.lock:
                    if event.stamp != Stamp(pipeline.session.serial, pipeline.session.generation):
                        raise AssertionError("A stale event reached presentation")
                    overlay.display(event.source, event.result.text)
                    pipeline.delivered_source = event.source
                app.processEvents()
                overlay.grab()
                presented = time.monotonic()
                if cold_ms is None:
                    cold_ms = (presented - cold) * 1000
                    capture.origin = presented
                    capture.playing = True
                    end = presented + sum(c.duration for c in cues)
                    deadline = end + 1
                    continue
                captured = event.created - event.timings["total_ms"] / 1000
                index, onset = capture.index_at(captured)
                active_index, _ = capture.index_at(presented)
                expected = compact(cues[index].text)
                error = distance(expected, compact(event.source)) / max(1, len(expected))
                row = {
                    "cue": cues[index].name,
                    "source": event.source,
                    "at_s": round(presented - capture.origin, 3),
                    "source_cer": round(error, 4),
                    "lag_cues": semantic_lag(cues, index, active_index),
                    "presentation_ms": (presented - captured) * 1000,
                    "onset_ms": (presented - capture.origin - onset) * 1000,
                    "replaces_source": event.replaces_source,
                }
                records.append(row)
                values = {
                    **event.timings,
                    "gui_delivery_ms": (before - event.created) * 1000,
                    "render_ms": (presented - before) * 1000,
                    "presentation_ms": row["presentation_ms"],
                    "onset_ms": row["onset_ms"],
                }
                for key, value in values.items():
                    stages.setdefault(key, []).append(value)
            time.sleep(0.008)
        if cold_ms is None:
            raise AssertionError("No cold primer result")
        required = {c.name for c in cues[1:] if c.required and c.text}
        delivered = {r["cue"] for r in records if r["source_cer"] <= 0.12}
        checks["required_dialogue_delivered"] = required <= delivered
        checks["freshness_no_backlog"] = all(r["lag_cues"] <= 1 for r in records)
        checks["bounded_work"] = (
            maximum["frames"] <= 1
            and maximum["texts"] <= 1
            and maximum["events"] <= 32
            and maximum["children"] <= 1
        )
        checks["no_wrong_source"] = all(r["source_cer"] <= 0.12 for r in records)
        progressive = [r for r in records if r["cue"].startswith("prefix")]
        checks["progressive_consolidated"] = len(progressive) <= 1
    finally:
        pipeline.stop()
        checks["workers_closed"] = pipeline.wait_closed(10)
        overlay.close()
    # Allow no post-stop receipt, context mutation, or surviving owned OCR child.
    checks["no_post_stop_results"] = not any(e.result for e in pipeline.poll())
    checks["no_remaining_children"] = not multiprocessing.active_children()
    return {
        "name": name,
        "language": language,
        "vertical": vertical,
        "checks": checks,
        "passed": all(checks.values()),
        "cold_first_presentation_ms": cold_ms,
        "warm_stage_ms": {k: percentiles(v) for k, v in stages.items()},
        "records": records,
        "missing": sorted(required - delivered),
        "max_pending": maximum,
        "counters": pipeline.counters,
        "http_requests": len(server.requests) - first_request,
    }


def qualify(models: Path) -> dict:
    manager = ModelManager(models)
    if not all(manager.installed(code, verify=True) for code in ("ja", "en")):
        raise ValueError("Verified local Japanese/English models required; no downloads")
    suites = [
        (
            "vn-moving-fade-return",
            "ja",
            False,
            [
                Cue("primer", "明日、またここで会おう。", 1, required=False),
                Cue("blank", "", 1.8, required=False),
                *[
                    Cue(f"prefix{i}", text, 0.12, moving=True, required=False, turn="vn-reveal")
                    for i, text in enumerate(["彼", "彼女", "彼女は", "彼女は昨日"])
                ],
                Cue("complete", "彼女は昨日ここに来た。", 4.5, moving=True, turn="vn-reveal"),
                Cue("outline", "ミカ、鍵を見つけた？", 4, moving=True),
                Cue(
                    "translucent", "彼女の名前はアウレリア。", 4, moving=True, sample={"alpha": 170}
                ),
                Cue("disappear", "", 1.8, required=False),
                Cue("return", "彼女は昨日ここに来た。", 4, moving=True),
                Cue("static", "明日、またここで会おう。", 4.2),
            ],
        ),
        (
            "brief-one-character-subtitles",
            "en",
            False,
            [
                Cue("primer", "Ready!", 1, required=False),
                Cue("blank", "", 1.5, required=False),
                Cue("me", "Wait for me!", 2, moving=True),
                Cue("us", "Wait for us!", 2, moving=True),
                Cue("go", "Go!", 2.8, moving=True),
                Cue("blank2", "", 1.5, required=False),
                Cue("return", "Go!", 3, moving=True),
            ],
        ),
        (
            "columns-ruby-captions",
            "ja",
            True,
            [
                Cue("primer", "明日また\n会おう", 1, required=False),
                Cue("blank", "", 2, required=False),
                Cue("columns", "アルトリア\n魔導炉", 5),
                Cue("ruby", "魔導炉\n明日の光", 5, sample={"ruby": "まどうろ"}),
                Cue(
                    "caption",
                    "ミカ：待って！\nアルトリア\n魔導炉",
                    5,
                    sample={"caption": "ミカ：待って！", "columns": ["アルトリア", "魔導炉"]},
                ),
            ],
        ),
        (
            "slow-provider-freshness",
            "en",
            False,
            [
                Cue("primer", "Ready!", 1, required=False),
                Cue("blank", "", 1.5, required=False),
                Cue("first", "The first line.", 2, moving=True, required=False),
                Cue("second", "A different line!", 2, moving=True, required=False),
                Cue("final", "The final line.", 5, moving=True),
            ],
        ),
    ]
    before = runtime_source_hashes(ROOT)
    rows = []
    server = Server(("127.0.0.1", 0), Handler)
    server.requests = []
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        with tempfile.TemporaryDirectory(prefix="desktranslate-paced-authored-") as directory:
            rendered = [
                render(cues, code, vertical, Path(directory)) for _, code, vertical, cues in suites
            ]
            app = QApplication.instance() or QApplication([])

            def forbidden(*args, **kwargs):
                raise AssertionError("Desktop access forbidden in paced qualification")

            with patch("mss.mss", forbidden), patch("PySide6.QtGui.QScreen.grabWindow", forbidden):
                for (name, code, vertical, cues), images in zip(suites, rendered, strict=True):
                    rows.append(journey(app, models, server, name, code, vertical, cues, images))
    finally:
        server.shutdown()
        server.server_close()
        worker.join(3)
    return {
        "version": __version__,
        "python_version": platform.python_version(),
        "source_hashes": before,
        "source_unchanged": before == runtime_source_hashes(ROOT),
        "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "scope": __doc__,
        "paced": True,
        "desktop_capture": False,
        "semantic_translation": False,
        "workloads": rows,
        "remaining_children": len(multiprocessing.active_children()),
        "passed": all(row["passed"] for row in rows) and before == runtime_source_hashes(ROOT),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--component-test", action="store_true")
    parser.add_argument("--models", type=Path, default=ROOT / ".test-data/models")
    parser.add_argument("--output", type=Path, default=ROOT / ".audit/media-pipeline.json")
    args = parser.parse_args()
    if not args.component_test:
        parser.error("Paced real OCR requires --component-test; excluded from routine validation")
    script = str(Path(__file__).resolve())
    if os.environ.get("DESKTRANSLATE_PACED_CHILD") != script:
        from qualification_policy import run_bounded_probe

        return run_bounded_probe(
            [sys.executable, script, *sys.argv[1:]],
            dict(os.environ, DESKTRANSLATE_PACED_CHILD=script),
            300,
            ROOT,
            "Paced media",
        )
    report = qualify(args.models.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "passed": report["passed"],
                "workloads": [
                    {"name": r["name"], "checks": r["checks"], "missing": r["missing"]}
                    for r in report["workloads"]
                ],
            }
        )
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
