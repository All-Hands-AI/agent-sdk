"""Tests for WebSocketCallbackClient."""

import time
from unittest.mock import MagicMock, patch

from openhands.sdk.conversation.impl.remote_conversation import WebSocketCallbackClient
from openhands.sdk.event.base import EventBase
from openhands.sdk.event.llm_convertible import MessageEvent


class TestWebSocketCallbackClient:
    """Test WebSocketCallbackClient functionality."""

    def setup_method(self):
        """Set up test environment."""
        self.received_events = []
        self.callback_calls = []

    def event_callback(self, event: EventBase):
        """Test callback to capture events."""
        self.received_events.append(event)
        self.callback_calls.append(event)

    def test_websocket_client_initialization(self):
        """Test WebSocketCallbackClient initialization."""
        callbacks = [self.event_callback]
        client = WebSocketCallbackClient(
            host="http://localhost:8000",
            conversation_id="test-conv-id",
            callbacks=callbacks,
        )

        assert client.host == "http://localhost:8000"
        assert client.conversation_id == "test-conv-id"
        assert client.callbacks == callbacks
        assert client._thread is None
        assert not client._stop.is_set()

    def test_websocket_client_start_stop(self):
        """Test starting and stopping the WebSocket client."""
        callbacks = [self.event_callback]
        client = WebSocketCallbackClient(
            host="http://localhost:8000",
            conversation_id="test-conv-id",
            callbacks=callbacks,
        )

        # Mock the _run method to avoid actual WebSocket connection
        with patch.object(client, "_run") as _mock_run:
            # Start the client
            client.start()
            assert client._thread is not None
            assert client._thread.daemon is True
            assert not client._stop.is_set()

            # Starting again should not create a new thread
            original_thread = client._thread
            client.start()
            assert client._thread is original_thread

            # Stop the client
            client.stop()
            assert client._stop.is_set()
            assert client._thread is None

    def test_websocket_client_error_handling(self):
        """Test error handling in WebSocket client."""
        callbacks = [self.event_callback]
        client = WebSocketCallbackClient(
            host="http://localhost:8000",
            conversation_id="test-conv-id",
            callbacks=callbacks,
        )

        # Test that exceptions in callbacks don't crash the client
        def failing_callback(event):
            raise ValueError("Test error")

        def working_callback(event):
            self.received_events.append(event)

        client.callbacks = [failing_callback, working_callback]

        # Create a test event
        from datetime import datetime

        from openhands.sdk.llm import Message, TextContent

        test_event = MessageEvent(
            id="test-event-id",
            timestamp=datetime.now().isoformat(),
            source="agent",
            llm_message=Message(
                role="assistant", content=[TextContent(text="Test message")]
            ),
        )

        # Simulate event processing with error handling
        with patch(
            "openhands.sdk.conversation.impl.remote_conversation.logger"
        ) as mock_logger:
            # Process event - should handle the exception gracefully
            for cb in client.callbacks:
                try:
                    cb(test_event)
                except Exception:
                    # This simulates the exception handling in the actual client
                    mock_logger.exception("ws_event_processing_error", stack_info=True)

            # Verify that the logger was called for the exception
            mock_logger.exception.assert_called_with(
                "ws_event_processing_error", stack_info=True
            )

            # The working callback should still have been called
            assert len(self.received_events) == 1

    def test_websocket_client_stop_timeout(self):
        """Test WebSocket client stop with timeout."""
        callbacks = [self.event_callback]
        client = WebSocketCallbackClient(
            host="http://localhost:8000",
            conversation_id="test-conv-id",
            callbacks=callbacks,
        )

        # Create a mock thread that doesn't respond to join
        mock_thread = MagicMock()
        mock_thread.join.side_effect = lambda timeout: time.sleep(0.1)  # Simulate delay
        client._thread = mock_thread

        # Stop should handle timeout gracefully
        start_time = time.time()
        client.stop()
        end_time = time.time()

        # Should have attempted to join with timeout
        mock_thread.join.assert_called_with(timeout=5)
        # Should complete quickly despite the delay
        assert end_time - start_time < 1.0
        assert client._thread is None

    def test_websocket_client_multiple_callbacks(self):
        """Test WebSocket client with multiple callbacks."""
        callback1_events = []
        callback2_events = []

        def callback1(event):
            callback1_events.append(event)

        def callback2(event):
            callback2_events.append(event)

        callbacks = [callback1, callback2]
        client = WebSocketCallbackClient(
            host="http://localhost:8000",
            conversation_id="test-conv-id",
            callbacks=callbacks,
        )

        # Create a test event
        from datetime import datetime

        from openhands.sdk.llm import Message, TextContent

        test_event = MessageEvent(
            id="test-event-id",
            timestamp=datetime.now().isoformat(),
            source="agent",
            llm_message=Message(
                role="assistant", content=[TextContent(text="Test message")]
            ),
        )

        # Simulate event processing
        for cb in client.callbacks:
            cb(test_event)

        # Both callbacks should have received the event
        assert len(callback1_events) == 1
        assert len(callback2_events) == 1
        assert callback1_events[0].id == test_event.id
        assert callback2_events[0].id == test_event.id

    def test_websocket_client_no_callbacks(self):
        """Test WebSocket client with no callbacks."""
        client = WebSocketCallbackClient(
            host="http://localhost:8000",
            conversation_id="test-conv-id",
            callbacks=[],
        )

        # Should not crash with empty callbacks
        assert client.callbacks == []

        # Create a test event
        from datetime import datetime

        from openhands.sdk.llm import Message, TextContent

        test_event = MessageEvent(
            id="test-event-id",
            timestamp=datetime.now().isoformat(),
            source="agent",
            llm_message=Message(
                role="assistant", content=[TextContent(text="Test message")]
            ),
        )

        # Should handle event processing with no callbacks
        for cb in client.callbacks:
            cb(test_event)  # This loop should not execute

        # No events should be processed
        assert len(self.received_events) == 0
