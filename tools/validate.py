"""Routine, headless quality checks. No desktop capture, playback or OS changes."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def commands(predeploy: bool, junit: Path) -> list[list[str]]:
    checks = [
        ["-m", "ruff", "check", "src", "tests", "tools"],
        ["-m", "ruff", "format", "--check", "src", "tests", "tools"],
        ["-m", "mypy", "src"],
        ["-m", "pytest", "-q", "--junitxml=" + str(junit)],
        ["-m", "desktranslate", "--smoke-test"],
    ]
    if predeploy:
        checks += [
            ["-m", "pip", "check"],
            [
                "-m",
                "pip_audit",
                "--require-hashes",
                "--disable-pip",
                "-r",
                "requirements-windows.lock",
                "-f",
                "json",
                "-o",
                ".audit/dependency-audit.json",
            ],
            ["tools/privacy_scan.py", "--history", "--output", ".audit/privacy-source.json"],
            ["-m", "build", "--no-isolation", "--outdir", "dist-python"],
        ]
    return checks


def main() -> int:
    if __package__:
        from .qualification_policy import run_bounded_probe
    else:
        from qualification_policy import run_bounded_probe

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--predeploy",
        action="store_true",
        help="Also audit dependencies/history and build wheel/sdist; network/CPU work, no desktop",
    )
    parser.add_argument("--junitxml", type=Path, default=Path(".audit/pytest.xml"))
    parser.add_argument(
        "--frozen",
        type=Path,
        help="Also smoke-test an existing executable offscreen; does not install it",
    )
    args = parser.parse_args()
    environment = dict(os.environ)
    environment.update(
        QT_QPA_PLATFORM="offscreen",
        QT_SCALE_FACTOR="1",
        DESKTRANSLATE_DATA_DIR=str(ROOT / ".test-data/routine-validation"),
    )
    (ROOT / ".audit").mkdir(exist_ok=True)
    for arguments in commands(args.predeploy, args.junitxml):
        print("Checking: python " + " ".join(arguments), flush=True)
        result = run_bounded_probe(
            [sys.executable, *arguments],
            environment,
            600,
            cwd=ROOT,
            label="Validation",
        )
        if result:
            return result
    if args.frozen:
        return run_bounded_probe(
            [str(args.frozen.resolve()), "--smoke-test"],
            environment,
            30,
            cwd=ROOT,
            label="Frozen smoke",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
