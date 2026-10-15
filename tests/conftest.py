"""Routine tests stay off the real desktop, network, vault and global shortcuts."""

from __future__ import annotations

import ctypes
import ipaddress
import os
import socket

import pytest

# Set this before test modules import Qt. An inherited native backend must not
# turn harmless widget/component tests into real foreground windows.
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_SCALE_FACTOR"] = "1"


def pytest_sessionstart(session):
    from PySide6.QtGui import QGuiApplication

    existing = QGuiApplication.instance()
    if existing is not None and existing.platformName() != "offscreen":
        raise pytest.UsageError(
            "Routine tests require a fresh offscreen process; an existing native Qt app is unsafe"
        )


def require_loopback(host: object) -> None:
    if host is None:
        return
    if isinstance(host, bytes):
        host = host.decode("ascii")
    if host == "localhost":
        return
    try:
        if ipaddress.ip_address(str(host)).is_loopback:
            return
    except ValueError:
        pass
    raise AssertionError("Routine tests may connect only to loopback; use a mock transport")


@pytest.fixture(autouse=True)
def isolated_system_boundaries(monkeypatch, tmp_path):
    """Keep production validation logic; replace only its external OS boundaries."""
    import keyring
    import mss
    from PySide6.QtGui import QDesktopServices, QScreen

    monkeypatch.setenv("DESKTRANSLATE_DATA_DIR", str(tmp_path / "app-data"))

    class MemoryVault:
        # Simulates an approved backend; dedicated tests override this to check
        # rejection. Nothing calls the actual account's credential manager.
        __module__ = "keyring.backends.Windows"

        def __init__(self):
            self.values = {}

        def get_password(self, service, account):
            return self.values.get((service, account))

        def set_password(self, service, account, value):
            self.values[service, account] = value

        def delete_password(self, service, account):
            self.values.pop((service, account), None)

    vault = MemoryVault()
    monkeypatch.setattr(keyring, "get_keyring", lambda: vault)

    def forbidden(*args, **kwargs):
        raise AssertionError("Real desktop/browser access is excluded from routine tests")

    monkeypatch.setattr(mss, "mss", forbidden)
    monkeypatch.setattr(QScreen, "grabWindow", forbidden)
    monkeypatch.setattr(QDesktopServices, "openUrl", forbidden)

    if os.name == "nt":
        # Exercise Hotkeys.register/close/conflict logic without claiming keys
        # from whatever application the user is currently typing in.
        monkeypatch.setattr(ctypes.windll.user32, "RegisterHotKey", lambda *args: True)
        monkeypatch.setattr(ctypes.windll.user32, "UnregisterHotKey", lambda *args: True)

    connect, connect_ex, resolve = (
        socket.socket.connect,
        socket.socket.connect_ex,
        socket.getaddrinfo,
    )

    def local_connect(sock, address):
        if isinstance(address, tuple):
            require_loopback(address[0])
        return connect(sock, address)

    def local_connect_ex(sock, address):
        if isinstance(address, tuple):
            require_loopback(address[0])
        return connect_ex(sock, address)

    def local_resolve(host, *args, **kwargs):
        require_loopback(host)
        return resolve(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", local_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", local_connect_ex)
    monkeypatch.setattr(socket, "getaddrinfo", local_resolve)
