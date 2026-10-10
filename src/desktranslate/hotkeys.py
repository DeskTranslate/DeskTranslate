from __future__ import annotations

import ctypes
import os
from collections.abc import Callable
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, QByteArray

from desktranslate.shortcuts import parse_hotkey, validate_hotkeys


class Hotkeys(QAbstractNativeEventFilter):
    def __init__(
        self, actions: dict[str, Callable[[], None]], suspend: Callable[[], None] | None = None
    ) -> None:
        super().__init__()
        self.actions = actions
        self.registered: dict[int, str] = {}
        self.suspend = suspend

    def register(self, values: dict[str, str]) -> list[str]:
        validate_hotkeys(values)
        self.close()
        conflicts = []
        if os.name != "nt":
            return ["Global shortcuts require Windows. Use the app controls on this platform."]
        for index, (name, value) in enumerate(values.items(), start=1):
            if name not in self.actions:
                continue
            modifiers, key = parse_hotkey(value)
            if ctypes.windll.user32.RegisterHotKey(None, index, modifiers, key):
                self.registered[index] = name
            else:
                conflicts.append(value)
        return conflicts

    def nativeEventFilter(
        self, event_type: QByteArray | bytes | bytearray | memoryview, message: int
    ) -> tuple[bool, int]:
        msg = wintypes.MSG.from_address(int(message))
        if msg.message == 0x0218 and msg.wParam == 4 and self.suspend:
            self.suspend()
            return False, 0
        if msg.message == 0x0312 and msg.wParam in self.registered:
            self.actions[self.registered[msg.wParam]]()
            return True, 0
        return False, 0

    def register_first_run(self, values: dict[str, str]) -> tuple[dict[str, str], list[str]]:
        """Choose discoverable alternatives only before a user has completed setup."""
        updated = dict(values)
        conflicts = self.register(updated)
        for modifier in ("Shift", "Win"):
            if not conflicts:
                break
            for name, value in list(updated.items()):
                if value in conflicts and modifier.upper() not in value.upper().split("+"):
                    parts = value.split("+")
                    updated[name] = "+".join([*parts[:-1], modifier, parts[-1]])
            conflicts = self.register(updated)
        return updated, conflicts

    def close(self) -> None:
        if os.name == "nt":
            for index in self.registered:
                ctypes.windll.user32.UnregisterHotKey(None, index)
        self.registered.clear()
