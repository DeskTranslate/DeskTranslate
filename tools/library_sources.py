"""Package matching unmodified LGPL library sources alongside binary releases."""

from __future__ import annotations

import hashlib
import json
import tarfile
import zipfile
from pathlib import Path

import httpx


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
                    relative = Path(member.name.split("/LICENSES/", 1)[1])
                    if relative.is_absolute() or ".." in relative.parts:
                        raise RuntimeError("Invalid archive license path")
                    target = root / "packaging/licenses" / name / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    content = archive.extractfile(member)
                    if content:
                        target.write_bytes(content.read())
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    dist = root / "dist"
    dist.mkdir(exist_ok=True)
    with zipfile.ZipFile(
        dist / "DeskTranslate-2.0.0b1-LibrarySources.zip", "w", compression=zipfile.ZIP_STORED
    ) as output:
        for file in cache.glob("*.tar.gz"):
            output.write(file, file.name)
        output.write(root / "docs/third-party.md", "README.md")
        output.write(manifest_path, "library-sources.json")
    print("Corresponding library sources and original licenses prepared")


if __name__ == "__main__":
    main()
