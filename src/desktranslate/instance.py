"""One settings writer per data directory, with a bounded user-only activation channel."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable
from functools import partial
from pathlib import Path

from PySide6.QtCore import QLockFile, QObject, QTimer, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from desktranslate.errors import DeskTranslateError

ACTIVATE = b"activate\n"


class InstanceError(DeskTranslateError):
    message = "DeskTranslate cannot reserve its data folder. Check folder permissions or extract the portable app to a writable folder."


class SingleInstance(QObject):
    activated = Signal()

    def __init__(self, directory: Path, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.directory = directory.resolve()
        identity = os.path.normcase(str(self.directory)).encode("utf-8")
        self.name = "DeskTranslate2-" + hashlib.sha256(identity).hexdigest()[:32]
        self.lock = QLockFile(str(self.directory / "instance.lock"))
        # This is lifetime ownership, not a document save timeout. Qt still
        # detects a dead owner; never break a live lock because it is old.
        self.lock.setStaleLockTime(0)
        self.owned = False
        self.can_activate: Callable[[], bool] = lambda: True
        self.server = QLocalServer(self)
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self.server.setMaxPendingConnections(4)
        self.server.newConnection.connect(self.accept_connections)
        self.buffers: dict[QLocalSocket, bytearray] = {}

    def acquire(self) -> bool:
        if self.owned:
            return True
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
        except OSError:
            raise InstanceError() from None
        if not self.lock.tryLock(0):
            if self.lock.error() == QLockFile.LockError.LockFailedError:
                return False
            raise InstanceError()
        self.owned = True
        # Only the resource owner can remove an endpoint left by its crashed
        # predecessor. A competing launch never removes a live endpoint/lock.
        QLocalServer.removeServer(self.name)
        if not self.server.listen(self.name):
            self.close()
            raise InstanceError(
                "DeskTranslate cannot open its local activation channel. Close other DeskTranslate windows and try again."
            )
        return True

    def notify(self) -> bool:
        """Startup-only bounded IPC. Never called by automated verification modes."""
        socket = QLocalSocket()
        socket.setReadBufferSize(16)
        try:
            socket.connectToServer(self.name)
            if not socket.waitForConnected(400):
                return False
            if socket.write(ACTIVATE) != len(ACTIVATE):
                return False
            if socket.bytesToWrite() and not socket.waitForBytesWritten(200):
                return False
            if not socket.bytesAvailable() and not socket.waitForReadyRead(1500):
                return False
            return socket.read(16).data() == b"ok\n"
        finally:
            socket.abort()

    def accept_connections(self) -> None:
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            if socket is None:
                continue
            if len(self.buffers) >= 4:
                socket.abort()
                socket.deleteLater()
                continue
            socket.setReadBufferSize(16)
            self.buffers[socket] = bytearray()
            socket.readyRead.connect(partial(self.receive, socket))
            socket.disconnected.connect(partial(self.release, socket))
            timer = QTimer(socket)
            timer.setSingleShot(True)
            timer.timeout.connect(partial(self.release, socket))
            timer.start(2000)
            self.receive(socket)

    def receive(self, socket: QLocalSocket) -> None:
        buffer = self.buffers.get(socket)
        if buffer is None:
            return
        buffer.extend(socket.read(16).data())
        if len(buffer) >= len(ACTIVATE):
            if bytes(buffer) == ACTIVATE:
                if self.can_activate():
                    self.activated.emit()
                    socket.write(b"ok\n")
                else:
                    socket.write(b"busy\n")
                socket.disconnectFromServer()
            else:
                self.release(socket)

    def release(self, socket: QLocalSocket) -> None:
        if self.buffers.pop(socket, None) is not None:
            socket.abort()
            socket.deleteLater()

    def close(self) -> None:
        self.server.close()
        for socket in list(self.buffers):
            self.release(socket)
        if self.owned:
            self.lock.unlock()
            self.owned = False
