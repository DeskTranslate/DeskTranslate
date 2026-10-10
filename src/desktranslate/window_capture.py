"""Win32 client-relative capture over the compatibility backend.

The visibility guard rejects occluded/minimized targets before reading screen pixels.
No fallback from a missing target to arbitrary desktop content is permitted.
"""

from __future__ import annotations

import ctypes
import hashlib
import math
import os
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import PureWindowsPath
from typing import Protocol

from PIL import Image

from desktranslate.capture import MSSCapture
from desktranslate.errors import TargetUnavailableError
from desktranslate.models import Rect


@dataclass(frozen=True)
class WindowInfo:
    handle: int
    pid: int
    executable: str
    executable_hash: str
    title: str
    client: Rect
    bounds: Rect
    minimized: bool = False

    def binding(self) -> dict[str, str]:
        return {
            "executable": self.executable,
            "executable_hash": self.executable_hash,
            "title": self.title,
        }


def normalized_region(client: Rect, region: Rect) -> list[float]:
    if not client.contains(region):
        raise ValueError("Select a region inside the chosen application's client area.")
    return [
        (region.x - client.x) / client.width,
        (region.y - client.y) / client.height,
        region.width / client.width,
        region.height / client.height,
    ]


def project_region(client: Rect, relative: list[float] | None) -> Rect:
    if relative is None:
        return client
    if len(relative) != 4 or any(
        type(v) not in {float, int} or not math.isfinite(v) for v in relative
    ):
        raise ValueError("Invalid window-relative region")
    x, y, width, height = relative
    if (
        x < 0
        or y < 0
        or width <= 0
        or height <= 0
        or x + width > 1.00000001
        or y + height > 1.00000001
    ):
        raise ValueError("Window-relative region is outside its client area")
    left, top = round(x * client.width), round(y * client.height)
    right, bottom = (
        min(client.width, round((x + width) * client.width)),
        min(client.height, round((y + height) * client.height)),
    )
    result = Rect(client.x + left, client.y + top, max(1, right - left), max(1, bottom - top))
    if not client.contains(result):
        raise ValueError("Window region became too small. Select it again.")
    return result


class WindowInspector(Protocol):
    def windows(self) -> list[WindowInfo]: ...
    def unobscured(self, target: WindowInfo, region: Rect) -> bool: ...


class Win32Windows:
    def __init__(self, include_own: bool = False) -> None:
        if os.name != "nt":
            raise TargetUnavailableError("Application capture requires Windows.")
        self.include_own = include_own
        self.user = ctypes.WinDLL("user32", use_last_error=True)
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.dwm = ctypes.WinDLL("dwmapi")
        self.callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        self.user.EnumWindows.argtypes = [self.callback_type, wintypes.LPARAM]
        self.user.EnumWindows.restype = wintypes.BOOL
        for name in ("GetClientRect", "GetWindowRect"):
            function = getattr(self.user, name)
            function.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
            function.restype = wintypes.BOOL
        self.user.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
        self.user.GetWindowThreadProcessId.argtypes = [
            wintypes.HWND,
            ctypes.POINTER(wintypes.DWORD),
        ]
        self.user.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        self.user.IsWindowVisible.argtypes = [wintypes.HWND]
        self.user.IsIconic.argtypes = [wintypes.HWND]
        self.kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.kernel.OpenProcess.restype = wintypes.HANDLE
        self.kernel.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD),
        ]
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.dwm.DwmGetWindowAttribute.argtypes = [
            wintypes.HWND,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]

    def visible(self, handle: int) -> bool:
        cloaked = wintypes.DWORD()
        self.dwm.DwmGetWindowAttribute(handle, 14, ctypes.byref(cloaked), ctypes.sizeof(cloaked))
        return bool(self.user.IsWindowVisible(handle)) and not cloaked.value

    def handles(self) -> list[int]:
        result: list[int] = []

        def collect(handle: int, data: int) -> bool:
            if self.visible(handle):
                result.append(int(handle))
            return True

        self.user.EnumWindows(self.callback_type(collect), 0)
        return result

    def info(self, handle: int) -> WindowInfo | None:
        pid = wintypes.DWORD()
        self.user.GetWindowThreadProcessId(handle, ctypes.byref(pid))
        if not pid.value or (pid.value == os.getpid() and not self.include_own):
            return None
        title = ctypes.create_unicode_buffer(513)
        self.user.GetWindowTextW(handle, title, len(title))
        if not title.value:
            return None
        process = self.kernel.OpenProcess(0x1000, False, pid.value)
        if not process:
            return None
        try:
            path = ctypes.create_unicode_buffer(32768)
            length = wintypes.DWORD(len(path))
            if not self.kernel.QueryFullProcessImageNameW(process, 0, path, ctypes.byref(length)):
                return None
            executable = PureWindowsPath(path.value).name
            digest = hashlib.sha256(path.value.casefold().encode("utf-8")).hexdigest()
        finally:
            self.kernel.CloseHandle(process)
        client, bounds = wintypes.RECT(), wintypes.RECT()
        origin = wintypes.POINT()
        if (
            not self.user.GetClientRect(handle, ctypes.byref(client))
            or not self.user.GetWindowRect(handle, ctypes.byref(bounds))
            or not self.user.ClientToScreen(handle, ctypes.byref(origin))
        ):
            return None
        try:
            return WindowInfo(
                handle,
                pid.value,
                executable,
                digest,
                title.value,
                Rect(origin.x, origin.y, client.right, client.bottom),
                Rect(
                    bounds.left, bounds.top, bounds.right - bounds.left, bounds.bottom - bounds.top
                ),
                bool(self.user.IsIconic(handle)),
            )
        except ValueError:
            return None

    def windows(self) -> list[WindowInfo]:
        return [info for handle in self.handles() if (info := self.info(handle)) is not None]

    def unobscured(self, target: WindowInfo, region: Rect) -> bool:
        if target.minimized:
            return False
        # EnumWindows returns top-to-bottom Z order. Every visible window above
        # the target is checked, including our own overlay; no text is captured
        # from a different application obscuring the requested crop.
        for handle in self.handles():
            if handle == target.handle:
                return True
            if self.user.IsIconic(handle):
                continue
            bounds = wintypes.RECT()
            if self.user.GetWindowRect(handle, ctypes.byref(bounds)):
                try:
                    rectangle = Rect(
                        bounds.left,
                        bounds.top,
                        bounds.right - bounds.left,
                        bounds.bottom - bounds.top,
                    )
                except ValueError:
                    continue
                if rectangle.intersects(region):
                    return False
        return False


class WindowCapture:
    def __init__(
        self,
        binding: dict[str, str],
        relative: list[float] | None,
        follow_restart: bool = False,
        inspector: WindowInspector | None = None,
        backend: MSSCapture | None = None,
    ) -> None:
        self.binding = dict(binding)
        self.relative = relative
        self.follow_restart = follow_restart
        self.inspector = inspector or Win32Windows()
        self.backend = backend or MSSCapture()
        self.identity: tuple[int, int] | None = None
        self.region: Rect | None = None
        self.rebound = False

    def resolve(self) -> WindowInfo:
        windows = [
            w
            for w in self.inspector.windows()
            if w.executable_hash == self.binding.get("executable_hash")
            and w.executable.casefold() == self.binding.get("executable", "").casefold()
        ]
        if self.identity is not None:
            exact = next((w for w in windows if (w.handle, w.pid) == self.identity), None)
            if exact:
                return exact
            if not self.follow_restart:
                raise TargetUnavailableError(
                    "The chosen application closed. Select its new window to continue."
                )
        matches = [w for w in windows if w.title == self.binding.get("title")]
        if len(matches) != 1:
            raise TargetUnavailableError(
                "The chosen window is missing or ambiguous. Restore it, or select it again."
            )
        identity = (matches[0].handle, matches[0].pid)
        self.rebound = self.identity is not None and self.identity != identity
        self.identity = identity
        return matches[0]

    def capture(self, region: Rect) -> Image.Image:
        target = self.resolve()
        actual = project_region(target.client, self.relative)
        self.region = actual
        if not self.inspector.unobscured(target, actual):
            raise TargetUnavailableError(
                "Waiting for the chosen window. Restore it and keep the capture area unobstructed."
            )
        # Check identity and geometry on both sides of the screen read. A moving
        # window cannot deliver pixels using yesterday's client rectangle.
        image = self.backend.capture(actual)
        after = self.resolve()
        if (
            after.handle != target.handle
            or after.pid != target.pid
            or after.client != target.client
            or not self.inspector.unobscured(after, actual)
        ):
            raise TargetUnavailableError(
                "The window moved during capture. Retrying its current position."
            )
        return image

    def close(self) -> None:
        self.backend.close()
