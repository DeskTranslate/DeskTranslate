"""Versioned portable profiles. Imports are data, never credentials or executable paths."""

from __future__ import annotations

import copy
import csv
import io
import json
from dataclasses import fields
from pathlib import Path
from typing import Any

from desktranslate.security import validate_endpoint
from desktranslate.settings import Settings

SCHEMA = "desktranslate.profile"
PROFILE_VERSION = 1
BASE_KEYS = {
    "source",
    "target",
    "provider",
    "model",
    "endpoint",
    "openai_api",
    "ocr",
    "quality",
    "preprocessing",
    "vertical",
    "style",
    "instructions",
    "glossary",
    "context_entries",
    "context_chars",
    "recent_region",
    "display_signature",
    "capture_mode",
    "monitor_name",
    "window_target",
    "window_region",
    "window_follow_restart",
    "hotkeys",
    "reduced_motion",
}
PROFILE_KEYS = BASE_KEYS | {f.name for f in fields(Settings) if f.name.startswith("overlay_")}
CAPTURE_KEYS = {
    "recent_region",
    "display_signature",
    "capture_mode",
    "monitor_name",
    "window_target",
    "window_region",
    "window_follow_restart",
}


def profile_values(settings: Settings) -> dict[str, Any]:
    return {key: copy.deepcopy(getattr(settings, key)) for key in sorted(PROFILE_KEYS)}


def validate_profile(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict) or len(raw) > len(PROFILE_KEYS) + 30:
        raise ValueError("This profile is invalid")
    # Unknown fields are ignored for forward additions. Secrets and unsupported
    # nested objects are never round-tripped into persistent settings.
    values = {key: copy.deepcopy(value) for key, value in raw.items() if key in PROFILE_KEYS}
    candidate = Settings(**values)
    candidate.validate()
    if candidate.endpoint:
        validate_endpoint(candidate.endpoint, candidate.provider in {"ollama", "lmstudio"})
    if len(json.dumps(values, ensure_ascii=False).encode("utf-8")) > 60_000:
        raise ValueError("Profile is too large")
    return values


def apply_profile(settings: Settings, raw: Any) -> Settings:
    updated = copy.deepcopy(settings)
    for key, value in validate_profile(raw).items():
        setattr(updated, key, value)
    updated.provider_models[updated.provider] = updated.model
    updated.provider_endpoints[updated.provider] = updated.endpoint
    updated.validate()
    return updated


def export_profile(name: str, raw: Any, include_target: bool = False) -> str:
    values = validate_profile(raw)
    if not include_target:
        for key in CAPTURE_KEYS:
            values.pop(key, None)
    return json.dumps(
        {
            "schema": SCHEMA,
            "version": PROFILE_VERSION,
            "name": valid_name(name),
            "settings": values,
        },
        ensure_ascii=False,
        indent=2,
    )


def import_profile(content: str) -> tuple[str, dict[str, Any]]:
    if len(content.encode("utf-8")) > 80_000:
        raise ValueError("Profile file is too large")
    try:
        raw = json.loads(content)
        if (
            not isinstance(raw, dict)
            or raw.get("schema") != SCHEMA
            or type(raw.get("version")) is not int
            or raw["version"] != PROFILE_VERSION
        ):
            raise ValueError("Unsupported profile version. Use a compatible DeskTranslate build.")
        name = valid_name(raw.get("name"))
        values = validate_profile(raw["settings"])
        # Imported coordinates/target identity cannot establish capture consent
        # on this computer. A local target must be selected explicitly.
        for key in CAPTURE_KEYS:
            values.pop(key, None)
        values.update(
            capture_mode="fixed",
            recent_region=None,
            window_target={},
            window_region=None,
            display_signature="",
        )
        return name, values
    except (KeyError, TypeError, RecursionError, json.JSONDecodeError):
        raise ValueError("This is not a valid DeskTranslate profile") from None


def valid_name(name: Any) -> str:
    if (
        not isinstance(name, str)
        or not name.strip()
        or len(name.strip()) > 60
        or any(ord(c) < 32 for c in name)
    ):
        raise ValueError("Use a profile name between 1 and 60 characters")
    return name.strip()


def read_profile(path: Path) -> tuple[str, dict[str, Any]]:
    if path.stat().st_size > 80_000:
        raise ValueError("Profile file is too large")
    return import_profile(path.read_text(encoding="utf-8-sig"))


def import_glossary(content: str, csv_format: bool = False) -> dict[str, str]:
    if len(content.encode("utf-8")) > 60_000:
        raise ValueError("Glossary is too large")
    try:
        if csv_format:
            rows = list(csv.reader(io.StringIO(content), strict=True))
            if rows and rows[0] == ["source", "translation"]:
                rows.pop(0)
            if any(len(row) != 2 for row in rows):
                raise ValueError("Use two CSV columns: source, translation")
            if len({row[0] for row in rows}) != len(rows):
                raise ValueError("Duplicate glossary sources are ambiguous")
            result = dict(rows)
        else:
            result = json.loads(content)
        Settings(glossary=result).validate()
        return result  # type: ignore[no-any-return]
    except (TypeError, json.JSONDecodeError, csv.Error):
        raise ValueError("Invalid glossary. Use JSON pairs or two CSV columns.") from None


def export_glossary(glossary: dict[str, str], csv_format: bool = False) -> str:
    Settings(glossary=glossary).validate()
    if not csv_format:
        return json.dumps(glossary, ensure_ascii=False, indent=2)
    if any(
        value.lstrip().startswith(("=", "+", "-", "@"))
        for pair in glossary.items()
        for value in pair
    ):
        raise ValueError(
            "A glossary term could be interpreted as a spreadsheet formula. Export JSON to preserve it safely."
        )
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["source", "translation"])
    writer.writerows(glossary.items())
    return buffer.getvalue()
