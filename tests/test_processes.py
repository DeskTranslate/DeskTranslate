import ctypes
import os
import subprocess
import sys
import time
from ctypes import wintypes

import pytest

from desktranslate.processes import ProcessJob

pytestmark = pytest.mark.native_process


@pytest.mark.skipif(os.name != "nt", reason="Native Windows job object regression")
def test_closing_ocr_job_terminates_external_engine_descendants(tmp_path):
    pid_path = tmp_path / "authored-child.pid"
    helper = (
        "import pathlib, subprocess, sys, time; sys.stdin.buffer.read(1); "
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'], "
        "creationflags=subprocess.CREATE_NO_WINDOW); "
        "pathlib.Path(sys.argv[1]).write_text(str(child.pid)); time.sleep(30)"
    )
    parent = subprocess.Popen(
        [sys.executable, "-c", helper, str(pid_path)],
        stdin=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    job = ProcessJob(parent.pid)
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    api.OpenProcess.restype = wintypes.HANDLE
    api.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    api.WaitForSingleObject.restype = wintypes.DWORD
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    child_handle = None
    try:
        parent.stdin.write(b"!")
        parent.stdin.flush()
        deadline = time.monotonic() + 5
        while not pid_path.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert pid_path.exists(), "Owned child failed to launch"
        child_handle = api.OpenProcess(0x00100000, False, int(pid_path.read_text()))
        assert child_handle
        assert api.WaitForSingleObject(child_handle, 0) == 258  # STILL RUNNING
        parent.terminate()  # Killing just the Python OCR host leaves its engine alive.
        parent.wait(5)
        assert api.WaitForSingleObject(child_handle, 0) == 258
        job.close()
        assert api.WaitForSingleObject(child_handle, 5000) == 0
        job.close()  # Idempotent teardown.
    finally:
        job.close()
        if parent.poll() is None:
            parent.kill()
        parent.wait(5)
        parent.stdin.close()
        if child_handle:
            api.CloseHandle(child_handle)


@pytest.mark.skipif(os.name != "nt", reason="Native Windows early-spawn handle regression")
def test_cancelling_ocr_before_initialization_does_not_leak_pipe_handles(tmp_path):
    from desktranslate.metrics import process_resources
    from desktranslate.ocr import IsolatedOCR

    def cancel_spawn():
        worker = IsolatedOCR("rapidocr", "ja", tmp_path)
        worker.cancel_pending()
        worker.close()
        worker.reap()
        assert worker.reaped

    cancel_spawn()  # Warm up the multiprocessing runtime before measuring.
    before = process_resources()["handles"]
    for _ in range(20):
        cancel_spawn()
    after = process_resources()["handles"]
    assert isinstance(before, int) and isinstance(after, int)
    assert after - before <= 4, "Early worker cancellation leaked native handles"
