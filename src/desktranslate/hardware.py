from __future__ import annotations

import ctypes
import os
import platform
import shutil
from pathlib import Path


def recommendation() -> str:
    """Cheap local inspection; no network, GPU probing process, or identifiers."""
    ram = 0
    if os.name == "nt":

        class MemoryStatus(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
                (name, ctypes.c_ulonglong)
                for name in (
                    "physical",
                    "available",
                    "page",
                    "page_available",
                    "virtual",
                    "virtual_available",
                    "extended",
                )
            ]

        status = MemoryStatus()
        status.length = ctypes.sizeof(status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            ram = round(status.physical / 1024**3)
    arch = platform.machine()
    available = round(shutil.disk_usage(Path.cwd()).free / 1024**3)
    return f"{arch} · {os.cpu_count() or 1} CPU threads · {ram or 'unknown'} GB RAM · {available} GB disk free. Recommended: lightweight CPU recognition + quick translation. Local AI depends on your server and model; GPU memory and speed are not inferred."
