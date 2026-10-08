from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

from desktranslate.languages import REGISTRY
from desktranslate.models import Rect


def data_dir() -> Path:
    if override := os.environ.get("DESKTRANSLATE_DATA_DIR"):
        return Path(override)
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "DeskTranslate"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "desktranslate"


DEFAULT_HOTKEYS = {
    "once": "Ctrl+Alt+T",
    "live": "Ctrl+Alt+L",
    "pause": "Ctrl+Alt+P",
    "stop": "Ctrl+Alt+S",
    "select": "Ctrl+Alt+R",
    "overlay": "Ctrl+Alt+O",
    "copy": "Ctrl+Alt+C",
    "edit": "Ctrl+Alt+E",
}


@dataclass
class Settings:
    version: int = 2
    source: str = "ja"
    target: str = "en"
    provider: str = "google"
    model: str = ""
    endpoint: str = ""
    provider_models: dict[str, str] = field(default_factory=dict)
    provider_endpoints: dict[str, str] = field(default_factory=dict)
    ocr: str = "rapidocr"
    quality: str = "balanced"
    preprocessing: str = "original"
    vertical: bool = False
    style: str = "natural"
    instructions: str = ""
    glossary: dict[str, str] = field(default_factory=dict)
    theme: str = "dark"
    onboarding_done: bool = False
    recent_region: list[int] | None = None
    display_signature: str = ""
    overlay_geometry: list[int] | None = None
    overlay_size: int = 22
    overlay_opacity: int = 92
    overlay_mode: str = "bilingual"
    overlay_click_through: bool = False
    overlay_font: str = "Segoe UI"
    overlay_weight: int = 600
    overlay_italic: bool = False
    overlay_color: str = "#f5faf7"
    overlay_text_opacity: int = 100
    overlay_source_color: str = "#aec7bf"
    overlay_source_size: int = 14
    overlay_background: str = "#13262e"
    overlay_gradient: str = "#13262e"
    overlay_background_opacity: int = 92
    overlay_gradient_angle: int = 90
    overlay_outline: str = "#071114"
    overlay_outline_width: int = 1
    overlay_shadow: bool = True
    overlay_shadow_opacity: int = 60
    overlay_shadow_x: int = 1
    overlay_shadow_y: int = 2
    overlay_line_spacing: int = 115
    overlay_letter_spacing: int = 0
    overlay_alignment: str = "left"
    overlay_padding: int = 22
    overlay_radius: int = 12
    overlay_max_lines: int = 5
    overlay_locked: bool = False
    overlay_source_position: str = "above"
    overlay_fade: bool = True
    reduced_motion: bool = False
    hotkeys: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_HOTKEYS))
    close_to_tray: bool = False
    speak: bool = False
    context_entries: int = 8
    context_chars: int = 6000
    timeout: int = 25
    profiles: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def region(self) -> Rect | None:
        return Rect(*self.recent_region) if self.recent_region else None

    def validate(self) -> None:
        if (
            self.version != 2
            or self.source not in REGISTRY
            or self.target not in REGISTRY
            or self.target == "auto"
        ):
            raise ValueError("Invalid language or schema")
        enums = {
            "provider": {
                "google",
                "deepl",
                "libre",
                "openai",
                "anthropic",
                "gemini",
                "openrouter",
                "ollama",
                "lmstudio",
                "custom",
            },
            "ocr": {"rapidocr", "tesseract"},
            "quality": {"fast", "balanced", "accuracy"},
            "theme": {"light", "dark"},
            "preprocessing": {"original", "contrast", "subtitle"},
            "style": {"natural", "literal", "subtitle", "game", "custom"},
            "overlay_mode": {"translation", "bilingual", "subtitle", "compact"},
            "overlay_alignment": {"left", "center", "right"},
            "overlay_source_position": {"above", "below"},
        }
        for name, values in enums.items():
            if getattr(self, name) not in values:
                raise ValueError("Invalid setting")
        for name, low, high in [
            ("overlay_size", 12, 64),
            ("overlay_opacity", 30, 100),
            ("timeout", 3, 120),
            ("context_entries", 0, 20),
            ("context_chars", 0, 12000),
            ("overlay_weight", 100, 900),
            ("overlay_text_opacity", 30, 100),
            ("overlay_source_size", 10, 48),
            ("overlay_background_opacity", 0, 100),
            ("overlay_gradient_angle", 0, 360),
            ("overlay_outline_width", 0, 6),
            ("overlay_shadow_opacity", 0, 100),
            ("overlay_shadow_x", -12, 12),
            ("overlay_shadow_y", -12, 12),
            ("overlay_line_spacing", 90, 200),
            ("overlay_letter_spacing", -2, 8),
            ("overlay_padding", 4, 60),
            ("overlay_radius", 0, 40),
            ("overlay_max_lines", 1, 12),
        ]:
            value = getattr(self, name)
            if type(value) is not int or not low <= value <= high:
                raise ValueError("Invalid range")
        for name in (
            "vertical",
            "onboarding_done",
            "overlay_click_through",
            "close_to_tray",
            "speak",
            "overlay_italic",
            "overlay_shadow",
            "overlay_locked",
            "overlay_fade",
            "reduced_motion",
        ):
            if type(getattr(self, name)) is not bool:
                raise ValueError("Invalid boolean")
        for name in ("model", "endpoint", "instructions", "display_signature", "overlay_font"):
            if not isinstance(getattr(self, name), str) or len(getattr(self, name)) > 2000:
                raise ValueError("Invalid text setting")
        for name in (
            "overlay_color",
            "overlay_source_color",
            "overlay_background",
            "overlay_gradient",
            "overlay_outline",
        ):
            if not isinstance(getattr(self, name), str) or not re.fullmatch(
                r"#[0-9a-fA-F]{6}", getattr(self, name)
            ):
                raise ValueError("Use a color in #RRGGBB format")
        for name in ("glossary", "provider_models", "provider_endpoints", "hotkeys"):
            value = getattr(self, name)
            if (
                not isinstance(value, dict)
                or len(value) > 100
                or any(
                    not isinstance(k, str) or not isinstance(v, str) or len(k) + len(v) > 2000
                    for k, v in value.items()
                )
            ):
                raise ValueError("Invalid mapping")
        self.hotkeys = {**DEFAULT_HOTKEYS, **self.hotkeys}
        for name in ("recent_region", "overlay_geometry"):
            value = getattr(self, name)
            if value is not None:
                if (
                    not isinstance(value, list)
                    or len(value) != 4
                    or any(type(x) is not int for x in value)
                ):
                    raise ValueError("Invalid geometry")
                Rect(*value)
        if not isinstance(self.profiles, dict) or len(self.profiles) > 30:
            raise ValueError("Invalid profiles")
        if len(self.instructions) > 1500:
            raise ValueError("Instructions too long")


class SettingsStore:
    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory or data_dir()
        self.path = self.directory / "settings.json"
        self.recovered = False

    def load(self) -> Settings:
        if not self.path.exists():
            return Settings()
        try:
            if self.path.stat().st_size > 200_000:
                raise ValueError("Oversized settings")
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("Invalid settings")
            # A prior schema may contain secrets; never preserve them in a backup.
            if raw.get("version", 1) == 1:
                raw = {
                    "source": raw.get("source", "ja"),
                    "target": raw.get("target", "en"),
                    "version": 2,
                }
            allowed = {f.name for f in fields(Settings)}
            settings = Settings(**{k: v for k, v in raw.items() if k in allowed})
            settings.validate()
            return settings
        except (OSError, ValueError, TypeError):
            self.recovered = True
            return Settings()

    def save(self, settings: Settings) -> None:
        settings.validate()
        self.directory.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix="settings-", suffix=".tmp", dir=self.directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(asdict(settings), stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            Path(temporary).unlink(missing_ok=True)
