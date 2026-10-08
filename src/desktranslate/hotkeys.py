from __future__ import annotations

import ctypes
import os
from collections.abc import Callable
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, QByteArray


def parse_hotkey(value: str) -> tuple[int, int]:
    parts = value.upper().split("+")
    modifiers = {"CTRL": 2, "ALT": 1, "SHIFT": 4, "WIN": 8}
    if len(parts) < 2 or len(set(parts)) != len(parts):
        raise ValueError("Use modifiers and a letter, digit or F1–F12, such as Ctrl+Alt+T.")
    mask = 0x4000  # MOD_NOREPEAT
    for part in parts[:-1]:
        if part not in modifiers:
            raise ValueError("Use Ctrl, Alt, Shift or Win as modifiers.")
        mask |= modifiers[part]
    key = parts[-1]
    if len(key) == 1 and key.isascii() and key.isalnum():
        return mask, ord(key)
    if key.startswith("F") and key[1:].isdigit() and 1 <= int(key[1:]) <= 12:
        return mask, 111 + int(key[1:])
    raise ValueError("Use a letter, digit or F1–F12.")


def validate_hotkeys(values: dict[str, str]) -> None:
    parsed = [parse_hotkey(value) for value in values.values()]
    if len(parsed) != len(set(parsed)):
        raise ValueError("Two actions use the same shortcut. Choose different keys.")


class Hotkeys(QAbstractNativeEventFilter):
    def __init__(self, actions: dict[str, Callable[[], None]]) -> None:
        super().__init__()
        self.actions = actions
        self.registered: dict[int, str] = {}

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
