# tests/test_async_executor.py

import asyncio

from openhands.sdk.utils.async_executor import AsyncExecutor


async def async_add(a, b):
    await asyncio.sleep(0.01)
    return a + b


def test_run_async_returns_value():
    """Basic test: coroutine function runs and returns result."""
    executor = AsyncExecutor()
    result = executor.run_async(async_add, 2, 3)
    assert result == 5
    executor.close()


def test_run_async_accepts_coroutine_object():
    """Ensure coroutine objects are accepted directly."""
    executor = AsyncExecutor()
    coro = async_add(5, 7)
    result = executor.run_async(coro)
    assert result == 12
    executor.close()


def test_close_stops_loop():
    """Closing should stop the loop and clear state."""
    executor = AsyncExecutor()
    executor.run_async(async_add, 1, 2)
    executor.close()

    # After close, loop and thread should be None
    assert executor._loop is None
    assert executor._thread is None


def test_scheduling_failure_fallback_runs_cleanup(monkeypatch):
    """
    If scheduling fails, executor should still run the coroutine fallback.
    This simulates the BrowserToolExecutor.cleanup() case.
    """
    executor = AsyncExecutor()
    called = {}

    async def fake_cleanup():
        called["done"] = True
        return "cleaned"

    # Force run_coroutine_threadsafe to raise
    import asyncio as real_asyncio

    monkeypatch.setattr(
        real_asyncio,
        "run_coroutine_threadsafe",
        lambda coro, loop: (_ for _ in ()).throw(RuntimeError("error")),
    )

    result = executor.run_async(fake_cleanup)
    assert result == "cleaned"
    assert called["done"] is True
    executor.close()


def test_no_runtime_warning_on_failure(monkeypatch, recwarn):
    """
    Ensure no 'coroutine was never awaited' RuntimeWarning is emitted
    when scheduling fails and fallback runs.
    """
    executor = AsyncExecutor()

    async def fake_cleanup():
        return "ok"

    import asyncio as real_asyncio

    monkeypatch.setattr(
        real_asyncio,
        "run_coroutine_threadsafe",
        lambda coro, loop: (_ for _ in ()).throw(RuntimeError("error")),
    )

    # Run the coroutine, simulating a scheduling failure
    result = executor.run_async(fake_cleanup)
    assert result == "ok"

    # Assert no warnings captured at all
    assert len(recwarn) == 0

    executor.close()
