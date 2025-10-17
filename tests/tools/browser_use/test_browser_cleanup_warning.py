"""Test to reproduce the RuntimeWarning issue with BrowserToolExecutor cleanup."""

import warnings
from unittest.mock import AsyncMock, patch

from openhands.tools.browser_use import BrowserToolExecutor


def test_browser_tool_executor_cleanup_warning():
    """Test that reproduces the RuntimeWarning about unawaited coroutine cleanup."""
    # Capture warnings
    with warnings.catch_warnings(record=True) as warning_list:
        warnings.simplefilter("always")

        # Create a BrowserToolExecutor
        executor = BrowserToolExecutor()

        # Mock the server methods to be async and simulate some initialization
        executor._server._init_browser_session = AsyncMock()
        executor._server._close_browser = AsyncMock()
        executor._server._close_all_sessions = AsyncMock()

        # Initialize the executor to set _initialized = True
        # This ensures cleanup() will actually try to do something
        executor._initialized = True

        # Mock the async executor to raise an exception during cleanup
        # This simulates the scenario where cleanup fails and the coroutine
        # warning occurs
        original_run_async = executor._async_executor.run_async

        def mock_run_async(awaitable_or_fn, *args, **kwargs):
            if awaitable_or_fn == executor.cleanup:
                # Simulate an exception during cleanup that leaves the coroutine
                # unawaited
                raise RuntimeError("Simulated cleanup failure")
            return original_run_async(awaitable_or_fn, *args, **kwargs)

        executor._async_executor.run_async = mock_run_async

        # Simulate client exit by calling close()
        # This should trigger the RuntimeWarning about unawaited coroutine
        executor.close()

    # Check if we got the expected RuntimeWarning
    runtime_warnings = [
        w for w in warning_list if issubclass(w.category, RuntimeWarning)
    ]

    # We expect to see a RuntimeWarning about the unawaited coroutine
    # Note: The warning might not always appear due to timing of garbage collection
    # But we should at least see the logged warning from the exception handler
    print(f"All warnings: {[str(w.message) for w in warning_list]}")
    print(f"Runtime warnings: {[str(w.message) for w in runtime_warnings]}")

    # The test documents the issue - we may or may not get the exact RuntimeWarning
    # depending on when garbage collection happens, but the issue exists


def test_browser_tool_executor_del_cleanup_warning():
    """Test that reproduces the RuntimeWarning when executor is garbage collected."""
    # Capture warnings
    with warnings.catch_warnings(record=True) as warning_list:
        warnings.simplefilter("always")

        # Mock the server to avoid actual browser initialization
        with patch(
            "openhands.tools.browser_use.impl.CustomBrowserUseServer"
        ) as mock_server_class:
            mock_server = mock_server_class.return_value
            mock_server._init_browser_session = lambda **kwargs: None
            mock_server._close_browser = lambda: None
            mock_server._close_all_sessions = lambda: None

            # Create a BrowserToolExecutor and let it go out of scope
            # This should trigger the __del__ method which calls close()
            executor = BrowserToolExecutor()
            del executor

    # Check if we got the expected RuntimeWarning
    runtime_warnings = [
        w for w in warning_list if issubclass(w.category, RuntimeWarning)
    ]

    # We might get a RuntimeWarning about the unawaited coroutine during garbage
    # collection
    # This test documents the current behavior - the warning may or may not appear
    # depending on when garbage collection happens
    print(
        f"Warnings during garbage collection: "
        f"{[str(w.message) for w in runtime_warnings]}"
    )


def test_demonstrate_coroutine_cleanup_issue():
    """Test that demonstrates the core issue with the cleanup coroutine."""
    import gc

    # This test demonstrates the actual problem:
    # When cleanup() is called but not properly awaited, we get a RuntimeWarning

    executor = BrowserToolExecutor()

    # Mock the server methods
    executor._server._init_browser_session = AsyncMock()
    executor._server._close_browser = AsyncMock()
    executor._server._close_all_sessions = AsyncMock()
    executor._initialized = True

    # Create the coroutine but don't await it - this simulates the issue
    cleanup_coro = executor.cleanup()

    # When the coroutine is garbage collected without being awaited,
    # Python will issue a RuntimeWarning
    del cleanup_coro
    gc.collect()  # Force garbage collection

    # The warning will appear in the console, not as a catchable warning
    # This demonstrates why the original issue occurs


def test_browser_tool_executor_close_no_warning():
    """Test that the fixed close() method doesn't produce unawaited coroutine warnings."""  # noqa: E501
    import warnings

    # Capture warnings
    with warnings.catch_warnings(record=True) as warning_list:
        warnings.simplefilter("always")

        # Create a BrowserToolExecutor
        executor = BrowserToolExecutor()

        # Mock the server methods to avoid actual browser operations
        executor._server._init_browser_session = AsyncMock()
        executor._server._close_browser = AsyncMock()
        executor._server._close_all_sessions = AsyncMock()

        # Initialize the executor
        executor._initialized = True

        # Call close() - this should not produce unawaited coroutine warnings
        executor.close()

    # Check that we don't get RuntimeWarnings about unawaited coroutines
    runtime_warnings = [
        w for w in warning_list if issubclass(w.category, RuntimeWarning)
    ]
    coroutine_warnings = [
        w
        for w in runtime_warnings
        if "coroutine" in str(w.message) and "cleanup" in str(w.message)
    ]

    # We should not get any warnings about unawaited cleanup coroutines
    assert len(coroutine_warnings) == 0, (
        f"Unexpected coroutine warnings: {[str(w.message) for w in coroutine_warnings]}"
    )

    print(f"All warnings: {[str(w.message) for w in warning_list]}")
    print("✓ No unawaited coroutine warnings detected")
