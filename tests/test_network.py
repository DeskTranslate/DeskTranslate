import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event, Thread

import httpx
import pytest

from desktranslate.errors import (
    Cancelled,
    OCRInitializationError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    TranslationError,
)
from desktranslate.models import TranslationRequest
from desktranslate.network import strict_json
from desktranslate.ocr import ModelManager
from desktranslate.providers import create_provider
from desktranslate.updates import check_release


@pytest.fixture
def slow_headers():
    started = Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            started.set()
            try:
                for byte in b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{}":
                    self.connection.sendall(bytes([byte]))
                    time.sleep(0.02)
            except OSError:
                pass

        do_GET = do_POST

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/v1", started
    server.shutdown()
    server.server_close()
    thread.join(2)


def test_total_deadline_covers_slow_response_headers(slow_headers):
    endpoint, _ = slow_headers
    provider = create_provider("custom", endpoint=endpoint, timeout=0.15)
    started = time.monotonic()
    try:
        with pytest.raises(ProviderTimeoutError):
            provider.translate(TranslationRequest("authored text", "en", "ja", "model"))
        assert time.monotonic() - started < 1
    finally:
        provider.close()


def test_stop_cancels_request_during_headers(slow_headers):
    endpoint, requested = slow_headers
    provider = create_provider("custom", endpoint=endpoint)
    failures = []

    def translate():
        try:
            provider.translate(TranslationRequest("authored text", "en", "ja", "model"))
        except Exception as error:
            failures.append(type(error))
        finally:
            provider.close()

    thread = Thread(target=translate, daemon=True)
    thread.start()
    assert requested.wait(2)
    provider.cancel_pending()
    thread.join(2)
    assert not thread.is_alive()
    assert failures == [Cancelled]


@pytest.mark.parametrize(
    "content",
    [
        b"[" * 2000 + b"]" * 2000,
        b'{"tokens":NaN}',
        json.dumps(
            {"choices": [{"message": {"content": "result"}}], "usage": {"prompt_tokens": -1}}
        ).encode(),
    ],
)
def test_hostile_json_and_usage_fail_without_exposing_payload(content):
    provider = create_provider(
        "custom",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, content=content)),
    )
    try:
        with pytest.raises(TranslationError):
            provider.translate(TranslationRequest("authored text", "en", "ja", "model"))
    finally:
        provider.close()


@pytest.mark.parametrize("operation", ["models", "updates"])
def test_download_metadata_deadlines_cover_slow_headers(
    operation, slow_headers, tmp_path, monkeypatch
):
    endpoint, _ = slow_headers
    if operation == "models":
        monkeypatch.setattr("desktranslate.ocr.MODEL_TIMEOUT", 0.15)
        manager = ModelManager(tmp_path)
        manager.catalog = {
            key: {"filename": key + ".onnx", "url": endpoint, "sha256": "0" * 64}
            for key in manager.required("ja")
        }

        def run():
            return manager.install("ja", Event(), lambda *args: None)

        expected = OCRInitializationError
    else:
        monkeypatch.setattr("desktranslate.updates.UPDATE_TIMEOUT", 0.15)
        monkeypatch.setattr("desktranslate.updates.RELEASES", endpoint)
        run = check_release
        expected = ProviderUnavailableError
    started = time.monotonic()
    with pytest.raises(expected):
        run()
    assert time.monotonic() - started < 1
    assert not list(tmp_path.glob("*.part"))


@pytest.mark.parametrize("operation", ["models", "updates"])
def test_download_metadata_cancel_during_headers(operation, slow_headers, tmp_path, monkeypatch):
    endpoint, requested = slow_headers
    cancel, failures = Event(), []
    if operation == "models":
        manager = ModelManager(tmp_path)
        manager.catalog = {
            key: {"filename": key + ".onnx", "url": endpoint, "sha256": "0" * 64}
            for key in manager.required("ja")
        }

        def run():
            return manager.install("ja", cancel, lambda *args: None)
    else:
        monkeypatch.setattr("desktranslate.updates.RELEASES", endpoint)

        def run():
            return check_release(cancel=cancel)

    def worker():
        try:
            run()
        except Exception as error:
            failures.append(type(error))

    thread = Thread(target=worker, daemon=True)
    thread.start()
    assert requested.wait(2)
    cancel.set()
    thread.join(2)
    assert not thread.is_alive()
    assert failures == [Cancelled]
    assert not list(tmp_path.glob("*.part"))


@pytest.mark.parametrize(
    "content", [b"[NaN]", b"[" * 2000 + b"]" * 2000], ids=["nonfinite", "deep"]
)
def test_update_catalog_rejects_hostile_json(content):
    with pytest.raises(ProviderUnavailableError):
        check_release(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, content=content))
        )


def test_json_nesting_guard_handles_quoted_braces_and_escapes():
    value = {"description": "[" * 100 + '\\"' + "]" * 100}
    assert strict_json(json.dumps(value).encode()) == value
