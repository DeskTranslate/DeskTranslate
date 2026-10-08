from __future__ import annotations

import ctypes
import hashlib
import json
import os

from PIL import Image

from desktranslate.errors import CaptureError, DisplayChangedError
from desktranslate.models import Rect


def enable_dpi_awareness() -> None:
    if os.name == "nt":
        # Call before QApplication, MSS, or any window creation.
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("DeskTranslate.2")


def physical_monitors() -> dict[str, Rect]:
    """Match Win32 device names to Qt screen names; never assume enumeration order."""
    if os.name != "nt":
        return {}
    from ctypes import wintypes

    class MonitorInfo(ctypes.Structure):
        _fields_ = [
            ("size", wintypes.DWORD),
            ("monitor", wintypes.RECT),
            ("work", wintypes.RECT),
            ("flags", wintypes.DWORD),
            ("device", wintypes.WCHAR * 32),
        ]

    result: dict[str, Rect] = {}
    callback_type = ctypes.WINFUNCTYPE(
        wintypes.BOOL,
        wintypes.HMONITOR,
        wintypes.HDC,
        ctypes.POINTER(wintypes.RECT),
        wintypes.LPARAM,
    )
    user32 = ctypes.windll.user32
    user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(MonitorInfo)]
    user32.GetMonitorInfoW.restype = wintypes.BOOL
    user32.EnumDisplayMonitors.argtypes = [
        wintypes.HDC,
        ctypes.c_void_p,
        callback_type,
        wintypes.LPARAM,
    ]

    def callback(handle: int, dc: int, rect: object, param: int) -> bool:
        info = MonitorInfo()
        info.size = ctypes.sizeof(info)
        if user32.GetMonitorInfoW(handle, ctypes.byref(info)):
            r = info.monitor
            result[info.device] = Rect(r.left, r.top, r.right - r.left, r.bottom - r.top)
        return True

    user32.EnumDisplayMonitors(None, None, callback_type(callback), 0)
    return result


def topology_signature() -> str:
    layout = {k: (v.x, v.y, v.width, v.height) for k, v in physical_monitors().items()}
    return hashlib.sha256(json.dumps(layout, sort_keys=True).encode()).hexdigest()


class MSSCapture:
    def __init__(self, signature: str = "") -> None:
        import mss

        self.backend = mss.mss()
        self.signature = signature

    def capture(self, region: Rect) -> Image.Image:
        if self.signature and topology_signature() != self.signature:
            raise DisplayChangedError()
        if os.name == "nt" and not any(
            bounds.contains(region) for bounds in physical_monitors().values()
        ):
            raise DisplayChangedError()
        try:
            screenshot = self.backend.grab(
                {"left": region.x, "top": region.y, "width": region.width, "height": region.height}
            )
            return Image.frombytes("RGB", screenshot.size, screenshot.rgb)
        except Exception:
            raise CaptureError() from None

    def close(self) -> None:
        self.backend.close()
