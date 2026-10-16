import os
import subprocess
import sys
import time

import pytest
from PySide6.QtNetwork import QLocalSocket
from PySide6.QtWidgets import QApplication

from desktranslate.instance import ACTIVATE, InstanceError, SingleInstance

pytestmark = pytest.mark.headless_ui

SAFE_APP = """
import os
import mss
from PySide6 import QtGui, QtWidgets
from desktranslate.hotkeys import Hotkeys
from desktranslate.security import CredentialStore
def forbidden(*args,**kwargs):
    raise AssertionError('Real desktop/browser/vault access forbidden in child fixtures')
mss.mss = forbidden
QtGui.QScreen.grabWindow = forbidden
QtGui.QDesktopServices.openUrl = forbidden
Hotkeys.register = lambda *args: []
Hotkeys.register_first_run = lambda self,values: (values,[])
Hotkeys.watch_session = lambda *args: True
CredentialStore.get = lambda *args: ''
CredentialStore.set = forbidden
CredentialStore.delete = forbidden
Base = QtWidgets.QApplication
class HeadlessOnly(Base):
    def __init__(self,*args):
        assert os.environ.get('QT_QPA_PLATFORM') == 'offscreen', 'Native backend forbidden in tests'
        super().__init__(*args)
QtWidgets.QApplication = HeadlessOnly
"""

SAFE_SMOKE = (
    SAFE_APP
    + """
from desktranslate.app import main
raise SystemExit(main())
"""
)


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def until(app, condition, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if condition():
            return
        time.sleep(0.01)
    raise AssertionError("Owned instance fixture did not complete")


def test_lifetime_lock_prevents_competing_writers_but_separates_portable_data(app, tmp_path):
    directory = tmp_path / "翻訳 data"
    owner, duplicate, separate = (
        SingleInstance(directory),
        SingleInstance(directory / "child/.."),
        SingleInstance(tmp_path / "another portable folder"),
    )
    try:
        assert owner.acquire() and owner.acquire()
        sentinel = directory / "settings.json"
        sentinel.write_text("authored preferences", encoding="utf-8")
        os.utime(directory / "instance.lock", (1, 1))
        assert not duplicate.acquire()  # An old but live owner is never displaced.
        duplicate.close()
        assert owner.owned and sentinel.read_text(encoding="utf-8") == "authored preferences"
        assert separate.acquire()
        owner.close()
        assert duplicate.acquire()
    finally:
        for instance in (owner, duplicate, separate):
            instance.close()
            instance.deleteLater()


def test_activation_accepts_only_bounded_command_and_closes_idle_peers(app, tmp_path):
    owner = SingleInstance(tmp_path)
    received = []
    owner.activated.connect(lambda: received.append(True))
    assert owner.acquire()
    clients = []
    try:
        for message in (b"arbitrary-command", ACTIVATE):
            client = QLocalSocket()
            clients.append(client)
            client.connectToServer(owner.name)
            assert client.waitForConnected(500)
            client.write(message)
            client.flush()
            until(
                app,
                lambda expected=message, peer=client: (
                    not owner.server.hasPendingConnections()
                    and (
                        bool(received)
                        if expected == ACTIVATE
                        else peer.state() == QLocalSocket.LocalSocketState.UnconnectedState
                    )
                ),
            )
        assert received == [True]
        until(app, lambda: not owner.buffers)
        for _ in range(10):
            client = QLocalSocket()
            clients.append(client)
            client.connectToServer(owner.name)
            app.processEvents()
        until(app, lambda: len(owner.buffers) == 4)
        assert len(owner.buffers) <= 4
        until(app, lambda: not owner.buffers, timeout=3)
        assert received == [True]
    finally:
        for client in clients:
            client.abort()
        owner.close()
        owner.deleteLater()


def test_fragmented_activation_waits_for_complete_command(app, tmp_path):
    owner, client, received = SingleInstance(tmp_path), QLocalSocket(), []
    owner.activated.connect(lambda: received.append(True))
    assert owner.acquire()
    try:
        client.connectToServer(owner.name)
        assert client.waitForConnected(500)
        client.write(ACTIVATE[:4])
        client.flush()
        until(app, lambda: any(len(buffer) == 4 for buffer in owner.buffers.values()))
        assert not received
        client.write(ACTIVATE[4:])
        client.flush()
        until(app, lambda: bool(received))
        assert received == [True]
    finally:
        client.abort()
        owner.close()
        owner.deleteLater()


def test_failed_activation_listener_releases_ownership_for_recovery(app, tmp_path, monkeypatch):
    failed, replacement = SingleInstance(tmp_path), SingleInstance(tmp_path)
    monkeypatch.setattr(failed.server, "listen", lambda name: False)
    try:
        with pytest.raises(InstanceError):
            failed.acquire()
        assert not failed.owned and replacement.acquire()
    finally:
        failed.close()
        replacement.close()
        failed.deleteLater()
        replacement.deleteLater()


def test_quitting_owner_rejects_activation_but_keeps_the_data_lock(app, tmp_path):
    owner, duplicate, client = SingleInstance(tmp_path), SingleInstance(tmp_path), QLocalSocket()
    received = []
    owner.activated.connect(lambda: received.append(True))
    owner.can_activate = lambda: False
    assert owner.acquire()
    try:
        client.connectToServer(owner.name)
        assert client.waitForConnected(500)
        client.write(ACTIVATE)
        client.flush()
        until(app, lambda: client.bytesAvailable() > 0)
        assert client.readAll().data() == b"busy\n" and not received
        assert not duplicate.acquire() and owner.owned
    finally:
        client.abort()
        owner.close()
        duplicate.close()
        owner.deleteLater()
        duplicate.deleteLater()


def test_unwritable_data_shape_preserves_existing_file_and_returns_safe_error(app, tmp_path):
    occupied = tmp_path / "authored-file"
    occupied.write_text("retain", encoding="utf-8")
    instance = SingleInstance(occupied)
    try:
        with pytest.raises(InstanceError):
            instance.acquire()
        assert occupied.read_text(encoding="utf-8") == "retain"
    finally:
        instance.close()
        instance.deleteLater()


@pytest.mark.native_process
def test_second_process_activates_existing_instance_without_claiming_data(app, tmp_path):
    owner = SingleInstance(tmp_path / "空の data")
    received = []
    owner.activated.connect(lambda: received.append(True))
    assert owner.acquire()
    code = """
import sys
from pathlib import Path
from PySide6.QtCore import QCoreApplication
from desktranslate.instance import SingleInstance
app = QCoreApplication([])
instance = SingleInstance(Path(sys.argv[1]))
assert not instance.acquire()
raise SystemExit(0 if instance.notify() else 2)
"""
    child = subprocess.Popen(
        [sys.executable, "-c", code, str(owner.directory)],
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    try:
        until(app, lambda: child.poll() is not None, timeout=10)
        assert child.returncode == 0 and received == [True]
        assert owner.owned
    finally:
        if child.poll() is None:
            child.kill()
        child.wait(5)
        owner.close()
        owner.deleteLater()


@pytest.mark.native_process
def test_crashed_owner_releases_data_without_forced_live_lock_removal(app, tmp_path):
    ready = tmp_path / "ready"
    data = tmp_path / "instance"
    code = """
import sys,time
from pathlib import Path
from PySide6.QtCore import QCoreApplication
from desktranslate.instance import SingleInstance
app = QCoreApplication([])
instance = SingleInstance(Path(sys.argv[1]))
assert instance.acquire()
Path(sys.argv[2]).write_text('ready',encoding='utf-8')
time.sleep(30)
"""
    child = subprocess.Popen(
        [sys.executable, "-c", code, str(data), str(ready)],
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    replacement = SingleInstance(data)
    try:
        until(app, ready.exists, timeout=10)
        assert not replacement.acquire()
        child.kill()  # Only this fixture's owned process is terminated.
        child.wait(5)
        assert replacement.acquire()
    finally:
        if child.poll() is None:
            child.kill()
        child.wait(5)
        replacement.close()
        replacement.deleteLater()


@pytest.mark.native_process
def test_smoke_duplicate_does_not_activate_the_user_or_report_false_success(app, tmp_path):
    owner = SingleInstance(tmp_path)
    received = []
    owner.activated.connect(lambda: received.append(True))
    assert owner.acquire()
    environment = dict(os.environ, DESKTRANSLATE_DATA_DIR=str(tmp_path), QT_QPA_PLATFORM="windows")
    try:
        result = subprocess.run(
            [sys.executable, "-c", SAFE_SMOKE, "--smoke-test"],
            env=environment,
            capture_output=True,
            timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        assert result.returncode == 1
        assert b"isolated data folder" in result.stderr
        app.processEvents()
        assert not received and owner.owned
    finally:
        owner.close()
        owner.deleteLater()


@pytest.mark.native_process
def test_headless_startup_io_failure_exits_without_blocking_dialog(app, tmp_path):
    occupied = tmp_path / "authored-file"
    occupied.write_text("retain", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-c", SAFE_SMOKE, "--smoke-test"],
        env=dict(os.environ, DESKTRANSLATE_DATA_DIR=str(occupied), QT_QPA_PLATFORM="windows"),
        capture_output=True,
        timeout=15,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    assert result.returncode == 1 and b"writable" in result.stderr
    assert occupied.read_text(encoding="utf-8") == "retain"


@pytest.mark.native_process
def test_actual_app_relaunch_restores_owned_window_then_releases_data_on_quit(app, tmp_path):
    from desktranslate.settings import Settings, SettingsStore

    store = SettingsStore(tmp_path / "翻訳 app data")
    store.save(Settings(onboarding_done=True, source="ko", target="es"))
    original = store.path.read_bytes()
    ready, restored, stop = (tmp_path / name for name in ("ready", "restored", "stop"))
    observed = (
        SAFE_APP
        + """
import os,sys
from pathlib import Path
from PySide6.QtCore import QTimer
import desktranslate.ui.window as ui
BaseWindow = ui.MainWindow
class Observed(BaseWindow):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fixture_timer = QTimer(self)
        def tick():
            if Path(os.environ['FIXTURE_STOP']).exists():
                self.quit()
        self.fixture_timer.timeout.connect(tick)
        self.fixture_timer.start(20)
        def ready():
            self.hide()
            Path(os.environ['FIXTURE_READY']).write_text('hidden',encoding='utf-8')
        QTimer.singleShot(100,ready)
        QTimer.singleShot(10000,self.quit)
    def showNormal(self):
        super().showNormal()
        assert self.isVisible()
        Path(os.environ['FIXTURE_RESTORED']).write_text('restored',encoding='utf-8')
ui.MainWindow = Observed
from desktranslate.app import main
raise SystemExit(main())
"""
    )
    environment = dict(
        os.environ,
        DESKTRANSLATE_DATA_DIR=str(store.directory),
        QT_QPA_PLATFORM="offscreen",
        FIXTURE_READY=str(ready),
        FIXTURE_RESTORED=str(restored),
        FIXTURE_STOP=str(stop),
    )
    primary = subprocess.Popen(
        [sys.executable, "-c", observed, "--demo"],
        env=environment,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    try:
        until(app, ready.exists, timeout=10)
        duplicate = subprocess.run(
            [sys.executable, "-c", SAFE_SMOKE, "--demo"],
            env=environment,
            capture_output=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        assert duplicate.returncode == 0, duplicate.stderr.decode(errors="replace")
        until(app, restored.exists)
        assert primary.poll() is None and store.path.read_bytes() == original
        stop.write_text("stop", encoding="utf-8")
        until(app, lambda: primary.poll() is not None, timeout=5)
        assert primary.returncode == 0 and not (store.directory / "instance.lock").exists()
    finally:
        if primary.poll() is None:
            primary.kill()
        primary.wait(5)


@pytest.mark.skipif(os.name != "nt", reason="Windows local-pipe native resource qualification")
def test_repeated_activation_cleanup_keeps_native_resources_bounded(app, tmp_path):
    from PySide6.QtCore import QCoreApplication, QEvent

    from desktranslate.metrics import process_resources

    baseline = None
    for index in range(24):
        owner, client = SingleInstance(tmp_path / str(index)), QLocalSocket()
        assert owner.acquire()
        try:
            client.connectToServer(owner.name)
            assert client.waitForConnected(500)
            client.write(ACTIVATE)
            client.flush()
            until(app, lambda peer=client: peer.bytesAvailable() > 0)
            assert client.readAll().data() == b"ok\n"
        finally:
            client.abort()
            client.deleteLater()
            owner.close()
            owner.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            app.processEvents()
        if index == 3:
            baseline = process_resources()
    final = process_resources()
    assert baseline and final
    assert final["handles"] - baseline["handles"] <= 12
    assert final["native_threads"] - baseline["native_threads"] <= 4
