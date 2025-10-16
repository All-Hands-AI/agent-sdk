"""Tests for async utilities in OpenHands SDK."""

import asyncio
import threading
import time

from openhands.sdk.event import Event
from openhands.sdk.event.types import SourceType
from openhands.sdk.utils.async_utils import (
    AsyncCallbackWrapper,
    AsyncConversationCallback,
)


class AsyncUtilsMockEvent(Event):
    """Mock event for testing."""

    data: str = "test"
    source: SourceType = "agent"


def test_async_conversation_callback_type():
    """Test that AsyncConversationCallback type is properly defined."""

    async def sample_callback(event: Event) -> None:
        pass

    # This should not raise any type errors
    callback: AsyncConversationCallback = sample_callback
    assert callable(callback)


def test_async_callback_wrapper_basic():
    """Test basic functionality of AsyncCallbackWrapper."""
    events_processed = []

    async def async_callback(event: Event) -> None:
        events_processed.append(f"processed: {event.source}")

    async def run_test():
        # Create event loop for the async callback
        loop = asyncio.get_running_loop()

        # Create wrapper with the loop
        wrapper = AsyncCallbackWrapper(async_callback, loop)

        # Create and process event
        event = AsyncUtilsMockEvent()
        wrapper(event)

        # Wait a bit for the callback to execute
        await asyncio.sleep(0.1)

    asyncio.run(run_test())

    assert len(events_processed) == 1
    assert events_processed[0] == "processed: agent"


def test_async_callback_wrapper_multiple_events():
    """Test AsyncCallbackWrapper with multiple events."""
    events_processed = []

    async def async_callback(event: Event) -> None:
        events_processed.append(event.id)

    async def run_test():
        loop = asyncio.get_running_loop()
        wrapper = AsyncCallbackWrapper(async_callback, loop)

        events = [AsyncUtilsMockEvent() for _ in range(3)]

        for event in events:
            wrapper(event)

        # Wait for all callbacks to complete
        await asyncio.sleep(0.1)

        return events

    events = asyncio.run(run_test())

    assert len(events_processed) == 3
    assert all(event.id in events_processed for event in events)


def test_async_callback_wrapper_with_stopped_loop():
    """Test AsyncCallbackWrapper behavior when loop is not running."""
    events_processed = []

    async def async_callback(event: Event) -> None:
        events_processed.append("processed")

    # Create a loop but don't run it
    loop = asyncio.new_event_loop()
    wrapper = AsyncCallbackWrapper(async_callback, loop)

    event = AsyncUtilsMockEvent()

    # This should not execute the callback since loop is not running
    wrapper(event)

    # Wait a bit
    time.sleep(0.1)

    # No events should be processed since loop wasn't running
    assert len(events_processed) == 0

    loop.close()


def test_async_callback_wrapper_exception_handling():
    """Test that exceptions in async callbacks don't crash the wrapper."""

    async def failing_callback(event: Event) -> None:
        raise ValueError("Test exception")

    async def run_test():
        loop = asyncio.get_running_loop()
        wrapper = AsyncCallbackWrapper(failing_callback, loop)

        event = AsyncUtilsMockEvent()

        # This should not raise an exception in the calling thread
        wrapper(event)

        # Wait for the callback to execute (and fail)
        await asyncio.sleep(0.1)

    # Should not raise an exception
    asyncio.run(run_test())


def test_async_callback_wrapper_concurrent_execution():
    """Test that AsyncCallbackWrapper can handle concurrent events."""
    events_processed = []

    async def async_callback(event: Event) -> None:
        await asyncio.sleep(0.05)  # Simulate async work
        events_processed.append(
            {
                "id": event.id,
                "source": event.source,
            }
        )

    async def run_test():
        loop = asyncio.get_running_loop()
        wrapper = AsyncCallbackWrapper(async_callback, loop)

        events = [AsyncUtilsMockEvent() for _ in range(5)]

        # Submit all events quickly
        for event in events:
            wrapper(event)

        # Wait for all callbacks to complete
        await asyncio.sleep(0.3)

        return events

    events = asyncio.run(run_test())

    assert len(events_processed) == 5

    # Check that all events were processed
    processed_ids = {entry["id"] for entry in events_processed}
    expected_ids = {event.id for event in events}
    assert processed_ids == expected_ids

    # All should have the same source
    sources = {entry["source"] for entry in events_processed}
    assert sources == {"agent"}


def test_async_callback_wrapper_from_different_thread():
    """Test AsyncCallbackWrapper when called from a different thread."""
    events_processed = []
    exception_caught = None

    async def async_callback(event: Event) -> None:
        events_processed.append(f"processed: {event.source}")

    def thread_function(wrapper):
        """Function to run in a separate thread."""
        try:
            event = AsyncUtilsMockEvent()
            wrapper(event)
        except Exception as e:
            nonlocal exception_caught
            exception_caught = e

    async def run_test():
        loop = asyncio.get_running_loop()
        wrapper = AsyncCallbackWrapper(async_callback, loop)

        # Start a thread that will call the wrapper
        thread = threading.Thread(target=thread_function, args=(wrapper,))
        thread.start()

        # Wait for the thread and the callback
        thread.join()
        await asyncio.sleep(0.1)

    asyncio.run(run_test())

    # Should not have raised an exception
    assert exception_caught is None
    assert len(events_processed) == 1
    assert events_processed[0] == "processed: agent"


def test_async_callback_wrapper_performance():
    """Test that the wrapper doesn't add significant overhead."""

    async def simple_callback(event: Event) -> None:
        pass  # Do nothing

    async def run_test():
        loop = asyncio.get_running_loop()
        wrapper = AsyncCallbackWrapper(simple_callback, loop)

        events = [AsyncUtilsMockEvent() for _ in range(100)]

        start_time = time.time()
        for event in events:
            wrapper(event)

        # Give time for processing
        await asyncio.sleep(0.1)

        end_time = time.time()
        total_time = end_time - start_time

        return total_time

    total_time = asyncio.run(run_test())

    # Should process 100 events reasonably quickly (less than 1 second)
    assert total_time < 1.0
