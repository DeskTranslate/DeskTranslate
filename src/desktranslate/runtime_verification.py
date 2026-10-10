"""Explicit release probe using authored text and a temporary loopback server."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

from desktranslate.models import TranslationRequest
from desktranslate.providers import CompatibleProvider, create_provider


def verify_http_provider() -> bool:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            pass

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length < 8192:
                self.send_error(400)
                return
            self.rfile.read(length)
            body = json.dumps({"choices": [{"message": {"content": "Authored result"}}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    provider = None
    try:
        provider = create_provider(
            "custom", endpoint=f"http://127.0.0.1:{server.server_port}/v1", timeout=5
        )
        if not isinstance(provider, CompatibleProvider):
            return False
        result = provider.translate(TranslationRequest("Authored input", "en", "ja", "probe"))
        return result.text == "Authored result"
    finally:
        if provider:
            provider.close()
        server.shutdown()
        server.server_close()
        thread.join(2)
