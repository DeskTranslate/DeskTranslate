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

from packaging.version import Version
from release_support import (
    Signer,
    git_trace,
    shipped_distributions,
    stable_gate,
    version_gate,
    windows_version,
)

from desktranslate import __version__

ROOT = Path(__file__).resolve().parents[1]


def build(installer: bool, signed: bool = False, stable: bool = False, tag: str = "") -> None:
    from PIL import Image
    from PyInstaller.utils.hooks import collect_data_files
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtWidgets import QApplication

    version_gate(ROOT, tag)
    # Every final-version build enforces qualification, including CI and local
    # invocations that accidentally omit --stable.
    if stable or not Version(__version__).is_prerelease:
        stable_gate(ROOT, tag)
        if not signed or not installer:
            raise ValueError("Stable builds require verified publisher signing and an installer")
    signer = Signer() if signed else None
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
    numeric = tuple(int(value) for value in windows_version().split("."))
    version_file = build_dir / "version-info.txt"
    version_file.write_text(
        "VSVersionInfo(ffi=FixedFileInfo(filevers="
        + repr(numeric)
        + ", prodvers="
        + repr(numeric)
        + ", mask=0x3f, flags=0, OS=0x40004, fileType=1, subtype=0, date=(0,0)), kids=["
        + "StringFileInfo([StringTable('040904B0',["
        + "StringStruct('CompanyName','DeskTranslate'),StringStruct('FileDescription','DeskTranslate screen translator'),"
        + f"StringStruct('FileVersion','{__version__}'),StringStruct('ProductVersion','{__version__}'),"
        + "StringStruct('ProductName','DeskTranslate'),StringStruct('OriginalFilename','DeskTranslate.exe')])]),"
        + "VarFileInfo([VarStruct('Translation',[1033,1200])])])",
        encoding="utf-8",
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
        "--version-file",
        str(version_file),
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
        "--exclude-module",
        "pytest",
        "--exclude-module",
        "_pytest",
        "--exclude-module",
        "numpy.testing",
        "--exclude-module",
        "numpy.f2py",
        "--exclude-module",
        "setuptools",
        "--exclude-module",
        "wheel",
        "--exclude-module",
        "pip",
        "--exclude-module",
        "build",
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
        (
            d
            for d in importlib.metadata.distributions()
            if d.metadata["Name"].lower() != "desktranslate"
        ),
        key=lambda d: d.metadata["Name"].lower(),
    )
    runtime = shipped_distributions(ROOT)
    trace = git_trace(ROOT)
    dist = ROOT / "dist"
    artifacts: list[Path] = []
    for scope, inventory in (("build", dependencies), ("runtime", runtime)):
        sbom = {
            "bomFormat": "CycloneDX",
            "specVersion": "1.5",
            "version": 1,
            "metadata": {
                "component": {
                    "type": "application",
                    "name": "DeskTranslate",
                    "version": __version__,
                },
                "properties": [
                    {"name": "scope", "value": scope + " dependency inventory"},
                    {"name": "git_commit", "value": str(trace["git_commit"])},
                    {"name": "source_sha256", "value": str(trace["source_sha256"])},
                ],
            },
            "components": [
                {
                    "type": "library",
                    "name": d.metadata["Name"],
                    "version": d.version,
                    "purl": f"pkg:pypi/{d.metadata['Name'].lower()}@{d.version}",
                }
                for d in inventory
            ],
        }
        path = dist / f"DeskTranslate-{__version__}-{scope}-sbom.json"
        path.write_text(json.dumps(sbom, indent=2), encoding="utf-8")
        artifacts.append(path)
    build_info = {
        "version": __version__,
        "windows_version": windows_version(),
        **trace,
        "publisher_signed": bool(signer),
        "ocr_backend": "CPUExecutionProvider",
    }
    (dist / "DeskTranslate/build-info.json").write_text(
        json.dumps(build_info, indent=2), encoding="utf-8"
    )
    notices = dist / "DeskTranslate/THIRD_PARTY_NOTICES"
    notices.mkdir(exist_ok=True)
    for name in ("LICENSE", "README.md", "SECURITY.md"):
        path = ROOT / name
        if path.is_file():
            shutil.copyfile(path, dist / "DeskTranslate" / name)
    for distribution in runtime:
        for file in distribution.files or []:
            if (
                file.name.lower().startswith(("license", "copying", "notice"))
                or (
                    "licenses" in file.parts
                    and file.suffix.lower() in {"", ".txt", ".md", ".rst", ".html"}
                )
            ) and (
                ".." not in file.parts
                and "__pycache__" not in file.parts
                and file.suffix.lower() not in {".py", ".pyc", ".pyo", ".pyd", ".dll", ".exe"}
            ):
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
    executable = dist / "DeskTranslate/DeskTranslate.exe"
    if signer:
        signer.sign(executable)
    artifacts.append(
        Path(
            shutil.make_archive(
                str(dist / f"DeskTranslate-{__version__}-Portable-x64"),
                "zip",
                dist,
                "DeskTranslate",
            )
        )
    )
    sources = dist / f"DeskTranslate-{__version__}-LibrarySources.zip"
    if sources.exists():
        artifacts.append(sources)
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
        command = [compiler, f"/DAppVersion={__version__}", f"/DFileVersion={windows_version()}"]
        if signer:
            command.extend(["/DSignedBuild=1", "/SDeskTranslate=" + signer.inno_command()])
        command.append(str(ROOT / "packaging/installer.iss"))
        subprocess.run(command, check=True, cwd=ROOT)
        setup = dist / f"DeskTranslate-{__version__}-Setup-x64.exe"
        if signer:
            signer.verify(setup)
        artifacts.append(setup)
    provenance = {
        "_type": "https://in-toto.io/Statement/v1",
        "predicateType": "https://github.com/DeskTranslate/DeskTranslate/blob/main/docs/build-provenance-v1.md",
        "subject": [
            {"name": path.name, "digest": {"sha256": hashlib.sha256(path.read_bytes()).hexdigest()}}
            for path in artifacts
        ],
        "predicate": {
            **build_info,
            "builder": "tools/build.py",
            "build_environment_sbom": f"DeskTranslate-{__version__}-build-sbom.json",
            "runtime_sbom": f"DeskTranslate-{__version__}-runtime-sbom.json",
            "claim": "Local build statement; not a hosted or signed attestation",
        },
    }
    provenance_path = dist / f"DeskTranslate-{__version__}-provenance.json"
    provenance_path.write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    artifacts.append(provenance_path)
    hashes = []
    for path in sorted(artifacts):
        with path.open("rb") as stream:
            hashes.append(f"{hashlib.file_digest(stream, 'sha256').hexdigest()}  {path.name}")
    (dist / "SHA256SUMS.txt").write_text("\n".join(hashes) + "\n", encoding="utf-8")
    app.quit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--installer", action="store_true")
    parser.add_argument(
        "--signed",
        action="store_true",
        help="Require trusted Authenticode publisher signing and timestamps",
    )
    parser.add_argument(
        "--stable",
        action="store_true",
        help="Enforce stable manual, soak, version and signing gates",
    )
    parser.add_argument("--tag", default="", help="Exact release tag; required for stable")
    options = parser.parse_args()
    build(options.installer, options.signed, options.stable, options.tag)
