"""Opt-in, offscreen frozen relaunch/crash checks using isolated synthetic preferences."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from desktranslate import __version__
from desktranslate.settings import Settings, SettingsStore


def qualify(program: Path) -> dict:
    info = json.loads((program.parent / "build-info.json").read_text(encoding="utf-8"))
    if (
        program.name != "DeskTranslate.exe"
        or not (program.parent / "managed-runtime.txt").is_file()
        or info["version"] != __version__
    ):
        raise ValueError("Use a verified, matching DeskTranslate managed runtime, not an installer")
    report = {
        "version": __version__,
        "source_sha256": info["source_sha256"],
        "executable_sha256": hashlib.sha256(program.read_bytes()).hexdigest(),
        "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "scope": "Actual frozen executable, offscreen Qt, owned local pipes, system-only PATH and isolated authored preferences. No desktop input/capture/media or installation. Native foreground restore, cross-account ACL and clean consumer Windows not tested.",
        "checks": {},
        "passed": False,
    }
    checks = report["checks"]
    primary = None
    stage = "startup"
    with tempfile.TemporaryDirectory(prefix="desktranslate-authored-instance-") as temporary:
        owned = Path(temporary)
        store = SettingsStore(owned / "翻訳 data")
        store.save(Settings(source="ko", target="es", onboarding_done=True))
        original = store.path.read_bytes()
        environment = dict(os.environ)
        for name in ("PYTHONPATH", "PYTHONHOME", "QT_PLUGIN_PATH", "QML2_IMPORT_PATH"):
            environment.pop(name, None)
        environment.update(
            DESKTRANSLATE_DATA_DIR=str(store.directory),
            QT_QPA_PLATFORM="offscreen",
            QT_SCALE_FACTOR="1",
            LOCALAPPDATA=str(owned / "isolated AppData"),
            PATH=os.pathsep.join(
                [str(Path(os.environ["SYSTEMROOT"]) / "System32"), os.environ["SYSTEMROOT"]]
            ),
        )
        options = dict(
            cwd=owned,
            env=environment,
            creationflags=subprocess.CREATE_NO_WINDOW,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            primary = subprocess.Popen([str(program), "--demo"], **options)
            deadline = time.monotonic() + 15
            while (
                not (store.directory / "instance.lock").exists()
                and primary.poll() is None
                and time.monotonic() < deadline
            ):
                time.sleep(0.05)
            assert (store.directory / "instance.lock").exists() and primary.poll() is None
            stage = "relaunch"
            duplicate = subprocess.run([str(program), "--demo"], timeout=15, **options)
            checks["relaunch_existing_frozen_owner"] = (
                duplicate.returncode == 0 and primary.poll() is None
            )
            stage = "verification_isolation"
            probe = subprocess.run([str(program), "--smoke-test"], timeout=15, **options)
            checks["verification_refuses_active_data_without_activation"] = (
                probe.returncode == 1 and primary.poll() is None
            )
            stage = "dead_owner_recovery"
            primary.terminate()  # Only this owned, offscreen fixture is deliberately crashed.
            primary.wait(10)
            recovery = subprocess.run([str(program), "--smoke-test"], timeout=20, **options)
            checks["frozen_dead_owner_recovery"] = recovery.returncode == 0
            checks["ownership_removed_after_clean_exit"] = not (
                store.directory / "instance.lock"
            ).exists()
            checks["preferences_retained"] = original == store.path.read_bytes()
            report["passed"] = len(checks) == 5 and all(checks.values())
        except Exception as error:
            report.update(failure_category=type(error).__name__, failure_stage=stage)
        finally:
            if primary and primary.poll() is None:
                primary.kill()
                primary.wait(10)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--component-test",
        action="store_true",
        help="Explicitly permit short owned-process crash checks; no real desktop",
    )
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path(".audit/packaged-instance.json"))
    args = parser.parse_args()
    if not args.component_test or os.name != "nt":
        parser.error("Frozen Windows ownership qualification requires --component-test")
    script = str(Path(__file__).resolve())
    if os.environ.get("DESKTRANSLATE_INSTANCE_PROBE_CHILD") != script:
        from qualification_policy import run_bounded_probe

        return run_bounded_probe(
            [sys.executable, script, *sys.argv[1:]],
            dict(os.environ, DESKTRANSLATE_INSTANCE_PROBE_CHILD=script),
            90,
            label="Frozen ownership",
        )
    report = qualify(args.executable.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
