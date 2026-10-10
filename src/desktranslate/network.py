"""Worker-owned async deadlines for explicit downloads and metadata checks."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable, Coroutine
from threading import Event
from typing import Any, NoReturn, cast

import httpx

from desktranslate.errors import Cancelled


def run_cancellable[T](
    operation: Callable[[], Coroutine[Any, Any, T]], cancel: Event, timeout: float
) -> T:
    async def watch_cancel() -> None:
        while not cancel.is_set():
            await asyncio.sleep(0.05)

    async def bounded() -> T:
        if cancel.is_set():
            raise Cancelled()
        task = asyncio.create_task(operation())
        watcher = asyncio.create_task(watch_cancel())
        try:
            done, _ = await asyncio.wait(
                (task, watcher), timeout=timeout, return_when=asyncio.FIRST_COMPLETED
            )
            if cancel.is_set():
                raise Cancelled()
            if task in done:
                return await task
            raise TimeoutError()
        finally:
            task.cancel()
            watcher.cancel()
            await asyncio.gather(task, watcher, return_exceptions=True)

    loop = cast(asyncio.BaseEventLoop, asyncio.new_event_loop())
    try:
        return loop.run_until_complete(bounded())
    finally:
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.run_until_complete(loop.shutdown_default_executor(timeout=2))
        finally:
            loop.close()


async def identity_chunks(response: httpx.Response) -> AsyncIterator[bytes]:
    if response.headers.get("Content-Encoding", "identity").lower() != "identity":
        raise ValueError("Unexpected compressed download")
    if response.is_stream_consumed:
        for offset in range(0, len(response.content), 65536):
            yield response.content[offset : offset + 65536]
    else:
        async for chunk in response.aiter_raw(chunk_size=65536):
            yield chunk


def invalid_constant(value: str) -> NoReturn:
    raise ValueError("Non-finite JSON constant")


def strict_json(content: bytes | bytearray) -> Any:
    text = bytes(content).decode("utf-8")
    depth, quoted, escaped = 0, False, False
    for character in text:
        if quoted:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quoted = False
        elif character == '"':
            quoted = True
        elif character in "[{":
            depth += 1
            if depth > 64:
                raise ValueError("JSON nesting limit")
        elif character in "]}":
            depth -= 1
    return json.loads(text, parse_constant=invalid_constant)
