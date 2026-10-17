from __future__ import annotations

import asyncio
import contextlib
import copy
import csv
import hashlib
import io
import json
import multiprocessing as mp
import os
import shutil
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from threading import Event, Lock
from typing import Any

import httpx
from PIL import Image

from desktranslate.algorithms import reconstruct
from desktranslate.errors import (
    Cancelled,
    OCRInferenceError,
    OCRInitializationError,
    OCRLanguageMissingError,
)
from desktranslate.languages import REGISTRY
from desktranslate.layout import (
    from_counterclockwise,
    japanese_word_region,
    resolve_layout,
    uncovered_lines,
)
from desktranslate.models import OCRLine, OCRResult, Rect
from desktranslate.network import identity_chunks, run_cancellable
from desktranslate.settings import data_dir

INSTALL_LOCK = Lock()
MODEL_TIMEOUT = 180.0


def detector_size(width: int, height: int, short_side: int = 736) -> tuple[int, int]:
    """Preserve the pinned detector's scaling, but bound extreme aspect ratios.

    RapidOCR first limits the input's long side, then enlarges its short side
    to 736 again. A thin ultrawide region can therefore produce a huge tensor.
    Keep its existing integer/32-pixel rounding for ordinary subtitle regions.
    """
    ratio = max(1.0, short_side / min(width, height))
    resized = tuple(int(round(int(side * ratio) / 32) * 32) for side in (width, height))
    if max(resized) <= 4096:
        return resized[0], resized[1]
    ratio = 4096 / max(width, height)
    bounded = tuple(max(32, int(round(int(side * ratio) / 32) * 32)) for side in (width, height))
    return bounded[0], bounded[1]


def bounded_detector_preprocess(limit: int, kind: str, mean: Any, std: Any) -> Any:
    # This adapter is intentionally local to our pinned RapidOCR instance.
    # Its normalizer and box mapping remain the upstream implementation.
    import cv2
    from rapidocr.ch_ppocr_det.utils import DetPreProcess

    class BoundedPreprocess(DetPreProcess):
        def resize(self, image: Any) -> Any:
            if self.limit_type != "min":
                return super().resize(image)
            height, width = image.shape[:2]
            dimensions = detector_size(width, height, self.limit_side_len)
            if max(dimensions) < 4096:
                return super().resize(image)
            return cv2.resize(image, dimensions)

    return BoundedPreprocess(limit, kind, mean, std)


def manifest() -> dict[str, dict[str, Any]]:
    return json.loads((Path(__file__).parent / "assets/models.json").read_text(encoding="utf-8"))


class ModelManager:
    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory or data_dir() / "models"
        self.catalog = manifest()

    def required(self, language: str) -> list[str]:
        if language not in REGISTRY or not REGISTRY[language].recognition:
            raise OCRLanguageMissingError(
                "This language requires optional Tesseract recognition. Choose a managed source language or configure Tesseract."
            )
        return ["det", "cls", REGISTRY[language].recognition] + (
            ["japan_regional"] if language == "ja" else []
        )

    def path(self, model: str) -> Path:
        return self.directory / self.catalog[model]["filename"]

    def installed(self, language: str, verify: bool = False) -> bool:
        return all(
            self.path(m).is_file() and (not verify or self.valid(m))
            for m in self.required(language)
        )

    def valid(self, model: str) -> bool:
        path = self.path(model)
        if not path.is_file():
            return False
        if path.stat().st_size > 100_000_000:
            return False
        expected_size = self.catalog[model].get("bytes")
        if type(expected_size) is int and path.stat().st_size != expected_size:
            return False
        with path.open("rb") as stream:
            return (
                hashlib.file_digest(stream, "sha256").hexdigest() == self.catalog[model]["sha256"]
            )

    def install(
        self, language: str, cancel: Event, progress: Callable[[str, int, int], None]
    ) -> None:
        while not INSTALL_LOCK.acquire(timeout=0.1):
            if cancel.is_set():
                raise Cancelled()
        try:
            self._install(language, cancel, progress)
        except OSError:
            raise OCRInitializationError(
                "The language pack could not be written. Check free disk space and folder permissions, then retry."
            ) from None
        finally:
            INSTALL_LOCK.release()

    def _install(
        self, language: str, cancel: Event, progress: Callable[[str, int, int], None]
    ) -> None:
        try:
            run_cancellable(
                lambda: self._install_async(language, cancel, progress),
                cancel,
                MODEL_TIMEOUT * len(self.required(language)),
            )
        except TimeoutError:
            raise OCRInitializationError(
                "The language pack download took too long. Retry on a stable connection."
            ) from None
        except (httpx.HTTPError, ValueError):
            raise OCRInitializationError(
                "Cannot download recognition models. Check your connection, then retry."
            ) from None

    async def _install_async(
        self, language: str, cancel: Event, progress: Callable[[str, int, int], None]
    ) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(15.0, connect=5),
            follow_redirects=False,
            headers={"Accept-Encoding": "identity"},
        ) as client:
            for model in self.required(language):
                if self.valid(model):
                    continue
                info = self.catalog[model]
                target = self.path(model)
                partial = target.with_suffix(".part")
                url = info["url"]
                try:
                    async with asyncio.timeout(MODEL_TIMEOUT):
                        for _ in range(6):
                            if cancel.is_set():
                                raise Cancelled()
                            async with client.stream("GET", url) as response:
                                if response.is_redirect:
                                    next_url = str(response.url.join(response.headers["location"]))
                                    if not next_url.startswith("https://"):
                                        raise OCRInitializationError(
                                            "Model download requires HTTPS."
                                        )
                                    url = next_url
                                    continue
                                response.raise_for_status()
                                try:
                                    total = int(response.headers.get("Content-Length", 0))
                                except ValueError:
                                    total = 0
                                if not 0 <= total <= 100_000_000:
                                    raise OCRInitializationError(
                                        "Invalid language pack download size."
                                    )
                                digest = hashlib.sha256()
                                downloaded = 0
                                with partial.open("wb") as stream:
                                    async for chunk in identity_chunks(response):
                                        if cancel.is_set():
                                            raise Cancelled()
                                        downloaded += len(chunk)
                                        if downloaded > 100_000_000:
                                            raise OCRInitializationError(
                                                "Model download exceeded the size limit."
                                            )
                                        stream.write(chunk)
                                        digest.update(chunk)
                                        progress(model, downloaded, total)
                                progress("verifying:" + model, downloaded, downloaded)
                                if digest.hexdigest() != info["sha256"]:
                                    raise OCRInitializationError(
                                        "Model verification failed. Retry the download."
                                    )
                                os.replace(partial, target)
                                progress("installed:" + model, downloaded, downloaded)
                                break
                        else:
                            raise OCRInitializationError("Too many model download redirects.")
                finally:
                    partial.unlink(missing_ok=True)


class RapidEngine:
    def __init__(self, language: str, directory: Path | None = None) -> None:
        manager = ModelManager(directory)
        if not manager.installed(language, verify=True):
            raise OCRLanguageMissingError()
        import onnxruntime

        onnxruntime.disable_telemetry_events()
        from rapidocr import LangDet, LangRec, ModelType, OCRVersion, RapidOCR

        self.engine = RapidOCR(
            params={
                "Global.log_level": "critical",
                "Global.model_root_dir": str(manager.directory),
                "Det.model_path": str(manager.path("det")),
                "Det.ocr_version": OCRVersion.PPOCRV4,
                "Det.model_type": ModelType.MOBILE,
                "Det.lang_type": LangDet.CH,
                "Cls.model_path": str(manager.path("cls")),
                "Rec.model_path": str(manager.path(REGISTRY[language].recognition)),
                "Rec.ocr_version": OCRVersion.PPOCRV5
                if "PP-OCRv5" in manager.path(REGISTRY[language].recognition).name
                else OCRVersion.PPOCRV4,
                "Rec.model_type": ModelType.MOBILE,
                "Rec.lang_type": LangRec(REGISTRY[language].recognition),
                "EngineConfig.onnxruntime.intra_op_num_threads": 2,
                "EngineConfig.onnxruntime.inter_op_num_threads": 1,
            }
        )
        # RapidOCR's raster visualizer wants visual-order RTL strings. Qt and
        # translation APIs require the original logical Unicode order instead.
        # Limit this override to our recognizer instance; never patch the library.
        self.engine.text_rec.RTL_LANGS = set()
        detector: Any = self.engine.text_det
        detector.get_preprocess = lambda _max_wh: bounded_detector_preprocess(
            detector.limit_side_len, detector.limit_type, detector.mean, detector.std
        )
        self.regional_model = manager.path("japan_regional") if language == "ja" else None
        self.regional_recognizer: Any = None

    def recognize_regions(
        self, image: Image.Image, regions: tuple[tuple[Rect, bool], ...]
    ) -> tuple[OCRLine, ...]:
        import numpy as np
        from rapidocr import ModelType, OCRVersion
        from rapidocr.ch_ppocr_rec.main import TextRecognizer
        from rapidocr.ch_ppocr_rec.typings import TextRecInput

        if (
            not regions
            or self.regional_model is None
            or len(regions) > 256
            or sum(box.width * box.height for box, _ in regions) > image.width * image.height * 2
        ):
            return ()
        if self.regional_recognizer is None:
            config = copy.deepcopy(self.engine.cfg.Rec)
            config.model_path = str(self.regional_model)
            config.ocr_version = OCRVersion.PPOCRV6
            config.model_type = ModelType.SMALL
            config.lang_type = "multi"
            self.regional_recognizer = TextRecognizer(config)
            self.regional_recognizer.RTL_LANGS = set()
        crops = []
        for box, vertical in regions:
            crop = image.crop(
                (
                    max(0, box.x - 2),
                    max(0, box.y - 2),
                    min(image.width, box.right + 2),
                    min(image.height, box.bottom + 2),
                )
            )
            if vertical:
                crop = crop.transpose(Image.Transpose.ROTATE_90)
            crops.append(np.asarray(crop)[:, :, ::-1])
        result = self.regional_recognizer(TextRecInput(img=crops))
        if result.txts is None or result.scores is None:
            return ()
        return tuple(
            OCRLine(text, box, float(score))
            for (box, _), text, score in zip(regions, result.txts, result.scores, strict=True)
            if text.strip() and score >= self.engine.text_score
        )

    def refine_horizontal(
        self, image: Image.Image, original: tuple[OCRLine, ...]
    ) -> tuple[OCRLine, ...]:
        selected = tuple((line.box, False) for line in original if japanese_word_region(line))
        replacements = {line.box: line for line in self.recognize_regions(image, selected)}
        return tuple(replacements.get(line.box, line) for line in original)

    def vertical_layout(
        self, image: Image.Image, original: tuple[OCRLine, ...]
    ) -> tuple[str | None, tuple[OCRLine, ...], tuple[OCRLine, ...], dict[str, float]]:
        import numpy as np

        start = time.perf_counter()
        # The alternate orientation locates columns only. Horizontal regions
        # retain their own upright pixels; the whole frame is never translated
        # as if every region had the same orientation.
        detected: Any = self.engine(
            np.asarray(image.transpose(Image.Transpose.ROTATE_90))[:, :, ::-1],
            use_cls=False,
            use_rec=False,
        )
        columns: list[Rect] = []
        for points in detected.boxes if detected.boxes is not None else ():
            left, top = int(min(p[0] for p in points)), int(min(p[1] for p in points))
            right, bottom = int(max(p[0] for p in points)), int(max(p[1] for p in points))
            box = from_counterclockwise(
                Rect(left, top, max(1, right - left), max(1, bottom - top)),
                image.width,
                image.height,
            )
            # A single upright glyph has no reliable orientation. Leave it on
            # the normal path rather than guessing or discarding short text.
            if box and box.height >= box.width * 2 and box not in columns:
                columns.append(box)
        timings = {"ocr_layout_detect_ms": (time.perf_counter() - start) * 1000}
        if not columns or self.regional_model is None:
            return None, original, (), timings
        horizontal = uncovered_lines(original, tuple(columns))
        regions = tuple(columns) + tuple(line.box for line in horizontal)
        start = time.perf_counter()
        recognized = self.recognize_regions(
            image, tuple((box, index < len(columns)) for index, box in enumerate(regions))
        )
        timings["ocr_layout_recognize_ms"] = (time.perf_counter() - start) * 1000
        vertical = tuple(line for line in recognized if line.box in columns)
        if not vertical:
            return None, original, (), timings
        replacements = {line.box: line for line in recognized if line.box not in columns}
        horizontal = tuple(
            replacements.get(line.box, line)
            for line in uncovered_lines(original, tuple(line.box for line in vertical))
        )
        text, body, annotations = resolve_layout(horizontal, vertical)
        return text, body, annotations, timings

    def recognize(self, image: Image.Image, language: str, vertical: bool = False) -> OCRResult:
        import numpy as np

        start = time.perf_counter()
        # Screens are already upright. The document angle classifier can rotate
        # valid Hangul subtitles by 180 degrees, destroying otherwise accurate OCR.
        result: Any = self.engine(np.asarray(image)[:, :, ::-1], use_cls=False, use_rec=True)
        stages = getattr(result, "elapse_list", None) or []
        lines = []
        if result.boxes is not None:
            for box, text, score in zip(result.boxes, result.txts, result.scores, strict=True):
                left, top = int(min(p[0] for p in box)), int(min(p[1] for p in box))
                right, bottom = int(max(p[0] for p in box)), int(max(p[1] for p in box))
                lines.append(
                    OCRLine(
                        text,
                        Rect(left, top, max(1, right - left), max(1, bottom - top)),
                        float(score),
                    )
                )
        output = tuple(lines)
        layout_text = None
        layout_timings: dict[str, float] = {}
        annotations: tuple[OCRLine, ...] = ()
        if vertical and language == "ja":
            layout_text, output, annotations, layout_timings = self.vertical_layout(image, output)
        if language == "ja" and layout_text is None:
            regional_start = time.perf_counter()
            output = self.refine_horizontal(image, output)
            layout_timings["ocr_regional_ms"] = (time.perf_counter() - regional_start) * 1000
        confidence = sum(line.confidence for line in output) / len(output) if output else 0.0
        reconstruct_start = time.perf_counter()
        text = (
            layout_text
            if layout_text is not None
            else reconstruct(output, vertical, REGISTRY[language].direction)
        )
        return OCRResult(
            text,
            output,
            confidence,
            language,
            (time.perf_counter() - start) * 1000,
            {
                **layout_timings,
                **{
                    name: float(value) * 1000
                    for name, value in zip(
                        ("ocr_detect_ms", "ocr_classify_ms", "ocr_recognize_ms"),
                        stages,
                        strict=False,
                    )
                    if isinstance(value, (int, float))
                },
                "ocr_reconstruct_ms": (time.perf_counter() - reconstruct_start) * 1000,
            },
            annotations,
        )

    def close(self) -> None:
        pass


class TesseractEngine:
    def __init__(self) -> None:
        candidates = [shutil.which("tesseract")]
        if os.name == "nt":
            candidates.extend(
                str(Path(os.environ.get(name, "")) / "Tesseract-OCR/tesseract.exe")
                for name in ("ProgramFiles", "ProgramFiles(x86)")
            )
        self.executable = next((p for p in candidates if p and Path(p).is_file()), None)
        if not self.executable:
            raise OCRInitializationError(
                "Tesseract is not installed. Use managed RapidOCR for setup without executable paths."
            )

    def recognize(self, image: Image.Image, language: str, vertical: bool = False) -> OCRResult:
        code = REGISTRY[language].tesseract
        if not code:
            raise OCRLanguageMissingError("Choose a source language when using Tesseract.")
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        start = time.perf_counter()
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        try:
            response = subprocess.run(
                [
                    str(self.executable),
                    "stdin",
                    "stdout",
                    "-l",
                    code,
                    "--psm",
                    "5" if vertical else "6",
                    "tsv",
                ],
                input=buffer.getvalue(),
                capture_output=True,
                timeout=20,
                creationflags=flags,
            )
            if response.returncode:
                if b"traineddata" in response.stderr:
                    raise OCRLanguageMissingError()
                raise OCRInferenceError()
            lines = []
            for row in csv.DictReader(io.StringIO(response.stdout.decode("utf-8")), delimiter="\t"):
                if row["text"].strip() and float(row["conf"]) >= 0:
                    lines.append(
                        OCRLine(
                            row["text"],
                            Rect(
                                int(row["left"]),
                                int(row["top"]),
                                max(1, int(row["width"])),
                                max(1, int(row["height"])),
                            ),
                            float(row["conf"]) / 100,
                        )
                    )
            output = tuple(lines)
            return OCRResult(
                reconstruct(output, vertical, REGISTRY[language].direction),
                output,
                sum(line.confidence for line in output) / len(output) if output else 0,
                language,
                (time.perf_counter() - start) * 1000,
            )
        except (subprocess.TimeoutExpired, OSError, ValueError, KeyError):
            raise OCRInferenceError() from None

    def close(self) -> None:
        pass


def ocr_process(connection: Any, name: str, language: str, directory: str) -> None:
    """A process contains native inference crashes and can be terminated on shutdown."""
    try:
        # Parent assigns the Windows job before any external engine can launch.
        if connection.recv() != "initialize":
            return
        engine = RapidEngine(language, Path(directory)) if name == "rapidocr" else TesseractEngine()
        connection.send(("ready", None))
        while True:
            size, pixels, vertical = connection.recv()
            image = Image.frombytes("RGB", size, pixels)
            try:
                connection.send(("result", engine.recognize(image, language, vertical)))
            except Exception:
                connection.send(("error", "OCRInferenceError"))
    except OCRLanguageMissingError:
        connection.send(("error", "OCRLanguageMissingError"))
    except Exception:
        connection.send(("error", "OCRInitializationError"))
    finally:
        connection.close()


class IsolatedOCR:
    def __init__(self, name: str, language: str, directory: Path | None = None) -> None:
        self.lock = Lock()
        context = mp.get_context("spawn")
        self.connection, child = context.Pipe()
        child_endpoint: Any = child
        if os.name == "nt":
            from desktranslate.processes import ChildPipe

            child_endpoint = ChildPipe(child.fileno())
        self.process = context.Process(
            target=ocr_process,
            args=(child_endpoint, name, language, str(directory or data_dir() / "models")),
            daemon=True,
        )
        try:
            self.process.start()
        except Exception:
            self.connection.close()
            self.process.close()
            raise OCRInitializationError() from None
        finally:
            child.close()
        self.ready = False
        self.closed = Event()
        self.cancelled = Event()
        self.reaped = False
        self.job = None
        try:
            if os.name == "nt":
                from desktranslate.processes import ProcessJob

                assert self.process.pid is not None
                self.job = ProcessJob(self.process.pid)
            self.connection.send("initialize")
        except Exception:
            self.reap()
            raise OCRInitializationError() from None

    def receive(self, cancel: Event, timeout: float = 25.0) -> tuple[str, Any]:
        start = time.monotonic()
        while not self.closed.is_set() and not self.cancelled.is_set() and not cancel.is_set():
            try:
                if self.connection.poll(0.05):
                    return self.connection.recv()  # type: ignore[no-any-return]
            except (EOFError, OSError):
                if self.closed.is_set() or self.cancelled.is_set() or cancel.is_set():
                    raise Cancelled() from None
                raise OCRInferenceError() from None
            if not self.process.is_alive() or time.monotonic() - start > timeout:
                self.close()
                raise OCRInferenceError()
        raise Cancelled()

    def recognize(
        self, image: Image.Image, language: str, vertical: bool = False, cancel: Event | None = None
    ) -> OCRResult:
        cancel = cancel or Event()
        if not self.ready:
            status, value = self.receive(cancel)
            if status != "ready":
                error = (
                    OCRLanguageMissingError
                    if value == "OCRLanguageMissingError"
                    else OCRInitializationError
                )
                raise error()
            self.ready = True
        if self.closed.is_set() or self.cancelled.is_set() or cancel.is_set():
            raise Cancelled()
        try:
            self.connection.send((image.size, image.tobytes(), vertical))
        except (OSError, EOFError):
            if self.closed.is_set() or self.cancelled.is_set():
                raise Cancelled() from None
            raise OCRInferenceError() from None
        status, value = self.receive(cancel)
        if status != "result":
            raise OCRInferenceError()
        return value  # type: ignore[no-any-return]

    def cancel_pending(self) -> None:
        """Cancel IPC without waiting for a reaper's process-join lock."""
        self.cancelled.set()
        if self.closed.is_set():
            return
        with contextlib.suppress(ValueError, OSError):
            if self.job:
                self.job.terminate()
            else:
                self.process.terminate()

    def close(self) -> None:
        with self.lock:
            if not self.closed.is_set():
                self.closed.set()
                if self.process.is_alive():
                    self.process.terminate()
                self.connection.close()
                if self.job:
                    self.job.close()

    def reap(self) -> None:
        """Called from the recognition worker, after cancellation has ended IPC."""
        self.close()
        with self.lock:
            if self.reaped:
                return
            self.process.join(2.0)
            if self.process.is_alive():
                self.process.kill()
                self.process.join(2.0)
            if not self.process.is_alive():
                self.process.close()
                self.reaped = True
            else:
                raise OCRInferenceError("The OCR worker did not exit after termination.")
