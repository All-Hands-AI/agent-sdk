"""Signal handling utilities for graceful shutdown and cleanup."""

import signal
import threading
from collections.abc import Callable
from typing import Any

from openhands.sdk.logger import get_logger


logger = get_logger(__name__)


class GracefulShutdownHandler:
    """Handles graceful shutdown on SIGINT/SIGTERM with proper cleanup.

    This class provides a context manager that sets up signal handlers
    to gracefully shutdown threads and cleanup resources when the process
    receives SIGINT (Ctrl+C) or SIGTERM.
    """

    def __init__(self):
        self._shutdown_requested = threading.Event()
        self._cleanup_callbacks: list[Callable[[], None]] = []
        self._original_sigint_handler = None
        self._original_sigterm_handler = None
        self._lock = threading.Lock()

    def register_cleanup_callback(self, callback: Callable[[], None]) -> None:
        """Register a callback to be called during shutdown.

        Args:
            callback: Function to call during cleanup. Should not raise exceptions.
        """
        with self._lock:
            self._cleanup_callbacks.append(callback)

    def is_shutdown_requested(self) -> bool:
        """Check if shutdown has been requested."""
        return self._shutdown_requested.is_set()

    def request_shutdown(self) -> None:
        """Request shutdown (can be called from any thread)."""
        if not self._shutdown_requested.is_set():
            logger.info("Shutdown requested")
            self._shutdown_requested.set()

    def _signal_handler(self, signum: int, frame: Any) -> None:
        """Handle SIGINT/SIGTERM signals."""
        signal_name = "SIGINT" if signum == signal.SIGINT else "SIGTERM"
        logger.info(f"Received {signal_name}, initiating graceful shutdown...")
        self.request_shutdown()

    def _cleanup(self) -> None:
        """Run all registered cleanup callbacks."""
        logger.debug("Running cleanup callbacks...")
        with self._lock:
            for callback in self._cleanup_callbacks:
                try:
                    callback()
                except Exception as e:
                    logger.warning(f"Error in cleanup callback: {e}", exc_info=True)

    def __enter__(self):
        """Set up signal handlers."""
        self._original_sigint_handler = signal.signal(
            signal.SIGINT, self._signal_handler
        )
        self._original_sigterm_handler = signal.signal(
            signal.SIGTERM, self._signal_handler
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Restore original signal handlers and run cleanup."""
        # Restore original handlers
        if self._original_sigint_handler is not None:
            signal.signal(signal.SIGINT, self._original_sigint_handler)
        if self._original_sigterm_handler is not None:
            signal.signal(signal.SIGTERM, self._original_sigterm_handler)

        # Run cleanup
        self._cleanup()

        # If we're exiting due to KeyboardInterrupt, suppress it
        # since we've handled it gracefully
        if exc_type is KeyboardInterrupt:
            logger.info("KeyboardInterrupt handled gracefully")
            return True

        return False


def wait_for_threads_with_shutdown(
    threads: list[threading.Thread],
    shutdown_handler: GracefulShutdownHandler,
    timeout: float = 5.0,
) -> None:
    """Wait for threads to complete or shutdown to be requested.

    Args:
        threads: List of threads to wait for
        shutdown_handler: Shutdown handler to check for shutdown requests
        timeout: Maximum time to wait for each thread to join after shutdown
    """
    try:
        # Wait for threads to complete or shutdown to be requested
        for thread in threads:
            while thread.is_alive() and not shutdown_handler.is_shutdown_requested():
                thread.join(timeout=0.1)

        # If shutdown was requested, wait a bit more for threads to finish
        if shutdown_handler.is_shutdown_requested():
            logger.info("Waiting for threads to finish...")
            for thread in threads:
                if thread.is_alive():
                    thread.join(timeout=timeout)
                    if thread.is_alive():
                        logger.warning(
                            f"Thread {thread.name} did not finish within {timeout}s"
                        )

    except KeyboardInterrupt:
        # This shouldn't happen if the signal handler is working correctly,
        # but just in case...
        logger.info("KeyboardInterrupt during thread cleanup")
        shutdown_handler.request_shutdown()
