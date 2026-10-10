"""Exact support-data allowlist. User content, executable paths and endpoints excluded."""

from __future__ import annotations

import platform
import re
import sys
from dataclasses import asdict
from typing import Any

from desktranslate import __version__
from desktranslate.capture import physical_monitors
from desktranslate.metrics import LatencyMetrics, process_resources
from desktranslate.ocr import ModelManager
from desktranslate.settings import Settings


def diagnostic_metadata(
    settings: Settings,
    metrics: LatencyMetrics,
    errors: list[str],
    counters: dict[str, int],
    displays: list[dict[str, Any]],
    include_model: bool = False,
) -> dict[str, Any]:
    manager = ModelManager()
    result: dict[str, Any] = {
        "version": __version__,
        "os": platform.system(),
        "os_release": platform.release(),
        "os_version": platform.version(),
        "architecture": platform.machine(),
        "python": platform.python_version(),
        "packaged": bool(getattr(sys, "frozen", False)),
        "capture": "mss-window-guarded" if settings.capture_mode == "window" else "mss",
        "capture_mode": settings.capture_mode,
        "recognition_acceleration": "CPU compatibility",
        "ocr": settings.ocr,
        "source_language": settings.source,
        "target_language": settings.target,
        "provider": settings.provider,
        "openai_api": settings.openai_api if settings.provider == "openai" else None,
        "displays_physical": {name: asdict(bounds) for name, bounds in physical_monitors().items()},
        "displays_qt": displays,
        "latency_ms": metrics.snapshot(),
        "resources": process_resources(),
        "recent_error_categories": [
            value for value in errors[-10:] if re.fullmatch(r"[A-Za-z0-9_]{1,60}", value)
        ],
        "counters": {
            key: value
            for key, value in counters.items()
            if key in {"captures", "ocr", "translations", "stale", "cache_hits", "ocr_restarts"}
            and type(value) is int
        },
        "models": [
            {
                "id": model,
                "expected_sha256": manager.catalog[model]["sha256"],
                "present": manager.path(model).is_file(),
            }
            for model in manager.required(settings.source)
        ],
    }
    if (
        include_model
        and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,150}", settings.model)
        and not settings.model.startswith(("/", "C:", "c:"))
    ):
        result["model"] = settings.model
    return result
