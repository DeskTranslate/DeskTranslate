from __future__ import annotations

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
from desktranslate.models import OCRLine, OCRResult, Rect
from desktranslate.settings import data_dir

INSTALL_LOCK = Lock()


def manifest() -> dict[str, dict[str, Any]]:
    return json.loads((Path(__file__).parent / "assets/models.json").read_text(encoding="utf-8"))


class ModelManager:
    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory or data_dir() / "models"
        self.catalog = manifest()

    def required(self, language: str) -> list[str]:
        return ["det", "cls", REGISTRY[language].recognition]

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
        self.directory.mkdir(parents=True, exist_ok=True)
        with httpx.Client(timeout=httpx.Timeout(15.0, connect=5), follow_redirects=False) as client:
            for model in self.required(language):
                if self.valid(model):
                    continue
                info = self.catalog[model]
                target = self.path(model)
                partial = target.with_suffix(".part")
                url = info["url"]
                deadline = time.monotonic() + 180
                try:
                    for _ in range(6):
                        if cancel.is_set():
                            raise Cancelled()
                        with client.stream("GET", url) as response:
                            if response.is_redirect:
                                next_url = str(response.url.join(response.headers["location"]))
                                if not next_url.startswith("https://"):
                                    raise OCRInitializationError("Model download requires HTTPS.")
                                url = next_url
                                continue
                            response.raise_for_status()
                            try:
                                total = int(response.headers.get("Content-Length", 0))
                            except ValueError:
                                total = 0
                            if not 0 <= total <= 100_000_000:
                                raise OCRInitializationError("Invalid language pack download size.")
                            digest = hashlib.sha256()
                            downloaded = 0
                            with partial.open("wb") as stream:
                                for chunk in response.iter_bytes(65536):
                                    if cancel.is_set():
                                        raise Cancelled()
                                    if time.monotonic() > deadline:
                                        raise OCRInitializationError(
                                            "The language pack download took too long. Retry on a stable connection."
                                        )
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
                except httpx.HTTPError:
                    raise OCRInitializationError(
                        "Cannot download recognition models. Check your connection, then retry."
                    ) from None
                finally:
                    partial.unlink(missing_ok=True)


class RapidEngine:
    def __init__(self, language: str, directory: Path | None = None) -> None:
        manager = ModelManager(directory)
        if not manager.installed(language, verify=True):
            raise OCRLanguageMissingError()
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

    def recognize(self, image: Image.Image, language: str, vertical: bool = False) -> OCRResult:
        import numpy as np

        start = time.perf_counter()
        # Screens are already upright. The document angle classifier can rotate
        # valid Hangul subtitles by 180 degrees, destroying otherwise accurate OCR.
        result: Any = self.engine(np.asarray(image)[:, :, ::-1], use_cls=False)
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
        confidence = sum(line.confidence for line in output) / len(output) if output else 0.0
        return OCRResult(
            reconstruct(output, vertical),
            output,
            confidence,
            language,
            (time.perf_counter() - start) * 1000,
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
                reconstruct(output, vertical),
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
        self.process = context.Process(
            target=ocr_process,
            args=(child, name, language, str(directory or data_dir() / "models")),
            daemon=True,
        )
        self.process.start()
        child.close()
        self.ready = False
        self.closed = Event()
        self.reaped = False

    def receive(self, cancel: Event, timeout: float = 25.0) -> tuple[str, Any]:
        start = time.monotonic()
        while not self.closed.is_set() and not cancel.is_set():
            try:
                if self.connection.poll(0.05):
                    return self.connection.recv()  # type: ignore[no-any-return]
            except (EOFError, OSError):
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
        if self.closed.is_set() or cancel.is_set():
            raise Cancelled()
        try:
            self.connection.send((image.size, image.tobytes(), vertical))
        except (OSError, EOFError):
            if self.closed.is_set():
                raise Cancelled() from None
            raise OCRInferenceError() from None
        status, value = self.receive(cancel)
        if status != "result":
            raise OCRInferenceError()
        return value  # type: ignore[no-any-return]

    def close(self) -> None:
        with self.lock:
            if not self.closed.is_set():
                self.closed.set()
                if self.process.is_alive():
                    self.process.terminate()
                self.connection.close()

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
