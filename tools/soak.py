"""Opt-in two-hour native-resource soak using authored images and loopback HTTP only."""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing
import os
import statistics
import threading
import time
import tracemalloc
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PIL import Image
from PySide6.QtWidgets import QApplication

from desktranslate import __version__
from desktranslate.metrics import LatencyMetrics, process_resources
from desktranslate.models import Rect, SessionState
from desktranslate.ocr import IsolatedOCR, ModelManager
from desktranslate.pipeline import Pipeline
from desktranslate.providers import create_provider
from desktranslate.settings import Settings
from desktranslate.ui.overlay import Overlay

ROOT = Path(__file__).resolve().parents[1]


def resource_gate(samples: list[dict[str, object]], duration: float) -> dict[str, object]:
    """Declared regression budgets, after five minutes of allocator warmup."""
    stable = [sample for sample in samples if sample["elapsed_s"] >= 300]  # type: ignore[operator]
    if duration < 1800 or len(stable) < 20:
        return {
            "qualified": False,
            "reason": "At least 30 minutes and 20 post-warmup samples required",
        }
    early, late = stable[:10], stable[-10:]
    budgets = {
        "rss_bytes": 32 * 1024**2,
        "private_bytes": 32 * 1024**2,
        "handles": 32,
        "native_threads": 8,
    }
    growth = {}
    for key, limit in budgets.items():
        initial = statistics.median(sample["main"][key] for sample in early)  # type: ignore[index]
        final = statistics.median(sample["main"][key] for sample in late)  # type: ignore[index]
        growth[key] = {
            "initial_median": initial,
            "final_median": final,
            "growth": final - initial,
            "budget": limit,
            "passed": final - initial <= limit,
        }
    bounded = all(
        sample["subprocesses"] <= 1
        and sample["python_threads"] <= 12  # type: ignore[operator]
        and sample["frame_queue"] <= 1
        and sample["text_queue"] <= 1  # type: ignore[operator]
        and sample["event_queue"] <= 32
        and sample["cache_entries"] <= 256  # type: ignore[operator]
        and sample["context_pairs"] <= 8
        and sample["main"]["tcp_connections"] <= 8  # type: ignore[index,operator]
        for sample in stable
    )
    return {
        "qualified": bounded and all(value["passed"] for value in growth.values()),
        "bounded_collections_workers_sockets": bounded,
        "main_growth": growth,
    }


def source_hashes() -> dict[str, str]:
    return {
        name: hashlib.sha256((ROOT / "src/desktranslate" / name).read_bytes()).hexdigest()
        for name in (
            "pipeline.py",
            "ocr.py",
            "providers.py",
            "algorithms.py",
            "context.py",
            "models.py",
            "ui/overlay.py",
            "ui/subtitles.py",
        )
    }


class FixtureServer(ThreadingHTTPServer):
    daemon_threads = True
    request_count = 0
    fault_count = 0


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args: object) -> None:
        pass

    def do_POST(self) -> None:
        server: FixtureServer = self.server  # type: ignore[assignment]
        length = min(int(self.headers.get("Content-Length", "0")), 80_000)
        self.rfile.read(length)
        server.request_count += 1
        if server.request_count % 37 == 0:
            server.fault_count += 1
            self.send_response(500)
            body = b"{}"
        elif server.request_count % 29 == 0:
            server.fault_count += 1
            self.send_response(429)
            self.send_header("Retry-After", "1")
            body = b"{}"
        else:
            self.send_response(200)
            body = json.dumps(
                {"choices": [{"message": {"content": "A harmless sample translation."}}]}
            ).encode()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class FixtureCapture:
    def __init__(self, images: list[Image.Image]) -> None:
        self.images = images
        self.index = 0

    def capture(self, region: Rect) -> Image.Image:
        return self.images[self.index].copy()

    def close(self) -> None:
        pass


def run(duration: float, output: Path) -> None:
    if duration < 10:
        raise ValueError("Use at least ten seconds; stable qualification requires 7200.")
    if not ModelManager().installed("ja", verify=True):
        raise SystemExit(
            "Install the verified Japanese fixture models before running this opt-in test."
        )
    app = QApplication.instance() or QApplication([])
    settings = Settings(quality="fast", recent_region=[0, 0, 660, 160], reduced_motion=True)
    overlay = Overlay(settings)
    capture = FixtureCapture(
        [
            Image.open(ROOT / "tests/fixtures" / name).convert("RGB")
            for name in ("ja-game.png", "ja-multiline.png")
        ]
    )
    server = FixtureServer(("127.0.0.1", 0), Handler)
    server_thread = threading.Thread(target=server.serve_forever, name="soak-loopback", daemon=True)
    server_thread.start()
    endpoint = f"http://127.0.0.1:{server.server_port}/v1"

    def new_pipeline() -> Pipeline:
        pipeline = Pipeline(
            settings,
            lambda: capture,
            lambda: IsolatedOCR("rapidocr", "ja"),
            lambda: create_provider("custom", endpoint=endpoint, timeout=5),
        )
        pipeline.start()
        return pipeline

    baseline_hashes = source_hashes()
    pipeline = new_pipeline()
    tracemalloc.start()
    samples: list[dict[str, object]] = []
    counters: Counter[str] = Counter()
    latencies = LatencyMetrics(4096)
    errors: Counter[str] = Counter()
    started = time.monotonic()
    next_snapshot, next_restart, next_crash = 0.0, 300.0, 180.0
    accepted, restarts, max_queue = 0, 0, 0
    cancelled = False
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        while (elapsed := time.monotonic() - started) < duration:
            capture.index = int(elapsed // 4) % 2
            max_queue = max(max_queue, pipeline.events.qsize())
            for event in pipeline.poll():
                if event.category:
                    errors[event.category] += 1
                if event.result:
                    accepted += 1
                    before = time.perf_counter()
                    overlay.display(event.source, event.result.text)
                    app.processEvents()
                    overlay.grab()
                    latencies.observe(
                        {**event.timings, "overlay_paint_ms": (time.perf_counter() - before) * 1000}
                    )
            if elapsed >= next_crash and pipeline.ocr and hasattr(pipeline.ocr, "process"):
                pipeline.ocr.process.terminate()  # type: ignore[attr-defined]
                pipeline.reset_frames.set()
                next_crash += 900
            if elapsed >= next_restart or pipeline.session.state == SessionState.ERROR:
                counters.update(pipeline.counters)
                pipeline.stop()
                if not pipeline.wait_closed(10):
                    raise RuntimeError("Stopped workers did not exit within the cleanup budget")
                pipeline = new_pipeline()
                restarts += 1
                next_restart = elapsed + 300
            if elapsed >= next_snapshot:
                children = multiprocessing.active_children()
                heap, peak = tracemalloc.get_traced_memory()
                snapshot = {
                    "elapsed_s": round(elapsed, 2),
                    "main": process_resources(),
                    "workers": [process_resources(child.pid) for child in children if child.pid],
                    "subprocesses": len(children),
                    "python_threads": threading.active_count(),
                    "python_heap_bytes": heap,
                    "python_peak_bytes": peak,
                    "frame_queue": pipeline.frames.queue.qsize(),
                    "text_queue": pipeline.texts.queue.qsize(),
                    "event_queue": pipeline.events.qsize(),
                    "cache_entries": len(pipeline.cache.items),
                    "context_pairs": len(pipeline.context.snapshot()),
                }
                samples.append(snapshot)
                progress = {
                    "elapsed_s": round(elapsed, 1),
                    "duration_s": duration,
                    "accepted": accepted,
                    "restarts": restarts,
                    "samples": len(samples),
                }
                output.with_suffix(".progress.json").write_text(
                    json.dumps(progress, indent=2), encoding="utf-8"
                )
                next_snapshot += 30
            app.processEvents()
            time.sleep(0.02)
    except KeyboardInterrupt:
        cancelled = True
    finally:
        counters.update(pipeline.counters)
        pipeline.stop()
        closed = pipeline.wait_closed(10)
        server.shutdown()
        server.server_close()
        server_thread.join(2)
        overlay.close()
        elapsed = time.monotonic() - started
        report = {
            "version": __version__,
            "requested_duration_s": duration,
            "elapsed_s": round(elapsed, 2),
            "completed": not cancelled and elapsed >= duration and closed,
            "real_ocr": True,
            "synthetic_capture": True,
            "loopback_http": True,
            "source_unchanged": baseline_hashes == source_hashes(),
            "source_hashes": baseline_hashes,
            "accepted": accepted,
            "session_restarts": restarts,
            "injected_http_faults": server.fault_count,
            "http_requests": server.request_count,
            "errors": dict(errors),
            "counters": dict(counters),
            "max_event_queue": max_queue,
            "latency_ms": latencies.snapshot(),
            "samples": samples,
            "workers_closed": closed,
            "remaining_children": len(multiprocessing.active_children()),
            "final_resources": process_resources(),
            "resource_qualification": resource_gate(samples, duration),
        }
        report["workload_passed"] = bool(
            report["completed"]
            and report["source_unchanged"]
            and accepted >= max(1, int(duration / 12))
            and server.request_count > 0
            and report["remaining_children"] == 0
        )
        output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(
            json.dumps(
                {
                    key: report[key]
                    for key in (
                        "completed",
                        "elapsed_s",
                        "accepted",
                        "source_unchanged",
                        "workers_closed",
                        "remaining_children",
                    )
                }
            )
        )


if __name__ == "__main__":
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=float, default=7200)
    parser.add_argument("--output", type=Path, default=Path("docs/soak-2h.json"))
    args = parser.parse_args()
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    run(args.duration, args.output)
