import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

import pytest
from tools.validate import commands

from desktranslate.errors import CredentialError
from desktranslate.hotkeys import Hotkeys
from desktranslate.security import CredentialStore


def test_widget_tests_cannot_inherit_the_native_desktop_backend():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    assert os.environ["QT_QPA_PLATFORM"] == "offscreen"
    assert app.platformName() == "offscreen"


def test_existing_native_qt_app_is_rejected_before_routine_tests(monkeypatch):
    from types import SimpleNamespace

    from conftest import pytest_sessionstart
    from PySide6.QtGui import QGuiApplication

    monkeypatch.setattr(
        QGuiApplication, "instance", lambda: SimpleNamespace(platformName=lambda: "windows")
    )
    with pytest.raises(pytest.UsageError, match="offscreen"):
        pytest_sessionstart(None)


def test_routine_network_rejects_remote_connect_and_dns_before_io():
    with socket.socket() as stream, pytest.raises(AssertionError, match="loopback"):
        stream.connect(("203.0.113.1", 443))
    with pytest.raises(AssertionError, match="loopback"):
        socket.getaddrinfo("remote.example", 443)


def test_routine_vault_is_isolated_and_unapproved_backends_still_fail(monkeypatch):
    import keyring

    vault = CredentialStore()
    vault.set("authored", "synthetic-test-value")
    assert vault.get("authored") == "synthetic-test-value"
    vault.delete("authored")
    assert vault.get("authored") == ""
    monkeypatch.setattr(keyring, "get_keyring", lambda: object())
    with pytest.raises(CredentialError):
        vault.set("authored", "synthetic-test-value")


@pytest.mark.skipif(os.name != "nt", reason="Windows shortcut boundary")
def test_shortcut_conflict_logic_runs_without_claiming_real_keys(monkeypatch):
    import ctypes

    monkeypatch.setattr(ctypes.windll.user32, "RegisterHotKey", lambda *args: False)
    shortcuts = Hotkeys({"once": lambda: None})
    try:
        assert shortcuts.register({"once": "Ctrl+Alt+T"}) == ["Ctrl+Alt+T"]
        assert not shortcuts.registered
    finally:
        shortcuts.close()


def test_routine_desktop_capture_and_browser_launch_fail_closed():
    import mss
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices

    with pytest.raises(AssertionError, match="desktop"):
        mss.mss()
    with pytest.raises(AssertionError, match="desktop"):
        QDesktopServices.openUrl(QUrl("https://example.com"))


@pytest.mark.parametrize(
    "script",
    [
        "e2e_desktop.py",
        "qualify_ui.py",
        "qualify_window.py",
        "qualify_window_loop.py",
        "qualify_selection_motion.py",
    ],
)
def test_native_probes_require_explicit_desktop_opt_in(script):
    root = Path(__file__).resolve().parents[1]
    # If a future change removes the CLI guard, this regression must fail
    # without itself opening a window or reading the real desktop.
    bootstrap = """
import pathlib,runpy,sys
from PySide6 import QtGui,QtWidgets
import mss
def forbidden(*args,**kwargs):
    raise AssertionError('Native desktop boundary reached without opt-in')
QtWidgets.QApplication=forbidden
QtGui.QScreen.grabWindow=forbidden
QtGui.QDesktopServices.openUrl=forbidden
mss.mss=forbidden
script=sys.argv[1]
sys.argv=[script]
sys.path.insert(0,str(pathlib.Path(script).parent))
runpy.run_path(script,run_name='__main__')
"""
    result = subprocess.run(
        [sys.executable, "-c", bootstrap, str(root / "tools" / script)],
        cwd=root,
        capture_output=True,
        timeout=15,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    assert result.returncode == 2
    assert b"requires --interactive-desktop" in result.stderr


def test_default_validation_contains_no_install_media_capture_or_endurance():
    default = commands(False, Path(".audit/pytest.xml"))
    assert any("pytest" in command for command in default)
    assert all(
        not any(word in argument for word in ("qualify_", "soak.py", "installer", "e2e_"))
        for command in default
        for argument in command
    )


def test_extended_stress_requires_explicit_opt_in_before_starting():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(root / "tools/soak.py"), "--duration", "7200"],
        cwd=root,
        capture_output=True,
        timeout=15,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    assert result.returncode == 2
    assert b"--long-running" in result.stderr


@pytest.mark.parametrize(
    "script",
    [
        "profile_ocr.py",
        "evaluate.py",
        "evaluate_confidence.py",
        "evaluate_media.py",
        "evaluate_layout.py",
    ],
)
def test_background_ocr_benchmarks_require_explicit_opt_in(script, tmp_path):
    root = Path(__file__).resolve().parents[1]
    output = tmp_path / "not-created.json"
    result = subprocess.run(
        [sys.executable, str(root / "tools" / script), "--output", str(output)],
        cwd=root,
        capture_output=True,
        timeout=15,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    assert result.returncode == 2 and b"--ocr-experiment" in result.stderr
    assert not output.exists()


def test_real_ocr_product_probe_is_an_explicit_separate_command(tmp_path):
    root = Path(__file__).resolve().parents[1]
    output = tmp_path / "not-created.json"
    result = subprocess.run(
        [sys.executable, str(root / "tools/qualify_product.py"), "--output", str(output)],
        cwd=root,
        capture_output=True,
        timeout=15,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    assert result.returncode == 2 and b"--component-test" in result.stderr
    assert not output.exists()


def test_frozen_process_probe_requires_opt_in_before_launching_anything(tmp_path):
    root = Path(__file__).resolve().parents[1]
    output = tmp_path / "not-created.json"
    result = subprocess.run(
        [
            sys.executable,
            str(root / "tools/qualify_frozen_instance.py"),
            "--executable",
            str(tmp_path / "DeskTranslate.exe"),
            "--output",
            str(output),
        ],
        cwd=root,
        capture_output=True,
        timeout=15,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    assert result.returncode == 2 and b"--component-test" in result.stderr
    assert not output.exists()


def test_frozen_probe_refuses_installer_before_process_execution(tmp_path, monkeypatch):
    import json

    from tools.qualify_frozen_instance import qualify

    from desktranslate import __version__

    (tmp_path / "build-info.json").write_text(
        json.dumps({"version": __version__}), encoding="utf-8"
    )
    (tmp_path / "managed-runtime.txt").write_text("authored marker", encoding="utf-8")

    def forbidden(*args, **kwargs):
        raise AssertionError("No executable may run before runtime validation")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    with pytest.raises(ValueError, match="not an installer"):
        qualify(tmp_path / "Setup.exe")


@pytest.mark.skipif(os.name != "nt", reason="Owned Windows supervisor lifecycle")
def test_manual_probe_timeout_terminates_owned_worker_tree(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "tools"))
    from qualification_policy import run_bounded_probe

    result = run_bounded_probe(
        [sys.executable, "-c", "import time; time.sleep(20)"], dict(os.environ), 0.1
    )
    assert result == 124


@pytest.mark.skipif(os.name != "nt", reason="Windows qualification polling")
@pytest.mark.parametrize("completes", [True, False])
def test_installer_cleanup_polling_waits_or_fails_without_deleting_sentinels(tmp_path, completes):
    shell = shutil.which("pwsh") or shutil.which("powershell")
    assert shell
    helper = Path(__file__).resolve().parents[1] / "tools/qualification_wait.ps1"
    sentinel = tmp_path / "authored.txt"
    sentinel.write_text("keep", encoding="utf-8")
    script = tmp_path / "polling.ps1"
    script.write_text(
        "param([string]$Helper)\n"
        ". $Helper\n"
        "$state = @{ attempts=0 }\n"
        "try {\n"
        f" Wait-QualificationCondition -TimeoutSeconds {2 if completes else 0.1} -IntervalMilliseconds 1 -Condition {{\n"
        "  $state.attempts++; " + ("$state.attempts -ge 3" if completes else "$false") + "\n }\n"
        " if ($state.attempts -lt 3) { exit 2 }; exit 0\n"
        "} catch { if ($_.Exception.Message -notmatch 'did not complete') { exit 3 }; exit 4 }\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [shell, "-NoProfile", "-NonInteractive", "-File", str(script), str(helper)],
        capture_output=True,
        timeout=15,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    assert result.returncode == (0 if completes else 4), result.stderr.decode(errors="replace")
    assert sentinel.read_text(encoding="utf-8") == "keep"
