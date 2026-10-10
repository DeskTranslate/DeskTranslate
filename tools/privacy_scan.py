"""Release privacy gate. Reports locations/categories, never matched content."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import zipfile
from pathlib import Path
from typing import BinaryIO

ROOT = Path(__file__).resolve().parents[1]


def signatures() -> list[tuple[str, re.Pattern[bytes]]]:
    result = [
        (
            "credential_signature",
            re.compile(
                rb"(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{60,}|sk-(?:proj-)?[A-Za-z0-9_-]{40,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
            ),
        )
    ]
    private_home = os.environ.get("USERPROFILE", "")
    if private_home:
        for separator in ("/", "\\"):
            value = private_home.replace("\\", separator)
            for encoding in ("utf-8", "utf-16-le"):
                result.append(
                    (
                        "private_build_home",
                        re.compile(re.escape(value.encode(encoding)), re.IGNORECASE),
                    )
                )
    machine = os.environ.get("COMPUTERNAME", "")
    if len(machine) >= 6:
        result.append(
            (
                "private_workstation",
                re.compile(rb"\b" + re.escape(machine.encode()) + rb"\b", re.IGNORECASE),
            )
        )
    return result


def scan_stream(stream: BinaryIO, patterns: list[tuple[str, re.Pattern[bytes]]]) -> set[str]:
    hits: set[str] = set()
    previous = b""
    while chunk := stream.read(1024 * 1024):
        data = previous + chunk
        hits.update(category for category, pattern in patterns if pattern.search(data))
        previous = data[-4096:]
    return hits


def run(artifacts: bool, history: bool) -> dict[str, object]:
    import io

    patterns = signatures()
    findings = []
    counts = {
        "tree_files": 0,
        "history_blobs": 0,
        "artifact_members": 0,
        "release_files": 0,
        "release_archive_members": 0,
        "frozen_modules": 0,
    }

    def checked(location: str, stream: BinaryIO) -> None:
        categories = scan_stream(stream, patterns)
        if categories:
            findings.append({"location": location, "categories": sorted(categories)})

    tracked = (
        subprocess.check_output(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=ROOT
        )
        .decode()
        .split("\0")
    )
    for name in sorted(set(tracked)):
        path = ROOT / name
        if name and path.is_file():
            with path.open("rb") as stream:
                checked("tree/" + name, stream)
            counts["tree_files"] += 1
    if history:
        objects = (
            subprocess.check_output(["git", "rev-list", "--objects", "--all"], cwd=ROOT)
            .decode()
            .splitlines()
        )
        process = subprocess.Popen(
            ["git", "cat-file", "--batch"], cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE
        )
        assert process.stdin and process.stdout
        try:
            for entry in objects:
                identity = entry.split(" ", 1)[0]
                process.stdin.write((identity + "\n").encode())
                process.stdin.flush()
                header = process.stdout.readline().decode().split()
                length = int(header[2])
                data = process.stdout.read(length)
                process.stdout.read(1)
                if header[1] == "blob":
                    checked("history/blob/" + identity, io.BytesIO(data))
                    counts["history_blobs"] += 1
        finally:
            process.stdin.close()
            process.wait(timeout=10)
    if artifacts:
        from PyInstaller.archive.readers import CArchiveReader

        directory = ROOT / "dist/DeskTranslate"
        for path in directory.rglob("*"):
            if path.is_file():
                with path.open("rb") as stream:
                    checked("app/" + path.relative_to(directory).as_posix(), stream)
                counts["artifact_members"] += 1
                if path.suffix == ".zip":
                    with zipfile.ZipFile(path) as archive:
                        for name in archive.namelist():
                            with archive.open(name) as stream:
                                checked("app/archive/" + name, stream)
        archive = CArchiveReader(str(directory / "DeskTranslate.exe"))
        for name, entry in archive.toc.items():
            if entry[-1] == "z":
                pyz = archive.open_embedded_archive(name)
                for module in pyz.toc:
                    data = pyz.extract(module, raw=True)
                    if data:
                        checked("frozen/" + module, io.BytesIO(data))
                        counts["frozen_modules"] += 1
            elif entry[-1] in {"s", "m", "M"}:
                checked("frozen/" + name, io.BytesIO(archive.extract(name)))
        sums = ROOT / "dist/SHA256SUMS.txt"
        names = [line.split("  ", 1)[1] for line in sums.read_text().splitlines()]
        for name in [*names, sums.name]:
            if Path(name).name != name:
                raise ValueError("Release checksum paths must be plain filenames")
            path = ROOT / "dist" / name
            with path.open("rb") as stream:
                checked("release/" + name, stream)
            counts["release_files"] += 1
            if path.suffix == ".zip":
                with zipfile.ZipFile(path) as release_archive:
                    for member in release_archive.infolist():
                        if not member.is_dir():
                            with release_archive.open(member) as stream:
                                checked("release/" + name + "/" + member.filename, stream)
                            counts["release_archive_members"] += 1
    return {
        "scope": "Publishable tree, optional reachable Git blobs, extracted frozen code/runtime files, and checksum-listed release files/archive members; signature scan cannot prove absence of every secret. Public contributor identities and third-party attribution are retained.",
        "counts": counts,
        "findings": findings,
        "passed": not findings,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts", action="store_true")
    parser.add_argument("--history", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("docs/privacy-scan.json"))
    args = parser.parse_args()
    report = run(args.artifacts, args.history)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
    raise SystemExit(0 if report["passed"] else 1)
