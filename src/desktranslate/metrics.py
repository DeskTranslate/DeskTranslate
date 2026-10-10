"""Bounded numeric instrumentation, without content, paths or network identifiers."""

from __future__ import annotations

import ctypes
import math
import os
from collections import deque
from ctypes import wintypes
from threading import Lock
from typing import Any


class LatencyMetrics:
    def __init__(self, capacity: int = 512) -> None:
        self.capacity = capacity
        self.samples: dict[str, deque[float]] = {}
        self.lock = Lock()

    def observe(self, timings: dict[str, float]) -> None:
        with self.lock:
            for name, value in timings.items():
                if (
                    name.endswith("_ms")
                    and name.replace("_", "").isalnum()
                    and len(name) < 40
                    and isinstance(value, (int, float))
                    and math.isfinite(value)
                    and 0 <= value <= 600_000
                ):
                    if name not in self.samples and len(self.samples) >= 16:
                        continue
                    self.samples.setdefault(name, deque(maxlen=self.capacity)).append(float(value))

    def snapshot(self) -> dict[str, dict[str, float | int]]:
        with self.lock:
            result: dict[str, dict[str, float | int]] = {}
            for name, samples in self.samples.items():
                ordered = sorted(samples)
                if ordered:
                    result[name] = {
                        "count": len(ordered),
                        **{
                            label: round(
                                ordered[
                                    min(
                                        len(ordered) - 1,
                                        max(0, math.ceil(len(ordered) * quantile) - 1),
                                    )
                                ],
                                3,
                            )
                            for label, quantile in (("p50", 0.50), ("p95", 0.95), ("p99", 0.99))
                        },
                    }
            return result


def process_resources(pid: int | None = None) -> dict[str, int | float]:
    if os.name != "nt":
        return {}
    pid = pid or os.getpid()
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi")
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.GetProcessHandleCount.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]

    class MemoryCounters(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
            (name, ctypes.c_size_t)
            for name in (
                "peak_working",
                "working",
                "peak_paged",
                "paged",
                "peak_nonpaged",
                "nonpaged",
                "page",
                "peak_page",
                "private",
            )
        ]

    class FileTime(ctypes.Structure):
        _fields_ = [("low", wintypes.DWORD), ("high", wintypes.DWORD)]

    psapi.GetProcessMemoryInfo.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(MemoryCounters),
        wintypes.DWORD,
    ]
    kernel.GetProcessTimes.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(FileTime),
        ctypes.POINTER(FileTime),
        ctypes.POINTER(FileTime),
        ctypes.POINTER(FileTime),
    ]
    process = kernel.OpenProcess(0x1000 | 0x10, False, pid)
    if not process:
        return {}
    try:
        counters = MemoryCounters()
        counters.size = ctypes.sizeof(counters)
        handles = wintypes.DWORD()
        result: dict[str, int | float] = {}
        if psapi.GetProcessMemoryInfo(process, ctypes.byref(counters), counters.size):
            result.update(
                rss_bytes=counters.working,
                private_bytes=counters.private,
                peak_rss_bytes=counters.peak_working,
            )
        if kernel.GetProcessHandleCount(process, ctypes.byref(handles)):
            result["handles"] = handles.value
        created, ended, system, user = FileTime(), FileTime(), FileTime(), FileTime()
        if kernel.GetProcessTimes(
            process,
            ctypes.byref(created),
            ctypes.byref(ended),
            ctypes.byref(system),
            ctypes.byref(user),
        ):
            result["cpu_seconds"] = (
                (system.high << 32) + system.low + (user.high << 32) + user.low
            ) / 10_000_000
        result["native_threads"] = thread_count(pid)
        result["tcp_connections"] = socket_count(pid)
        return result
    finally:
        kernel.CloseHandle(process)


def thread_count(pid: int) -> int:
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)

    class ThreadEntry(ctypes.Structure):
        _fields_ = [
            ("size", wintypes.DWORD),
            ("usage", wintypes.DWORD),
            ("id", wintypes.DWORD),
            ("owner", wintypes.DWORD),
            ("base", wintypes.LONG),
            ("delta", wintypes.LONG),
            ("flags", wintypes.DWORD),
        ]

    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Thread32First.argtypes = [wintypes.HANDLE, ctypes.POINTER(ThreadEntry)]
    kernel.Thread32Next.argtypes = [wintypes.HANDLE, ctypes.POINTER(ThreadEntry)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    snapshot = kernel.CreateToolhelp32Snapshot(4, 0)
    if snapshot == ctypes.c_void_p(-1).value:
        return 0
    try:
        entry, count = ThreadEntry(), 0
        entry.size = ctypes.sizeof(entry)
        success = kernel.Thread32First(snapshot, ctypes.byref(entry))
        while success:
            count += entry.owner == pid
            success = kernel.Thread32Next(snapshot, ctypes.byref(entry))
        return count
    finally:
        kernel.CloseHandle(snapshot)


def socket_count(pid: int) -> int:
    library = ctypes.WinDLL("iphlpapi")
    library.GetExtendedTcpTable.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(wintypes.DWORD),
        wintypes.BOOL,
        wintypes.ULONG,
        ctypes.c_int,
        wintypes.ULONG,
    ]
    size = wintypes.DWORD()
    library.GetExtendedTcpTable(None, ctypes.byref(size), False, 2, 5, 0)
    if not 4 <= size.value <= 4_000_000:
        return 0
    buffer = ctypes.create_string_buffer(size.value)
    if library.GetExtendedTcpTable(buffer, ctypes.byref(size), False, 2, 5, 0):
        return 0
    count = wintypes.DWORD.from_buffer(buffer).value
    rows: Any = (wintypes.DWORD * (count * 6)).from_buffer(buffer, 4)
    return sum(rows[i * 6 + 5] == pid for i in range(count))
