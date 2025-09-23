"""
FIFO Lock implementation that guarantees first-in-first-out access ordering.

This provides fair lock access where threads acquire the lock in the exact order
they requested it, preventing starvation that can occur with standard RLock.
"""

import threading
from collections import deque
from threading import get_ident
from typing import Any


class FIFOLock:
    """
    A reentrant lock that guarantees FIFO (first-in-first-out) access ordering.

    Unlike Python's standard RLock, this lock ensures that threads acquire
    the lock in the exact order they requested it, providing fairness and
    preventing lock starvation.

    Features:
    - Reentrant: Same thread can acquire multiple times
    - FIFO ordering: Threads get lock in request order
    - Context manager support: Use with 'with' statement
    - Thread-safe: Safe for concurrent access
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()  # Protects internal state
        self._owner_tid: int | None = None  # Current lock owner thread ID
        self._count = 0  # Reentrancy count for current owner
        self._waiters: deque[threading.Event] = deque()  # FIFO queue of waiting threads
        self._waiter_events: dict[int, threading.Event] = {}  # Map thread ID to event

    def acquire(self, blocking: bool = True, timeout: float = -1) -> bool:
        """
        Acquire the lock.

        Args:
            blocking: If True, block until lock is acquired. If False, return
                     immediately.
            timeout: Maximum time to wait for lock (ignored if blocking=False).
                    -1 means wait indefinitely.

        Returns:
            True if lock was acquired, False otherwise.
        """
        current_tid = get_ident()

        with self._lock:
            # If we already own the lock, just increment count (reentrancy)
            if self._owner_tid == current_tid:
                self._count += 1
                return True

            # If lock is free, acquire it immediately
            if self._owner_tid is None:
                self._owner_tid = current_tid
                self._count = 1
                return True

            # Lock is owned by another thread
            if not blocking:
                return False

            # Create event for this thread and add to FIFO queue
            event = threading.Event()
            self._waiters.append(event)
            self._waiter_events[current_tid] = event

        # Wait for our turn (outside the internal lock)
        try:
            if timeout == -1:
                event.wait()
                acquired = True
            else:
                acquired = event.wait(timeout)

            if acquired:
                # We were signaled, so we now own the lock
                with self._lock:
                    # Clean up our event
                    if current_tid in self._waiter_events:
                        del self._waiter_events[current_tid]

                    # Double-check we're the owner (should always be true)
                    assert self._owner_tid == current_tid
                    assert self._count == 1

                return True
            else:
                # Timeout occurred, clean up
                with self._lock:
                    if current_tid in self._waiter_events:
                        del self._waiter_events[current_tid]
                    # Remove from waiters queue if still there
                    try:
                        self._waiters.remove(event)
                    except ValueError:
                        pass  # Already removed

                return False

        except Exception:
            # Clean up on any exception
            with self._lock:
                if current_tid in self._waiter_events:
                    del self._waiter_events[current_tid]
                try:
                    self._waiters.remove(event)
                except ValueError:
                    pass
            raise

    def release(self) -> None:
        """
        Release the lock.

        Raises:
            RuntimeError: If the current thread doesn't own the lock.
        """
        current_tid = get_ident()

        with self._lock:
            if self._owner_tid != current_tid:
                raise RuntimeError("Cannot release lock not owned by current thread")

            self._count -= 1

            # If still reentrant, just return
            if self._count > 0:
                return

            # Release the lock and wake up next waiter
            self._owner_tid = None
            self._count = 0

            # Wake up the next thread in FIFO order
            if self._waiters:
                next_event = self._waiters.popleft()
                # Find the thread ID for this event and set it as owner
                for tid, event in self._waiter_events.items():
                    if event is next_event:
                        self._owner_tid = tid
                        self._count = 1
                        next_event.set()
                        break

    def __enter__(self) -> "FIFOLock":
        """Context manager entry."""
        self.acquire()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.release()

    def locked(self) -> bool:
        """
        Return True if the lock is currently held by any thread.
        """
        with self._lock:
            return self._owner_tid is not None

    def owned(self) -> bool:
        """
        Return True if the lock is currently held by the calling thread.
        """
        with self._lock:
            return self._owner_tid == get_ident()
