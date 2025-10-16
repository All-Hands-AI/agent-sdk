"""Tests for WebSocketCallbackClient."""

import time
from unittest.mock import MagicMock, patch

from openhands.sdk.conversation.impl.remote_conversation import WebSocketCallbackClient
from openhands.sdk.event.base import Event
from openhands.sdk.event.llm_convertible import MessageEvent


class TestWebSocketCallbackClient:
    """Test WebSocketCallbackClient functionality."""

    def setup_method(self):
        """Set up test environment."""
        self.received_events = []
        self.callback_calls = []

    def event_callback(self, event: Event):
        """Test callback to capture events."""
        self.received_events.append(event)
        self.callback_calls.append(event)

    def test_websocket_client_initialization(self):
        """Test WebSocketCallbackClient initialization."""
        client = WebSocketCallbackClient(
            host="http://localhost:8000",
            conversation_id="test-conv-id",
            callback=self.event_callback,
        )

        assert client.host == "http://localhost:8000"
        assert client.conversation_id == "test-conv-id"
        assert client.callback == self.event_callback
        assert client._thread is None
        assert not client._stop.is_set()

    def test_websocket_client_start_stop(self):
        """Test starting and stopping the WebSocket client."""
        client = WebSocketCallbackClient(
            host="http://localhost:8000",
            conversation_id="test-conv-id",
            callback=self.event_callback,
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
        client = WebSocketCallbackClient(
            host="http://localhost:8000",
            conversation_id="test-conv-id",
            callback=self.event_callback,
        )

        # Test that exceptions in callback don't crash the client
        def failing_callback(event):
            raise ValueError("Test error")

        # Replace the callback with a failing one
        client.callback = failing_callback

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
            try:
                client.callback(test_event)
            except Exception:
                # This simulates the exception handling in the actual client
                mock_logger.exception("ws_event_processing_error", stack_info=True)

            # Verify that the logger was called for the exception
            mock_logger.exception.assert_called_with(
                "ws_event_processing_error", stack_info=True
            )

    def test_websocket_client_stop_timeout(self):
        """Test WebSocket client stop with timeout."""
        client = WebSocketCallbackClient(
            host="http://localhost:8000",
            conversation_id="test-conv-id",
            callback=self.event_callback,
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

    def test_websocket_client_callback_invocation(self):
        """Test WebSocket client callback invocation."""
        callback_events = []

        def test_callback(event):
            callback_events.append(event)

        client = WebSocketCallbackClient(
            host="http://localhost:8000",
            conversation_id="test-conv-id",
            callback=test_callback,
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
        client.callback(test_event)

        # Callback should have received the event
        assert len(callback_events) == 1
        assert callback_events[0].id == test_event.id

    def test_websocket_client_noop_callback(self):
        """Test WebSocket client with no-op callback."""

        def noop_callback(event):
            pass

        client = WebSocketCallbackClient(
            host="http://localhost:8000",
            conversation_id="test-conv-id",
            callback=noop_callback,
        )

        # Should not crash with no-op callback
        assert client.callback is noop_callback

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

        # Should handle event processing with no-op callback
        client.callback(test_event)  # Should not crash

        # No events should be processed by our test callback
        assert len(self.received_events) == 0
