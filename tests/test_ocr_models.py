import hashlib
from threading import Event

import httpx
import pytest

from desktranslate.errors import OCRInitializationError
from desktranslate.ocr import ModelManager


def test_model_integrity_and_truncated_download_cleanup(tmp_path, monkeypatch):
    manager = ModelManager(tmp_path)
    manager.catalog = {
        key: {
            "filename": key + ".onnx",
            "url": "https://models.example/" + key,
            "sha256": hashlib.sha256(b"correct").hexdigest(),
        }
        for key in ["det", "cls", "japan"]
    }
    original = httpx.Client

    def client(**kwargs):
        return original(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b"corrupt")),
            **kwargs,
        )

    monkeypatch.setattr(httpx, "Client", client)
    with pytest.raises(OCRInitializationError, match="verification"):
        manager.install("ja", Event(), lambda *args: None)
    assert not list(tmp_path.glob("*.part"))
    assert not manager.installed("ja")


def test_verified_preinstalled_models_need_no_network(tmp_path):
    manager = ModelManager(tmp_path)
    digest = hashlib.sha256(b"model").hexdigest()
    manager.catalog = {
        key: {"filename": key + ".onnx", "url": "https://models.example/" + key, "sha256": digest}
        for key in ["det", "cls", "japan"]
    }
    for key in manager.required("ja"):
        manager.path(key).write_bytes(b"model")
    assert manager.installed("ja", verify=True)
    manager.install("ja", Event(), lambda *args: None)
