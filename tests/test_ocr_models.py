import hashlib
import os
import subprocess
import sys
from threading import Event

import httpx
import pytest

from desktranslate.errors import OCRInitializationError
from desktranslate.ocr import ModelManager


@pytest.mark.parametrize("inherited", ["0", ""])
def test_process_privacy_policy_precedes_native_ocr_import(inherited):
    environment = {**os.environ, "ORT_DISABLE_TELEMETRY": inherited}
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import os,sys; import desktranslate; assert os.environ['ORT_DISABLE_TELEMETRY']=='1'; assert 'onnxruntime' not in sys.modules",
        ],
        env=environment,
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 0, "OCR telemetry policy must be applied before native import"


def test_ocr_disables_onnx_telemetry_before_creating_sessions(tmp_path, monkeypatch):
    from types import SimpleNamespace

    import onnxruntime
    import rapidocr

    from desktranslate.ocr import RapidEngine

    calls = []
    monkeypatch.setattr(ModelManager, "installed", lambda *args, **kwargs: True)
    monkeypatch.setattr(onnxruntime, "disable_telemetry_events", lambda: calls.append("disabled"))

    def create(*args, **kwargs):
        assert calls == ["disabled"], (
            "Telemetry must be disabled before native sessions are created"
        )
        calls.append("sessions")
        return SimpleNamespace(text_rec=SimpleNamespace(), text_det=SimpleNamespace())

    monkeypatch.setattr(rapidocr, "RapidOCR", create)
    RapidEngine("ja", tmp_path)
    assert calls == ["disabled", "sessions"]


@pytest.mark.parametrize(
    "width,height", [(660, 160), (320, 100), (1920, 1080), (2000, 2000), (160, 660)]
)
def test_detector_bound_preserves_ordinary_input_pixels(width, height):
    import numpy as np
    from rapidocr.ch_ppocr_det.utils import DetPreProcess

    from desktranslate.ocr import bounded_detector_preprocess

    image = np.random.default_rng(7).integers(0, 256, (height, width, 3), dtype=np.uint8)
    original = DetPreProcess(736, "min")
    bounded = bounded_detector_preprocess(736, "min", None, None)
    assert np.array_equal(original(image), bounded(image))


@pytest.mark.parametrize("width,height", [(7680, 64), (64, 7680), (2000, 1), (2000, 200)])
def test_detector_tensor_is_bounded_for_thin_display_regions(width, height):
    import numpy as np

    from desktranslate.ocr import bounded_detector_preprocess

    result = bounded_detector_preprocess(736, "min", None, None)(
        np.zeros((height, width, 3), dtype=np.uint8)
    )
    assert result.shape[:2] == (1, 3)
    assert max(result.shape[2:]) <= 4096
    assert all(side >= 32 and side % 32 == 0 for side in result.shape[2:])
    assert result.size <= 3 * 4096 * 736


def test_model_integrity_and_truncated_download_cleanup(tmp_path, monkeypatch):
    manager = ModelManager(tmp_path)
    manager.catalog = {
        key: {
            "filename": key + ".onnx",
            "url": "https://models.example/" + key,
            "sha256": hashlib.sha256(b"correct").hexdigest(),
        }
        for key in manager.required("ja")
    }
    original = httpx.AsyncClient

    def client(**kwargs):
        return original(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b"corrupt")),
            **kwargs,
        )

    monkeypatch.setattr(httpx, "AsyncClient", client)
    with pytest.raises(OCRInitializationError, match="verification"):
        manager.install("ja", Event(), lambda *args: None)
    assert not list(tmp_path.glob("*.part"))
    assert not manager.installed("ja")


def test_verified_preinstalled_models_need_no_network(tmp_path):
    manager = ModelManager(tmp_path)
    digest = hashlib.sha256(b"model").hexdigest()
    manager.catalog = {
        key: {"filename": key + ".onnx", "url": "https://models.example/" + key, "sha256": digest}
        for key in manager.required("ja")
    }
    for key in manager.required("ja"):
        manager.path(key).write_bytes(b"model")
    assert manager.installed("ja", verify=True)
    manager.install("ja", Event(), lambda *args: None)


def test_japanese_pack_requires_the_verified_regional_model_without_affecting_other_languages(
    tmp_path,
):
    manager = ModelManager(tmp_path)
    content = b"verified fixture model"
    for info in manager.catalog.values():
        info.update(bytes=len(content), sha256=hashlib.sha256(content).hexdigest())
    # A complete older Japanese pack and English pack coexist. Updating the
    # Japanese pack must not make an installed English pack require a download.
    for key in {"det", "cls", "japan", *manager.required("en")}:
        manager.path(key).write_bytes(content)
    assert manager.installed("en", verify=True)
    assert not manager.installed("ja")
    regional = manager.path("japan_regional")
    regional.write_bytes(b"interrupted download")
    assert not manager.installed("ja", verify=True)
    regional.write_bytes(content)
    assert manager.installed("ja", verify=True)


def test_oversized_cached_model_is_rejected_without_hashing_it(tmp_path, monkeypatch):
    manager = ModelManager(tmp_path)
    model = manager.path("det")
    with model.open("wb") as stream:
        stream.truncate(100_000_001)

    def unexpected_hash(*args):
        raise AssertionError("Oversized model must not be read")

    monkeypatch.setattr(hashlib, "file_digest", unexpected_hash)
    assert not manager.valid("det")


def test_rtl_dependency_is_present_in_the_locked_runtime():
    from bidi.algorithm import get_display

    assert get_display("שלום") == "םולש"


@pytest.mark.parametrize("compressed", [False, True])
def test_model_download_is_bounded_identity_and_atomic(tmp_path, monkeypatch, compressed):
    manager = ModelManager(tmp_path)
    manager.catalog = {
        key: {
            "filename": key + ".onnx",
            "url": "https://models.example/" + key,
            "sha256": hashlib.sha256(b"correct").hexdigest(),
        }
        for key in manager.required("ja")
    }
    original = httpx.AsyncClient

    def response(request):
        assert request.headers["Accept-Encoding"] == "identity"
        return httpx.Response(
            200,
            content=b"correct",
            headers={"Content-Encoding": "unexpected" if compressed else "identity"},
        )

    def client(**kwargs):
        return original(transport=httpx.MockTransport(response), **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client)
    if compressed:
        with pytest.raises(OCRInitializationError):
            manager.install("ja", Event(), lambda *args: None)
        assert not manager.installed("ja")
    else:
        manager.install("ja", Event(), lambda *args: None)
        assert manager.installed("ja", verify=True)
    assert not list(tmp_path.glob("*.part"))
