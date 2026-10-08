import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any


class PrivateFormatter(logging.Formatter):
    """Allowlist metadata; never format messages, args, traceback, URLs or headers."""

    def format(self, record: logging.LogRecord) -> str:
        safe: dict[str, Any] = {"time": self.formatTime(record), "level": record.levelname}
        for key in (
            "component",
            "operation",
            "status",
            "category",
            "duration_ms",
            "session",
            "generation",
        ):
            value = getattr(record, key, None)
            if (
                isinstance(value, (int, float))
                or isinstance(value, str)
                and value.replace("_", "").replace("-", "").isalnum()
                and len(value) < 60
            ):
                safe[key] = value
        return json.dumps(safe)


def configure_logging(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        directory / "application.jsonl", maxBytes=512_000, backupCount=2, encoding="utf-8"
    )
    handler.setFormatter(PrivateFormatter())
    logger = logging.getLogger("desktranslate")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.propagate = False
    # HTTP and OCR dependencies may log content, endpoints or local model paths.
    for name in ("httpx", "httpcore", "RapidOCR", "rapidocr", "onnxruntime"):
        logging.getLogger(name).disabled = True
