"""Contain Windows OCR helpers and their descendants in an owned job object."""

from __future__ import annotations

import ctypes
from ctypes import wintypes


class BasicLimits(ctypes.Structure):
    _fields_ = [
        ("process_time", ctypes.c_int64),
        ("job_time", ctypes.c_int64),
        ("flags", wintypes.DWORD),
        ("minimum_working_set", ctypes.c_size_t),
        ("maximum_working_set", ctypes.c_size_t),
        ("active_processes", wintypes.DWORD),
        ("affinity", ctypes.c_size_t),
        ("priority", wintypes.DWORD),
        ("scheduling", wintypes.DWORD),
    ]


class IOCounters(ctypes.Structure):
    _fields_ = [
        (name, ctypes.c_uint64)
        for name in ("read", "write", "other", "read_bytes", "write_bytes", "other_bytes")
    ]


class ExtendedLimits(ctypes.Structure):
    _fields_ = [
        ("basic", BasicLimits),
        ("io", IOCounters),
        ("process_memory", ctypes.c_size_t),
        ("job_memory", ctypes.c_size_t),
        ("peak_process_memory", ctypes.c_size_t),
        ("peak_job_memory", ctypes.c_size_t),
    ]


def rebuild_child_pipe(handle: int) -> object:
    from multiprocessing.connection import PipeConnection

    return PipeConnection(handle)


class ChildPipe:
    """Transfer a Windows pipe directly into the spawned process's handle table.

    The default Connection reducer duplicates into the parent and asks the child
    to steal it later. Killing a child before unpickling leaves that duplicate
    behind. Spawn's process-owned duplication also closes it on an early exit.
    This is local to OCR IPC; the global multiprocessing reducer is unchanged.
    """

    def __init__(self, handle: int) -> None:
        self.handle = handle

    def __reduce__(self) -> tuple[object, tuple[int]]:
        from multiprocessing.context import get_spawning_popen

        spawn = get_spawning_popen()
        if spawn is None:
            raise ValueError("OCR pipe transfer requires a spawning child")
        return rebuild_child_pipe, (spawn.duplicate_for_child(self.handle),)


class ProcessJob:
    """The child must wait for assignment before starting external helpers."""

    def __init__(self, pid: int) -> None:
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        self.api.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self.api.CreateJobObjectW.restype = wintypes.HANDLE
        self.api.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        self.api.SetInformationJobObject.restype = wintypes.BOOL
        self.api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.api.OpenProcess.restype = wintypes.HANDLE
        self.api.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self.api.AssignProcessToJobObject.restype = wintypes.BOOL
        self.api.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self.api.TerminateJobObject.restype = wintypes.BOOL
        self.api.CloseHandle.argtypes = [wintypes.HANDLE]
        self.api.CloseHandle.restype = wintypes.BOOL
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise OSError("OCR process containment could not be created")
        process = None
        try:
            limits = ExtendedLimits()
            limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if not self.api.SetInformationJobObject(
                self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)
            ):
                raise OSError("OCR process containment could not be configured")
            process = self.api.OpenProcess(0x0101, False, pid)  # SET_QUOTA | TERMINATE
            if not process or not self.api.AssignProcessToJobObject(self.handle, process):
                raise OSError("OCR process containment could not be assigned")
        except Exception:
            self.close()
            raise
        finally:
            if process:
                self.api.CloseHandle(process)

    def terminate(self) -> None:
        if self.handle and not self.api.TerminateJobObject(self.handle, 1):
            raise OSError("OCR process tree could not be terminated")

    def close(self) -> None:
        if self.handle:
            handle, self.handle = self.handle, None
            if not self.api.CloseHandle(handle):
                raise OSError("OCR containment handle could not be closed")
