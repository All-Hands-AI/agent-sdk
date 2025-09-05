"""Minimal sync helpers on top of fastmcp.Client, preserving original behavior."""

import asyncio
import inspect
import threading
from typing import Any, Callable

from fastmcp import Client as AsyncMCPClient


class MCPClient(AsyncMCPClient):
    """
    Behaves exactly like fastmcp.Client (same constructor & async API),
    but owns a background event loop and offers:
      - call_async_from_sync(awaitable_or_fn, *args, timeout=None, **kwargs)
      - call_sync_from_async(fn, *args, **kwargs)  # await this from async code
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    # ---------- loop management ----------

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        with self._lock:
            if self._loop is not None:
                return self._loop

            loop = asyncio.new_event_loop()

            def _runner():
                asyncio.set_event_loop(loop)
                loop.run_forever()

            t = threading.Thread(target=_runner, daemon=True)
            t.start()
            while not loop.is_running():
                pass

            self._loop = loop
            self._thread = t
            return loop

    def _shutdown_loop(self) -> None:
        with self._lock:
            loop, t = self._loop, self._thread
            self._loop = None
            self._thread = None

        if loop and loop.is_running():
            try:
                loop.call_soon_threadsafe(loop.stop)
            except RuntimeError:
                pass
        if t and t.is_alive():
            t.join(timeout=1.0)

    # ---------- public helpers ----------

    def call_async_from_sync(
        self,
        awaitable_or_fn: Callable[..., Any] | Any,
        *args,
        timeout: float,
        **kwargs,
    ):
        """
        Run a coroutine or async function on this client's loop from sync code.

        Usage:
            mcp.call_async_from_sync(async_fn, arg1, kw=...)
            mcp.call_async_from_sync(coro)
        """
        if inspect.iscoroutine(awaitable_or_fn):
            coro = awaitable_or_fn
        elif inspect.iscoroutinefunction(awaitable_or_fn):
            coro = awaitable_or_fn(*args, **kwargs)
        else:
            raise TypeError(
                "call_async_from_sync expects a coroutine or async function"
            )

        loop = self._ensure_loop()
        fut = asyncio.run_coroutine_threadsafe(coro, loop)
        return fut.result(timeout)

    async def call_sync_from_async(self, fn: Callable[..., Any], *args, **kwargs):
        """
        Await running a blocking function in the default threadpool from async code.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: fn(*args, **kwargs))

    # ---------- optional cleanup ----------

    def sync_close(self):
        # Best-effort: try async close if parent provides it
        aclose = self.close
        if inspect.iscoroutinefunction(aclose):
            try:
                self.call_async_from_sync(aclose, timeout=10.0)
            except Exception:
                pass
        self._shutdown_loop()

    def __del__(self):
        try:
            self.sync_close()
        except Exception:
            pass
