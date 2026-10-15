"""Explicit boundary between routine validation and interactive desktop probes."""

from __future__ import annotations

import argparse
import contextlib
import os
import signal
import subprocess
import sys
from pathlib import Path


def run_bounded_probe(
    command: list[str],
    environment: dict[str, str],
    timeout: float,
    cwd: Path | None = None,
    label: str = "Manual probe",
) -> int:
    """A terminal Ctrl+C/timeout closes only the owned process tree."""
    child = subprocess.Popen(
        command,
        env=environment,
        cwd=cwd,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        start_new_session=os.name != "nt",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    job = None
    output = None
    try:
        if os.name == "nt":
            from desktranslate.processes import ProcessJob

            job = ProcessJob(child.pid)
        output, _ = child.communicate(timeout=timeout)
        return child.returncode
    except subprocess.TimeoutExpired:
        print(f"{label} timed out; closing its owned workers.", file=sys.stderr)
        return 124
    except KeyboardInterrupt:
        print(f"{label} interrupted; closing its owned workers.", file=sys.stderr)
        return 130
    finally:
        if job:
            job.close()
        elif os.name != "nt":
            with contextlib.suppress(ProcessLookupError):
                os.killpg(child.pid, signal.SIGKILL)
        if child.poll() is None:
            child.kill()
        if output is None:
            output, _ = child.communicate(timeout=10)
        else:
            child.wait(10)
        if child.stdout:
            child.stdout.close()
        if output:
            print(output, end="", flush=True)


def require_interactive_desktop() -> None:
    """Reject accidental invocation before the probe creates any windows."""
    parser = argparse.ArgumentParser(
        description="MANUAL DESKTOP QUALIFICATION: opens visible authored windows and may capture "
        "their pixels or change focus. Excluded from routine pytest/CI validation. "
        "Run only in a reserved desktop session; close other work first."
    )
    parser.add_argument(
        "--interactive-desktop",
        action="store_true",
        help="Explicitly opt into this foreground-dependent manual probe",
    )
    parser.add_argument(
        "--desktop-timeout",
        type=float,
        default=120,
        help="Hard cleanup deadline in seconds (1–300; default120); Ctrl+C also stops the tree",
    )
    selected, remaining = parser.parse_known_args()
    if not selected.interactive_desktop:
        parser.error("This manual probe requires --interactive-desktop; routine tests are headless")
    if os.name != "nt":
        parser.error("Native manual probes require Windows")
    if not 1 <= selected.desktop_timeout <= 300:
        parser.error("--desktop-timeout must be between1 and300 seconds")
    script = str(Path(sys.argv[0]).resolve())
    if os.environ.get("DESKTRANSLATE_MANUAL_PROBE_CHILD") != script:
        environment = dict(os.environ)
        environment["DESKTRANSLATE_MANUAL_PROBE_CHILD"] = script
        environment["QT_QPA_PLATFORM"] = "windows"
        raise SystemExit(
            run_bounded_probe(
                [sys.executable, script, "--interactive-desktop", *remaining],
                environment,
                selected.desktop_timeout,
            )
        )
    # Leave each probe's own arguments intact after consuming the common flag.
    sys.argv[1:] = remaining
