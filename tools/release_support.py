"""Canonical versions, numeric build traceability and Windows publisher signing."""

from __future__ import annotations

import ast
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from packaging.version import Version

from desktranslate import __version__


def windows_version(version: str = __version__) -> str:
    parsed = Version(version)
    release = (*parsed.release[:3], *(0 for _ in range(3 - len(parsed.release))))
    revision = (
        60000
        if parsed.pre is None
        else {"a": 1000, "b": 10000, "rc": 30000}[parsed.pre[0]] + parsed.pre[1]
    )
    if any(not 0 <= value <= 65535 for value in (*release, revision)):
        raise ValueError("Version is outside Windows PE limits")
    return ".".join(str(value) for value in (*release, revision))


def version_gate(root: Path, tag: str = "") -> None:
    import tomllib

    project = tomllib.loads((root / "pyproject.toml").read_text())
    if (
        "version" not in project["project"].get("dynamic", [])
        or project["tool"]["setuptools"]["dynamic"]["version"]["attr"]
        != "desktranslate.__version__"
    ):
        raise ValueError("Package version must come from desktranslate.__version__")
    installer = (root / "packaging/installer.iss").read_text()
    if '#define AppVersion "' in installer or "{#AppVersion}" not in installer:
        raise ValueError("Installer must receive the canonical version from the build")
    if tag and tag != "v" + __version__:
        raise ValueError("Release tag does not match the canonical package version")


def git_trace(root: Path) -> dict[str, str | bool]:
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=root))
    digest = hashlib.sha256()
    for path in sorted((root / "src/desktranslate").rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(path.read_bytes())
    return {"git_commit": commit, "working_tree_dirty": dirty, "source_sha256": digest.hexdigest()}


def runtime_source_hashes(root: Path) -> dict[str, str]:
    directory = root / "src/desktranslate"
    return {
        path.relative_to(directory).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(directory.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts
    }


def shipped_distributions(root: Path) -> list[importlib.metadata.Distribution]:
    # PyInstaller records the precise analysis input paths. They are only used
    # privately to map owners; no absolute paths enter public inventories.
    analysis = ast.literal_eval(
        (root / "build/DeskTranslate/Analysis-00.toc").read_text(encoding="utf-8")
    )
    inputs: set[str] = set()

    def visit(value: Any) -> None:
        if (
            isinstance(value, tuple)
            and len(value) == 3
            and isinstance(value[2], str)
            and value[2] in {"PYMODULE", "PYSOURCE", "BINARY", "EXTENSION", "DATA"}
            and isinstance(value[1], str)
            and "site-packages" in value[1]
        ):
            inputs.add(os.path.normcase(str(Path(value[1]).resolve())))
        elif isinstance(value, (list, tuple)):
            for item in value:
                visit(item)

    visit(analysis)
    result = []
    for distribution in importlib.metadata.distributions():
        if any(
            os.path.normcase(str(Path(distribution.locate_file(file)).resolve())) in inputs
            for file in distribution.files or []
        ):
            result.append(distribution)
    return sorted(result, key=lambda d: d.metadata["Name"].lower())


class Signer:
    def __init__(self) -> None:
        self.thumbprint = os.environ.get("DESKTRANSLATE_SIGNING_THUMBPRINT", "").replace(" ", "")
        if not re.fullmatch(r"[A-Fa-f0-9]{40}", self.thumbprint):
            raise ValueError(
                "Configure a publisher signing certificate thumbprint; never use a self-signed release certificate."
            )
        self.timestamp = os.environ.get(
            "DESKTRANSLATE_TIMESTAMP_URL", "https://timestamp.digicert.com"
        )
        parts = urlsplit(self.timestamp)
        if (
            parts.scheme != "https"
            or not parts.hostname
            or parts.username
            or parts.password
            or parts.query
            or parts.fragment
            or any(ord(c) < 33 for c in self.timestamp)
        ):
            raise ValueError("Configure a valid HTTPS RFC 3161 timestamp server")
        self.tool = os.environ.get("SIGNTOOL_PATH") or shutil.which("signtool")
        if not self.tool:
            candidates = sorted(
                Path("C:/Program Files (x86)/Windows Kits/10/bin").glob("*/x64/signtool.exe"),
                reverse=True,
            )
            self.tool = str(candidates[0]) if candidates else None
        if not self.tool or not Path(self.tool).is_file() or '"' in self.tool:
            raise ValueError("Install the Windows SDK SignTool or configure SIGNTOOL_PATH")

    def sign(self, path: Path) -> None:
        subprocess.run(
            [
                str(self.tool),
                "sign",
                "/sha1",
                self.thumbprint,
                "/fd",
                "SHA256",
                "/tr",
                self.timestamp,
                "/td",
                "SHA256",
                str(path),
            ],
            check=True,
        )
        self.verify(path)

    def verify(self, path: Path) -> None:
        subprocess.run([str(self.tool), "verify", "/pa", "/all", "/tw", str(path)], check=True)
        # SignTool /tw only warns about missing timestamps. Make it a hard gate,
        # and check the certificate selected for our own executable/installer.
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-File",
                str(Path(__file__).resolve().parents[1] / "packaging/verify-signature.ps1"),
                "-Artifact",
                str(path),
                "-Expected",
                self.thumbprint,
            ],
            check=True,
        )

    def inno_command(self) -> str:
        # ISCC expands $q/$f itself. Process execution uses an argv list, never a
        # shell; certificate IDs are hex and the timestamp URL is validated.
        if any(c in self.timestamp for c in '"$&|<>`'):
            raise ValueError("Unsafe timestamp command characters")
        return f"$q{self.tool}$q sign /sha1 {self.thumbprint} /fd SHA256 /tr {self.timestamp} /td SHA256 $f"


def stable_gate(root: Path, tag: str) -> None:
    version_gate(root, tag)
    if Version(__version__).is_prerelease:
        raise ValueError("A prerelease version cannot be promoted as stable")
    evidence = json.loads((root / "docs/manual-qualification.json").read_text())
    required = (
        "clean_windows",
        "mixed_dpi_displays",
        "fullscreen_media",
        "accessibility_screen_reader",
        "real_provider_models",
        "installer_upgrade",
        "prolonged_media",
    )
    missing = [gate for gate in required if evidence.get("gates", {}).get(gate) is not True]
    if evidence.get("version") != __version__ or missing:
        raise ValueError("Stable manual qualification is incomplete: " + ", ".join(missing))
    soak = json.loads((root / "docs/soak-2h.json").read_text())
    if (
        soak.get("version") != __version__
        or soak.get("elapsed_s", 0) < 7200
        or not soak.get("workload_passed")
        or not soak.get("source_unchanged")
        or not soak.get("resource_qualification", {}).get("qualified")
    ):
        raise ValueError("Stable requires the completed two-hour workload/resource soak")
    if soak.get("source_hashes") != runtime_source_hashes(root):
        raise ValueError("Application source/assets changed after the recorded soak")
    if soak.get("python_version") != platform.python_version():
        raise ValueError("Python runtime changed after the recorded soak")
    if not tag:
        raise ValueError("Stable requires an exact canonical Git tag")
