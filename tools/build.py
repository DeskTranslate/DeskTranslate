"""Build a folder-based Windows app; no downloaded executable is run by this script."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build(installer: bool) -> None:
    from PIL import Image
    from PyInstaller.utils.hooks import collect_data_files
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtWidgets import QApplication

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    build_dir = ROOT / "build"
    build_dir.mkdir(exist_ok=True)
    raster = QImage(256, 256, QImage.Format.Format_ARGB32)
    raster.fill(0)
    painter = QPainter(raster)
    QSvgRenderer(str(ROOT / "src/desktranslate/assets/icon.svg")).render(painter)
    painter.end()
    raster.save(str(build_dir / "icon.png"))
    Image.open(build_dir / "icon.png").save(
        build_dir / "icon.ico",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    args = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onedir",
        "--name",
        "DeskTranslate",
        "--paths",
        str(ROOT / "src"),
        "--icon",
        str(build_dir / "icon.ico"),
        "--manifest",
        str(ROOT / "packaging/windows.manifest"),
        "--add-data",
        f"{ROOT / 'src/desktranslate/assets'};desktranslate/assets",
        "--collect-data",
        "certifi",
        "--collect-binaries",
        "onnxruntime",
        "--collect-data",
        "onnxruntime",
        "--hidden-import",
        "rapidocr.main",
        "--hidden-import",
        "rapidocr.inference_engine.onnxruntime",
        "--hidden-import",
        "keyring.backends.Windows",
        "--exclude-module",
        "tkinter",
        "--exclude-module",
        "matplotlib",
        "--exclude-module",
        "torch",
        "--exclude-module",
        "paddle",
        str(ROOT / "tools/launcher.py"),
    ]
    # Model provisioning belongs to the managed application-data cache. Never
    # bundle an accidental upstream auto-download from the development environment.
    for source, target in collect_data_files("rapidocr", excludes=["models/**"]):
        args.extend(["--add-data", f"{source};{target}"])
    # Dependency tools may put Poppler's incompatible ICU DLLs on PATH. Qt uses
    # the Windows system ICU; keep unrelated native runtimes out of analysis.
    build_env = os.environ.copy()
    windows = Path(os.environ.get("SYSTEMROOT", "C:/Windows"))
    build_env["PATH"] = os.pathsep.join(
        str(path)
        for path in (
            Path(sys.executable).parent,
            Path(sys.base_prefix),
            windows / "System32",
            windows,
        )
    )
    subprocess.run(args, cwd=ROOT, env=build_env, check=True)
    dependencies = sorted(
        importlib.metadata.distributions(), key=lambda d: d.metadata["Name"].lower()
    )
    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {
            "component": {"type": "application", "name": "DeskTranslate", "version": "2.0.0b1"},
            "properties": [
                {"name": "scope", "value": "build environment; includes development tooling"}
            ],
        },
        "components": [
            {
                "type": "library",
                "name": d.metadata["Name"],
                "version": d.version,
                "purl": f"pkg:pypi/{d.metadata['Name'].lower()}@{d.version}",
            }
            for d in dependencies
        ],
    }
    dist = ROOT / "dist"
    (dist / "DeskTranslate-2.0.0b1-sbom.json").write_text(
        json.dumps(sbom, indent=2), encoding="utf-8"
    )
    notices = dist / "DeskTranslate/THIRD_PARTY_NOTICES"
    notices.mkdir(exist_ok=True)
    for name in ("LICENSE", "README.md", "SECURITY.md"):
        path = ROOT / name
        if path.is_file():
            shutil.copyfile(path, dist / "DeskTranslate" / name)
    for distribution in dependencies:
        for file in distribution.files or []:
            if (
                file.name.lower().startswith(("license", "copying", "notice"))
                or "licenses" in file.parts
            ) and ".." not in file.parts:
                source = distribution.locate_file(file)
                if source.is_file():
                    target = notices / distribution.metadata["Name"] / Path(*file.parts)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, target)
    if (ROOT / "packaging/licenses").is_dir():
        shutil.copytree(
            ROOT / "packaging/licenses", notices / "Qt-source-licenses", dirs_exist_ok=True
        )
    shutil.copyfile(ROOT / "docs/third-party.md", dist / "DeskTranslate" / "THIRD_PARTY.md")
    shutil.make_archive(
        str(dist / "DeskTranslate-2.0.0b1-Portable-x64"), "zip", dist, "DeskTranslate"
    )
    if installer:
        compiler = (
            os.environ.get("ISCC_PATH")
            or shutil.which("ISCC")
            or next(
                (
                    str(p)
                    for p in (
                        ROOT / ".tools/inno/ISCC.exe",
                        Path("C:/Program Files (x86)/Inno Setup 6/ISCC.exe"),
                        Path("C:/Program Files/Inno Setup 6/ISCC.exe"),
                    )
                    if p.is_file()
                ),
                None,
            )
        )
        if not compiler:
            raise SystemExit(
                "Portable build is ready. Install Inno Setup 6 or put ISCC on PATH to compile the installer."
            )
        subprocess.run([compiler, str(ROOT / "packaging/installer.iss")], check=True, cwd=ROOT)
    hashes = []
    for path in sorted(dist.iterdir()):
        if path.is_file() and path.name != "SHA256SUMS.txt":
            with path.open("rb") as stream:
                hashes.append(f"{hashlib.file_digest(stream, 'sha256').hexdigest()}  {path.name}")
    (dist / "SHA256SUMS.txt").write_text("\n".join(hashes) + "\n", encoding="utf-8")
    app.quit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--installer", action="store_true")
    build(parser.parse_args().installer)
