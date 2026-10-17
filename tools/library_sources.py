"""Package matching unmodified LGPL library sources alongside binary releases."""

from __future__ import annotations

import hashlib
import json
import tarfile
import zipfile
from pathlib import Path, PureWindowsPath

import httpx

from desktranslate import __version__


def license_path(name: str) -> Path:
    """Reject Windows path tricks before writing an archive's license text."""
    windows = PureWindowsPath(name)
    parts = name.split("/")
    reserved = {"CON", "PRN", "AUX", "NUL"} | {
        prefix + str(number) for prefix in ("COM", "LPT") for number in range(1, 10)
    }
    if (
        windows.drive
        or windows.root
        or "\\" in name
        or any(
            part in {"", ".", ".."}
            or ":" in part
            or part.endswith((".", " "))
            or part.split(".", 1)[0].upper() in reserved
            for part in parts
        )
    ):
        raise RuntimeError("Invalid archive license path")
    return Path(*parts)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    cache = root / ".audit/library-sources"
    cache.mkdir(parents=True, exist_ok=True)
    manifest_path = root / "packaging/library-sources.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        for repo in ("qt/qtbase", "qt/qtsvg", "pyside/pyside-setup"):
            name = repo.split("/")[1]
            filename = f"{name}-6.12.0.tar.gz"
            url = f"https://codeload.github.com/{repo}/tar.gz/refs/tags/v6.12.0"
            path = cache / filename
            if not path.exists():
                with client.stream("GET", url) as response:
                    response.raise_for_status()
                    with path.open("wb") as stream:
                        for chunk in response.iter_bytes(65536):
                            stream.write(chunk)
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            if name in manifest and manifest[name]["sha256"] != digest:
                raise RuntimeError("Library source integrity mismatch")
            manifest[name] = {"filename": filename, "url": url, "sha256": digest, "tag": "v6.12.0"}
            with tarfile.open(path) as archive:
                for member in archive.getmembers():
                    if not member.isfile() or "/LICENSES/" not in member.name:
                        continue
                    relative = license_path(member.name.split("/LICENSES/", 1)[1])
                    target = root / "packaging/licenses" / name / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    content = archive.extractfile(member)
                    if content:
                        target.write_bytes(content.read())
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    # RapidOCR imports this LGPL dependency for Arabic recognition. Ship its
    # exact PyPI corresponding source alongside the compiled wheel.
    entry = manifest.get("python-bidi")
    if not entry or entry.get("tag") != "0.6.11":
        raise RuntimeError("Pinned python-bidi source is missing from the library manifest")
    filename = entry["filename"]
    if filename != "python_bidi-0.6.11.tar.gz" or not entry["url"].startswith(
        "https://files.pythonhosted.org/"
    ):
        raise RuntimeError("Unexpected corresponding-source location")
    source_path = cache / filename
    if not source_path.is_file():
        with (
            httpx.Client(timeout=60, follow_redirects=False) as source_client,
            source_client.stream("GET", entry["url"]) as response,
        ):
            response.raise_for_status()
            content = bytearray()
            for chunk in response.iter_bytes(65536):
                content.extend(chunk)
                if len(content) > 5_000_000:
                    raise RuntimeError("Corresponding source exceeds its download budget")
            if hashlib.sha256(content).hexdigest() != entry["sha256"]:
                raise RuntimeError("Corresponding-source integrity mismatch")
            source_path.write_bytes(content)
    with source_path.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != entry["sha256"]:
            raise RuntimeError("Corresponding-source integrity mismatch")
    dist = root / "dist"
    dist.mkdir(exist_ok=True)
    with zipfile.ZipFile(
        dist / f"DeskTranslate-{__version__}-LibrarySources.zip",
        "w",
        compression=zipfile.ZIP_STORED,
    ) as output:
        for entry in manifest.values():
            file = cache / entry["filename"]
            output.write(file, file.name)
        output.write(root / "docs/third-party.md", "README.md")
        output.write(manifest_path, "library-sources.json")
    print("Corresponding library sources and original licenses prepared")


if __name__ == "__main__":
    main()
