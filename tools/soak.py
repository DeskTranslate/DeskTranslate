"""Opt-in two-hour native-resource soak using authored images and loopback HTTP only."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import multiprocessing
import os
import platform
import statistics
import threading
import time
import tracemalloc
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont
from PySide6.QtWidgets import QApplication
from release_support import runtime_source_hashes

from desktranslate import __version__
from desktranslate.metrics import LatencyMetrics, process_resources
from desktranslate.models import Rect, SessionState, Stamp
from desktranslate.ocr import IsolatedOCR, ModelManager
from desktranslate.pipeline import Pipeline
from desktranslate.providers import create_provider
from desktranslate.settings import Settings, SettingsStore
from desktranslate.ui.overlay import Overlay
from desktranslate.ui.theme import apply_theme

ROOT = Path(__file__).resolve().parents[1]


def command_passed(report: dict[str, object]) -> bool:
    """Completed long runs must fail the command when resource gates fail."""
    if report.get("workload_passed") is not True:
        return False
    duration = float(report["requested_duration_s"])  # type: ignore[arg-type]
    if duration >= 1800:
        resources = report.get("resource_qualification")
        if not isinstance(resources, dict) or resources.get("qualified") is not True:
            return False
    if report.get("mode") == "steady" and duration >= 7200:
        worker = report.get("continuous_worker_qualification")
        if not isinstance(worker, dict) or worker.get("qualified") is not True:
            return False
    return True


def child_resources() -> list[dict[str, object]]:
    """Snapshot IDs once; an OCR worker may be reaped during sampling."""
    resources = []
    for child in multiprocessing.active_children():
        try:
            pid = child.pid
        except ValueError:
            continue
        if pid is not None:
            resources.append({"pid": pid, **process_resources(pid)})
    return resources


def observation_gate(samples: list[dict[str, object]], duration: float) -> dict[str, object]:
    """Wall time without observations cannot establish continuous endurance."""
    times = [sample.get("elapsed_s") for sample in samples]
    if (
        not times
        or not math.isfinite(duration)
        or any(type(value) not in (int, float) or not math.isfinite(value) for value in times)
    ):
        return {"qualified": False, "reason": "Sampling timestamps unavailable or invalid"}
    gaps = [later - earlier for earlier, later in zip(times, times[1:], strict=False)]
    start_gap = times[0]
    end_gap = duration - times[-1]
    longest = max([start_gap, end_gap, *gaps])
    return {
        "qualified": start_gap >= 0
        and end_gap >= 0
        and longest <= 90
        and all(gap > 0 for gap in gaps),
        "reason": "All observation gaps, including start/end, must be at most 90 seconds",
        "max_gap_s": round(longest, 3),
        "end_gap_s": round(end_gap, 3),
        "observed_span_s": round(times[-1] - times[0], 3),
    }


def resource_gate(samples: list[dict[str, object]], duration: float) -> dict[str, object]:
    """Declared regression budgets, after five minutes of allocator warmup."""
    observation = observation_gate(samples, duration)
    if not observation["qualified"]:
        return {
            "qualified": False,
            "reason": "Sampling coverage incomplete",
            "observation": observation,
        }
    stable = [sample for sample in samples if sample["elapsed_s"] >= 300]  # type: ignore[operator]
    if duration < 1800 or len(stable) < 20:
        return {
            "qualified": False,
            "reason": "At least 30 minutes and 20 post-warmup samples required",
        }
    for sample in stable:
        main = sample.get("main")
        if not isinstance(main, dict) or any(
            type(main.get(key)) not in (int, float)
            or not math.isfinite(main[key])
            or main[key] < (1 if key == "native_threads" else 0)
            for key in (
                "rss_bytes",
                "private_bytes",
                "handles",
                "native_threads",
                "tcp_connections",
            )
        ):
            return {
                "qualified": False,
                "reason": "Required native resource measurement unavailable or invalid",
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
    heaps = [sample.get("python_heap_bytes") for sample in stable]
    if any(type(heap) is not int or heap < 0 for heap in heaps):
        return {"qualified": False, "reason": "Python allocation measurement unavailable"}
    heap_growth = statistics.median(heaps[-10:]) - statistics.median(heaps[:10])
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
        "qualified": bounded
        and heap_growth <= 16 * 1024**2
        and all(value["passed"] for value in growth.values()),
        "bounded_collections_workers_sockets": bounded,
        "main_growth": growth,
        "python_heap_growth": {"bytes": heap_growth, "budget": 16 * 1024**2},
    }


def continuous_worker_gate(samples: list[dict[str, object]], duration: float) -> dict[str, object]:
    """A restart cannot hide a leaking native engine in the steady workload."""
    observation = observation_gate(samples, duration)
    if not observation["qualified"]:
        return {
            "qualified": False,
            "reason": "Sampling coverage incomplete",
            "observation": observation,
        }
    stable = [sample for sample in samples if sample["elapsed_s"] >= 300]
    if duration < 7200 or len(stable) < 200:
        return {"qualified": False, "reason": "Two hours and 200 post-warmup samples required"}
    workers = []
    for sample in stable:
        rows = sample.get("workers")
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
            return {"qualified": False, "reason": "Exactly one continuous OCR worker required"}
        worker = rows[0]
        if any(
            type(worker.get(key)) not in (int, float)
            or not math.isfinite(worker[key])
            or worker[key] < (1 if key in {"pid", "native_threads"} else 0)
            for key in (
                "pid",
                "rss_bytes",
                "private_bytes",
                "handles",
                "native_threads",
                "cpu_seconds",
            )
        ):
            return {"qualified": False, "reason": "Native child resource measurement unavailable"}
        workers.append(worker)
    if len({worker["pid"] for worker in workers}) != 1:
        return {"qualified": False, "reason": "OCR worker restarted during steady measurement"}
    growth = {}
    for key, budget in {
        "rss_bytes": 64 * 1024**2,
        "private_bytes": 64 * 1024**2,
        "handles": 16,
        "native_threads": 4,
    }.items():
        initial = statistics.median(worker[key] for worker in workers[:10])
        final = statistics.median(worker[key] for worker in workers[-10:])
        growth[key] = {
            "initial_median": initial,
            "final_median": final,
            "growth": final - initial,
            "budget": budget,
            "passed": final - initial <= budget,
        }
    return {
        "qualified": all(row["passed"] for row in growth.values()),
        "pid": workers[0]["pid"],
        "observed_span_s": stable[-1]["elapsed_s"] - stable[0]["elapsed_s"],
        "child_growth": growth,
    }


def source_hashes() -> dict[str, str]:
    return runtime_source_hashes(ROOT)


class FixtureServer(ThreadingHTTPServer):
    daemon_threads = True
    request_count = 0
    fault_count = 0
    faults = False

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.stopping = threading.Event()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args: object) -> None:
        pass

    def do_POST(self) -> None:
        server: FixtureServer = self.server  # type: ignore[assignment]
        length = min(int(self.headers.get("Content-Length", "0")), 80_000)
        self.rfile.read(length)
        server.request_count += 1
        if server.faults and server.request_count % 17 == 0:
            server.fault_count += 1
            return  # Disconnect before headers.
        if server.faults and server.request_count % 13 == 0:
            server.fault_count += 1
            if server.stopping.wait(6):
                return  # Exercise slow headers / timeout / cancellation.
        if server.faults and server.request_count % 11 == 0:
            server.fault_count += 1
            self.send_response(500)
            body = b"{}"
        elif server.faults and server.request_count % 7 == 0:
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
        try:
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass


class FixtureCapture:
    def __init__(self) -> None:
        self.images = []
        for name in ("ja-game", "ja-katakana-pixel", "ja-columns-mixed", "ja-columns-ruby"):
            with Image.open(ROOT / "tests/fixtures" / (name + ".png")) as source:
                canvas = Image.new("RGB", (660, 260), "#14262e")
                canvas.paste(source.convert("RGB"), (0, 0))
                self.images.append(canvas)
        self.image = self.images[0]
        self.font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 24)
        self.started = time.monotonic()
        self.previous = -1
        self.current = self.image
        self.phase = "starting"

    def capture(self, region: Rect) -> Image.Image:
        elapsed = time.monotonic() - self.started
        # One minute of genuinely static capture per five minutes. Active phase
        # has new authored text, disappearance, and continuously moving pixels.
        if elapsed % 300 < 60:
            sequence, self.phase = 0, "static"
        else:
            sequence, self.phase = int(elapsed // 12), "active"
            if elapsed % 12 < 2:
                return Image.new("RGB", self.image.size, "#14262e")
        if sequence != self.previous:
            self.current = self.images[sequence % len(self.images)].copy()
            ImageDraw.Draw(self.current).text(
                (24, 224), f"Sequence {sequence:04d}", font=self.font, fill="white"
            )
            self.previous = sequence
        if self.phase == "active" and elapsed % 12 > 7:
            return ImageEnhance.Brightness(self.current).enhance(
                0.65 + 0.3 * (int(elapsed * 5) % 4)
            )
        return self.current.copy()

    def close(self) -> None:
        pass


def run(duration: float, output: Path, mode: str = "steady", stop_file: Path | None = None) -> bool:
    if duration < 10:
        raise ValueError("Use at least ten seconds; stable qualification requires 7200.")
    if not all(ModelManager().installed(language, verify=True) for language in ("ja", "en")):
        raise SystemExit(
            "Install the verified Japanese fixture models before running this opt-in test."
        )
    app = QApplication.instance() or QApplication([])
    settings = Settings(
        quality="fast", recent_region=[0, 0, 660, 260], reduced_motion=True, vertical=True
    )
    apply_theme(app, settings.theme)
    overlay = Overlay(settings)
    capture = FixtureCapture()
    server = FixtureServer(("127.0.0.1", 0), Handler)
    server.faults = mode == "chaos"
    server_thread = threading.Thread(target=server.serve_forever, name="soak-loopback", daemon=True)
    server_thread.start()
    endpoint = f"http://127.0.0.1:{server.server_port}/v1"

    def new_pipeline() -> Pipeline:
        pipeline = Pipeline(
            settings,
            lambda: capture,
            lambda: IsolatedOCR("rapidocr", settings.source),
            lambda: create_provider("custom", endpoint=endpoint, timeout=2),
        )
        pipeline.start()
        return pipeline

    baseline_hashes = source_hashes()
    baseline_harness = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    pipeline = new_pipeline()
    tracemalloc.start()
    samples: list[dict[str, object]] = []
    counters: Counter[str] = Counter()
    latencies = LatencyMetrics(4096)
    errors: Counter[str] = Counter()
    started = time.monotonic()
    next_snapshot, next_restart, next_crash, next_pause = 0.0, 180.0, 150.0, 65.0
    accepted, restarts, max_queue = 0, 0, 0
    cancelled = False
    failure = ""
    pending_cancellations = []
    cancellation_ms = []
    source_store = SettingsStore(output.parent / (output.stem + "-authored-settings"))
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        while (elapsed := time.monotonic() - started) < duration:
            if stop_file is not None and stop_file.exists():
                cancelled = True
                break
            max_queue = max(max_queue, pipeline.events.qsize())
            for event in pipeline.poll():
                if event.category:
                    errors[event.category] += 1
                if event.result:
                    before = time.perf_counter()
                    with pipeline.session.lock:
                        if event.stamp != Stamp(
                            pipeline.session.serial, pipeline.session.generation
                        ):
                            continue
                        overlay.display(event.source, event.result.text)
                        pipeline.delivered_source = event.source
                        accepted += 1
                    app.processEvents()
                    overlay.grab()
                    latencies.observe(
                        {**event.timings, "overlay_paint_ms": (time.perf_counter() - before) * 1000}
                    )
            if (
                mode == "chaos"
                and elapsed >= next_crash
                and pipeline.ocr
                and hasattr(pipeline.ocr, "process")
            ):
                pipeline.ocr.process.terminate()  # type: ignore[attr-defined]
                pipeline.reset_frames.set()
                next_crash += 180
            if mode == "chaos" and elapsed >= next_pause:
                for _ in range(4):
                    before = time.monotonic()
                    if pipeline.ocr and hasattr(pipeline.ocr, "process"):
                        pending_cancellations.append((before, pipeline.ocr.process))
                    pipeline.pause()
                    app.processEvents()
                    pipeline.resume()
                next_pause += 60
            for before, process in pending_cancellations[:]:
                try:
                    alive = process.is_alive()
                except ValueError:
                    alive = False
                if not alive:
                    cancellation_ms.append((time.monotonic() - before) * 1000)
                    pending_cancellations.remove((before, process))
                elif time.monotonic() - before > 5:
                    raise RuntimeError("OCR cancellation exceeded five seconds")
            if pipeline.session.state == SessionState.ERROR and mode == "steady":
                raise RuntimeError("Steady workload unexpectedly failed")
            if mode == "chaos" and (
                elapsed >= next_restart or pipeline.session.state == SessionState.ERROR
            ):
                counters.update(pipeline.counters)
                pipeline.stop()
                if not pipeline.wait_closed(10):
                    raise RuntimeError("Stopped workers did not exit within the cleanup budget")
                restarts += 1
                settings.source = "en" if restarts % 2 else "ja"
                settings.vertical = settings.source == "ja"
                settings.profiles["Authored stress profile"] = {
                    "source": settings.source,
                    "target": "es",
                }
                source_store.save(settings)
                settings = source_store.load()
                overlay.configure(settings)
                overlay.toggle_visibility()
                pipeline = new_pipeline()
                next_restart = elapsed + 180
            if elapsed >= next_snapshot:
                workers = child_resources()
                heap, peak = tracemalloc.get_traced_memory()
                snapshot = {
                    "elapsed_s": round(elapsed, 2),
                    "phase": capture.phase,
                    "main": process_resources(),
                    "workers": workers,
                    "subprocesses": len(workers),
                    "python_threads": threading.active_count(),
                    "python_heap_bytes": heap,
                    "python_peak_bytes": peak,
                    "frame_queue": pipeline.frames.queue.qsize(),
                    "text_queue": pipeline.texts.queue.qsize(),
                    "event_queue": pipeline.events.qsize(),
                    "cache_entries": len(pipeline.cache.items),
                    "context_pairs": len(pipeline.context.snapshot()),
                    "counters": dict(pipeline.counters),
                    "pending_provider": int(
                        bool(pipeline.provider and getattr(pipeline.provider, "pending", None))
                    ),
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
                output.with_suffix(".partial.json").write_text(
                    json.dumps(
                        {
                            "version": __version__,
                            "mode": mode,
                            "completed": False,
                            "elapsed_s": elapsed,
                            "source_hashes": baseline_hashes,
                            "samples": samples,
                        }
                    ),
                    encoding="utf-8",
                )
                next_snapshot += 30
            app.processEvents()
            time.sleep(0.02)
    except KeyboardInterrupt:
        cancelled = True
    except Exception as error:
        failure = type(error).__name__
    finally:
        counters.update(pipeline.counters)
        pipeline.stop()
        closed = pipeline.wait_closed(10)
        server.stopping.set()
        server.shutdown()
        server.server_close()
        server_thread.join(2)
        overlay.close()
        elapsed = time.monotonic() - started
        report = {
            "version": __version__,
            "python_version": platform.python_version(),
            "requested_duration_s": duration,
            "elapsed_s": round(elapsed, 2),
            "completed": not cancelled and not failure and elapsed >= duration and closed,
            "mode": mode,
            "failure_category": failure,
            "real_ocr": True,
            "synthetic_capture": True,
            "loopback_http": True,
            "source_unchanged": baseline_hashes == source_hashes(),
            "source_hashes": baseline_hashes,
            "harness_sha256": baseline_harness,
            "harness_unchanged": baseline_harness
            == hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "accepted": accepted,
            "session_restarts": restarts,
            "injected_http_faults": server.fault_count,
            "http_requests": server.request_count,
            "errors": dict(errors),
            "counters": dict(counters),
            "max_event_queue": max_queue,
            "latency_ms": latencies.snapshot(),
            "cancellation_ms": {
                "count": len(cancellation_ms),
                "median": statistics.median(cancellation_ms) if cancellation_ms else None,
                "p95": sorted(cancellation_ms)[
                    min(len(cancellation_ms) - 1, math.ceil(len(cancellation_ms) * 0.95) - 1)
                ]
                if cancellation_ms
                else None,
            },
            "samples": samples,
            "workers_closed": closed,
            "remaining_children": len(multiprocessing.active_children()),
            "final_resources": process_resources(),
            "resource_qualification": resource_gate(samples, elapsed),
            "observation_coverage": observation_gate(samples, elapsed),
            "continuous_worker_qualification": continuous_worker_gate(samples, elapsed)
            if mode == "steady"
            else {"qualified": False, "reason": "NOT APPLICABLE to restart workload"},
            "measurement_scope": "Authored synthetic capture, real isolated CPU OCR, real loopback HTTP and Qt overlay. Not physical monitor or real media qualification.",
        }
        report["workload_passed"] = bool(
            report["completed"]
            and report["source_unchanged"]
            and report["harness_unchanged"]
            and accepted >= max(1, int(max(0, duration - 60) / 30))
            and server.request_count > 0
            and report["remaining_children"] == 0
        )
        report["rates_per_minute"] = {
            name: round(count * 60 / elapsed, 3) for name, count in counters.items()
        }
        cpu = {"active": [], "static": []}
        for previous, current in zip(samples, samples[1:], strict=False):
            if previous["phase"] != current["phase"] or current["phase"] not in cpu:
                continue
            delta = current["elapsed_s"] - previous["elapsed_s"]
            rows = [previous["main"], current["main"]]
            if all(type(row.get("cpu_seconds")) in (int, float) for row in rows):
                cpu[current["phase"]].append(
                    100 * (rows[1]["cpu_seconds"] - rows[0]["cpu_seconds"]) / delta
                )
        report["main_cpu_percent_one_core"] = {
            phase: {"median": statistics.median(values) if values else None, "samples": len(values)}
            for phase, values in cpu.items()
        }
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
    return command_passed(report)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--duration",
        type=float,
        default=60,
        help="Seconds of background fixture work (default60; no desktop capture or playback)",
    )
    parser.add_argument(
        "--long-running",
        action="store_true",
        help="Explicitly opt into at least30min of CPU/RAM stress; excluded from routine validation",
    )
    parser.add_argument("--output", type=Path, default=Path("docs/soak-2h.json"))
    parser.add_argument("--mode", choices=["steady", "chaos"], default="steady")
    parser.add_argument(
        "--stop-file",
        type=Path,
        help="Stop cooperatively and retain the incomplete report when this file appears",
    )
    args = parser.parse_args()
    if args.duration >= 1800 and not args.long_running:
        parser.error("Extended stress requires --long-running and a --stop-file")
    if args.duration >= 1800 and args.stop_file is None:
        parser.error("Extended stress requires --stop-file for cooperative interruption")
    # Never inherit a foreground backend from a developer's interactive Qt work.
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    raise SystemExit(0 if run(args.duration, args.output, args.mode, args.stop_file) else 1)
