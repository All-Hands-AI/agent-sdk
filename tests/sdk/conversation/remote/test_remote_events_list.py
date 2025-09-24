"""Tests for RemoteEventsList."""

from unittest.mock import Mock

import httpx
import pytest

from openhands.sdk.conversation.impl.remote_conversation import RemoteEventsList
from openhands.sdk.event.base import EventBase
from openhands.sdk.event.llm_convertible import MessageEvent


# Create test event classes at module level to avoid duplicate registration
class MockActionEvent(EventBase):
    pass


class MockObservationEvent(EventBase):
    pass


class MockGenericEvent(EventBase):
    pass


class TestRemoteEventsList:
    """Test RemoteEventsList functionality."""

    def setup_method(self):
        """Set up test environment."""
        self.mock_client = Mock(spec=httpx.Client)
        self.conversation_id = "test-conv-id"

    def create_mock_event(
        self, event_id: str, event_type: str = "MessageEvent"
    ) -> EventBase:
        """Create a mock event for testing."""
        from datetime import datetime

        from openhands.sdk.llm import Message, TextContent

        timestamp = datetime.now().isoformat()

        if event_type == "MessageEvent":
            return MessageEvent(
                id=event_id,
                timestamp=timestamp,
                source="agent",
                llm_message=Message(
                    role="assistant", content=[TextContent(text=f"Message {event_id}")]
                ),
            )
        elif event_type == "ActionEvent":
            # ActionEvent is complex, so let's create a simple test event instead
            return MockActionEvent(id=event_id, timestamp=timestamp, source="agent")
        elif event_type == "ObservationEvent":
            # ObservationEvent is complex, so let's create a simple test event instead
            return MockObservationEvent(
                id=event_id, timestamp=timestamp, source="environment"
            )
        else:
            # Generic event - create a simple EventBase subclass for testing
            return MockGenericEvent(id=event_id, timestamp=timestamp, source="agent")

    def create_mock_api_response(
        self, events: list[EventBase], next_page_id: str | None = None
    ):
        """Create a mock API response."""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "items": [event.model_dump() for event in events],
            "next_page_id": next_page_id,
        }
        return mock_response

    def test_remote_events_list_initialization_single_page(self):
        """Test RemoteEventsList initialization with single page of events."""
        # Create test events
        events = [
            self.create_mock_event("event-1", "MessageEvent"),
            self.create_mock_event("event-2", "ActionEvent"),
            self.create_mock_event("event-3", "ObservationEvent"),
        ]

        # Mock API response
        mock_response = self.create_mock_api_response(events)
        self.mock_client.get.return_value = mock_response

        # Initialize RemoteEventsList
        events_list = RemoteEventsList(self.mock_client, self.conversation_id)

        # Verify API was called correctly
        self.mock_client.get.assert_called_once_with(
            f"/api/conversations/{self.conversation_id}/events/search",
            params={"limit": 100},
        )

        # Verify events were loaded
        assert len(events_list) == 3
        assert events_list[0].id == "event-1"
        assert events_list[1].id == "event-2"
        assert events_list[2].id == "event-3"

        # Verify event IDs are cached
        assert "event-1" in events_list._cached_event_ids
        assert "event-2" in events_list._cached_event_ids
        assert "event-3" in events_list._cached_event_ids

    def test_remote_events_list_initialization_multiple_pages(self):
        """Test RemoteEventsList initialization with multiple pages."""
        # Create test events for multiple pages
        page1_events = [
            self.create_mock_event("event-1", "MessageEvent"),
            self.create_mock_event("event-2", "ActionEvent"),
        ]
        page2_events = [
            self.create_mock_event("event-3", "ObservationEvent"),
            self.create_mock_event("event-4", "MessageEvent"),
        ]

        # Mock API responses
        page1_response = self.create_mock_api_response(page1_events, "page-2")
        page2_response = self.create_mock_api_response(page2_events)

        self.mock_client.get.side_effect = [page1_response, page2_response]

        # Initialize RemoteEventsList
        events_list = RemoteEventsList(self.mock_client, self.conversation_id)

        # Verify API was called for both pages
        assert self.mock_client.get.call_count == 2

        # First call
        self.mock_client.get.assert_any_call(
            f"/api/conversations/{self.conversation_id}/events/search",
            params={"limit": 100},
        )

        # Second call with page_id
        self.mock_client.get.assert_any_call(
            f"/api/conversations/{self.conversation_id}/events/search",
            params={"limit": 100, "page_id": "page-2"},
        )

        # Verify all events were loaded
        assert len(events_list) == 4
        assert events_list[0].id == "event-1"
        assert events_list[1].id == "event-2"
        assert events_list[2].id == "event-3"
        assert events_list[3].id == "event-4"

    def test_remote_events_list_indexing_and_iteration(self):
        """Test indexing, slicing, and iteration."""
        events = [
            self.create_mock_event("event-1", "MessageEvent"),
            self.create_mock_event("event-2", "ActionEvent"),
            self.create_mock_event("event-3", "ObservationEvent"),
        ]

        mock_response = self.create_mock_api_response(events)
        self.mock_client.get.return_value = mock_response

        events_list = RemoteEventsList(self.mock_client, self.conversation_id)

        # Test positive indexing
        assert events_list[0].id == "event-1"
        assert events_list[1].id == "event-2"
        assert events_list[2].id == "event-3"

        # Test negative indexing
        assert events_list[-1].id == "event-3"
        assert events_list[-2].id == "event-2"
        assert events_list[-3].id == "event-1"

        # Test slice operations
        slice_result = events_list[1:3]
        assert len(slice_result) == 2
        assert slice_result[0].id == "event-2"
        assert slice_result[1].id == "event-3"

        # Test slice with step
        slice_result = events_list[::2]
        assert len(slice_result) == 2
        assert slice_result[0].id == "event-1"
        assert slice_result[1].id == "event-3"

        # Test iteration
        iterated_events = list(events_list)
        assert [e.id for e in iterated_events] == ["event-1", "event-2", "event-3"]

    def test_remote_events_list_add_event(self):
        """Test adding events to RemoteEventsList."""
        # Initialize with empty list
        mock_response = self.create_mock_api_response([])
        self.mock_client.get.return_value = mock_response

        events_list = RemoteEventsList(self.mock_client, self.conversation_id)
        assert len(events_list) == 0

        # Add a new event
        new_event = self.create_mock_event("new-event", "MessageEvent")
        events_list.add_event(new_event)

        # Verify event was added
        assert len(events_list) == 1
        assert events_list[0].id == "new-event"
        assert "new-event" in events_list._cached_event_ids

        # Add another event
        another_event = self.create_mock_event("another-event", "ActionEvent")
        events_list.add_event(another_event)

        assert len(events_list) == 2
        assert events_list[1].id == "another-event"

    def test_remote_events_list_add_duplicate_event(self):
        """Test adding duplicate events to RemoteEventsList."""
        mock_response = self.create_mock_api_response([])
        self.mock_client.get.return_value = mock_response

        events_list = RemoteEventsList(self.mock_client, self.conversation_id)

        # Add an event
        event = self.create_mock_event("duplicate-event", "MessageEvent")
        events_list.add_event(event)
        assert len(events_list) == 1

        # Try to add the same event again
        events_list.add_event(event)
        assert len(events_list) == 1  # Should not increase

        # Try to add an event with the same ID but different content
        duplicate_event = self.create_mock_event("duplicate-event", "ActionEvent")
        events_list.add_event(duplicate_event)
        assert len(events_list) == 1  # Should not increase

    def test_remote_events_list_create_default_callback(self):
        """Test creating default callback for RemoteEventsList."""
        mock_response = self.create_mock_api_response([])
        self.mock_client.get.return_value = mock_response

        events_list = RemoteEventsList(self.mock_client, self.conversation_id)
        callback = events_list.create_default_callback()

        # Test the callback
        test_event = self.create_mock_event("callback-event", "MessageEvent")
        callback(test_event)

        # Verify event was added through callback
        assert len(events_list) == 1
        assert events_list[0].id == "callback-event"

    def test_remote_events_list_append_not_implemented(self):
        """Test that append method raises NotImplementedError."""
        mock_response = self.create_mock_api_response([])
        self.mock_client.get.return_value = mock_response

        events_list = RemoteEventsList(self.mock_client, self.conversation_id)
        test_event = self.create_mock_event("test-event", "MessageEvent")

        with pytest.raises(
            NotImplementedError,
            match="Cannot directly append events to remote conversation",
        ):
            events_list.append(test_event)

    def test_remote_events_list_api_error_handling(self):
        """Test error handling when API calls fail."""
        # Mock API error
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "API Error", request=Mock(), response=Mock()
        )
        self.mock_client.get.return_value = mock_response

        # Should raise the HTTP error
        with pytest.raises(httpx.HTTPStatusError):
            RemoteEventsList(self.mock_client, self.conversation_id)

    def test_remote_events_list_empty_response(self):
        """Test handling of empty API response."""
        mock_response = self.create_mock_api_response([])
        self.mock_client.get.return_value = mock_response

        events_list = RemoteEventsList(self.mock_client, self.conversation_id)

        assert len(events_list) == 0
        assert len(events_list._cached_events) == 0
        assert len(events_list._cached_event_ids) == 0

        # Test iteration on empty list
        assert list(events_list) == []

        # Test indexing on empty list
        with pytest.raises(IndexError):
            _ = events_list[0]
