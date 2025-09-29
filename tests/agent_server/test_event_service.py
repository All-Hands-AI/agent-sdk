from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from openhands.agent_server.event_service import EventService
from openhands.agent_server.models import (
    EventPage,
    EventSortOrder,
    StoredConversation,
)
from openhands.sdk import LLM, Agent, Conversation, Message
from openhands.sdk.conversation.state import AgentExecutionStatus, ConversationState
from openhands.sdk.event.conversation_state import ConversationStateUpdateEvent
from openhands.sdk.event.llm_convertible import MessageEvent
from openhands.sdk.security.confirmation_policy import NeverConfirm


@pytest.fixture
def sample_stored_conversation():
    """Create a sample StoredConversation for testing."""
    return StoredConversation(
        id=uuid4(),
        agent=Agent(llm=LLM(model="gpt-4", service_id="test-llm"), tools=[]),
        confirmation_policy=NeverConfirm(),
        initial_message=None,
        metrics=None,
        created_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
        updated_at=datetime(2025, 1, 1, 12, 30, 0, tzinfo=UTC),
    )


@pytest.fixture
def event_service(sample_stored_conversation):
    """Create an EventService instance for testing."""
    service = EventService(
        stored=sample_stored_conversation,
        file_store_path=Path("test_file_store"),
        working_dir=Path("test_working_dir"),
    )
    return service


@pytest.fixture
def mock_conversation_with_events():
    """Create a mock conversation with sample events."""
    conversation = MagicMock(spec=Conversation)
    state = MagicMock(spec=ConversationState)

    # Create sample events with different timestamps and kinds
    events = [
        MessageEvent(
            id=f"event{index}", source="user", llm_message=Message(role="user")
        )
        for index in range(1, 6)
    ]

    state.events = events
    state.__enter__ = MagicMock(return_value=state)
    state.__exit__ = MagicMock(return_value=None)
    conversation._state = state

    return conversation


class TestEventServiceSearchEvents:
    """Test cases for EventService.search_events method."""

    @pytest.mark.asyncio
    async def test_search_events_inactive_service(self, event_service):
        """Test that search_events raises ValueError when conversation is not active."""
        event_service._conversation = None

        with pytest.raises(ValueError, match="inactive_service"):
            await event_service.search_events()

    @pytest.mark.asyncio
    async def test_search_events_empty_result(self, event_service):
        """Test search_events with no events."""
        # Mock conversation with empty events
        conversation = MagicMock(spec=Conversation)
        state = MagicMock(spec=ConversationState)
        state.events = []
        state.__enter__ = MagicMock(return_value=state)
        state.__exit__ = MagicMock(return_value=None)
        conversation._state = state

        event_service._conversation = conversation

        result = await event_service.search_events()

        assert isinstance(result, EventPage)
        assert result.items == []
        assert result.next_page_id is None

    @pytest.mark.asyncio
    async def test_search_events_basic(
        self, event_service, mock_conversation_with_events
    ):
        """Test basic search_events functionality."""
        event_service._conversation = mock_conversation_with_events

        result = await event_service.search_events()

        assert len(result.items) == 5
        assert result.next_page_id is None
        # Default sort is TIMESTAMP (ascending), so first event should be earliest
        assert result.items[0].timestamp < result.items[-1].timestamp

    @pytest.mark.asyncio
    async def test_search_events_kind_filter(
        self, event_service, mock_conversation_with_events
    ):
        """Test filtering events by kind."""
        event_service._conversation = mock_conversation_with_events

        # Test filtering by ActionEvent
        result = await event_service.search_events(kind="ActionEvent")
        assert len(result.items) == 0

        # Test filtering by MessageEvent
        result = await event_service.search_events(
            kind="openhands.sdk.event.llm_convertible.message.MessageEvent"
        )
        assert len(result.items) == 5
        for event in result.items:
            assert event.__class__.__name__ == "MessageEvent"

        # Test filtering by non-existent kind
        result = await event_service.search_events(kind="NonExistentEvent")
        assert len(result.items) == 0

    @pytest.mark.asyncio
    async def test_search_events_sorting(
        self, event_service, mock_conversation_with_events
    ):
        """Test sorting events by timestamp."""
        event_service._conversation = mock_conversation_with_events

        # Test TIMESTAMP (ascending) - default
        result = await event_service.search_events(sort_order=EventSortOrder.TIMESTAMP)
        assert len(result.items) == 5
        for i in range(len(result.items) - 1):
            assert result.items[i].timestamp <= result.items[i + 1].timestamp

        # Test TIMESTAMP_DESC (descending)
        result = await event_service.search_events(
            sort_order=EventSortOrder.TIMESTAMP_DESC
        )
        assert len(result.items) == 5
        for i in range(len(result.items) - 1):
            assert result.items[i].timestamp >= result.items[i + 1].timestamp

    @pytest.mark.asyncio
    async def test_search_events_pagination(
        self, event_service, mock_conversation_with_events
    ):
        """Test pagination functionality."""
        event_service._conversation = mock_conversation_with_events

        # Test first page with limit 2
        result = await event_service.search_events(limit=2)
        assert len(result.items) == 2
        assert result.next_page_id is not None

        # Test second page using next_page_id
        result = await event_service.search_events(page_id=result.next_page_id, limit=2)
        assert len(result.items) == 2
        assert result.next_page_id is not None

        # Test third page
        result = await event_service.search_events(page_id=result.next_page_id, limit=2)
        assert len(result.items) == 1  # Only one item left
        assert result.next_page_id is None

    @pytest.mark.asyncio
    async def test_search_events_combined_filter_and_sort(
        self, event_service, mock_conversation_with_events
    ):
        """Test combining kind filtering with sorting."""
        event_service._conversation = mock_conversation_with_events

        # Filter by ActionEvent and sort by TIMESTAMP_DESC
        result = await event_service.search_events(
            kind="openhands.sdk.event.llm_convertible.message.MessageEvent",
            sort_order=EventSortOrder.TIMESTAMP_DESC,
        )

        assert len(result.items) == 5
        for event in result.items:
            assert event.__class__.__name__ == "MessageEvent"
        # Should be sorted by timestamp descending (newest first)
        assert result.items[0].timestamp > result.items[1].timestamp

    @pytest.mark.asyncio
    async def test_search_events_pagination_with_filter(
        self, event_service, mock_conversation_with_events
    ):
        """Test pagination with filtering."""
        event_service._conversation = mock_conversation_with_events

        # Filter by MessageEvent with limit 1
        result = await event_service.search_events(
            kind="openhands.sdk.event.llm_convertible.message.MessageEvent", limit=1
        )
        assert len(result.items) == 1
        assert result.items[0].__class__.__name__ == "MessageEvent"
        assert result.next_page_id is not None

        # Get second page
        result = await event_service.search_events(
            kind="openhands.sdk.event.llm_convertible.message.MessageEvent",
            page_id=result.next_page_id,
            limit=4,
        )
        assert len(result.items) == 4
        assert result.items[0].__class__.__name__ == "MessageEvent"
        assert result.next_page_id is None  # No more MessageEvents

    @pytest.mark.asyncio
    async def test_search_events_invalid_page_id(
        self, event_service, mock_conversation_with_events
    ):
        """Test search_events with invalid page_id."""
        event_service._conversation = mock_conversation_with_events

        # Use a non-existent page_id
        invalid_page_id = "invalid_event_id"
        result = await event_service.search_events(page_id=invalid_page_id)

        # Should return all items since page_id doesn't match any event
        assert len(result.items) == 5
        assert result.next_page_id is None

    @pytest.mark.asyncio
    async def test_search_events_large_limit(
        self, event_service, mock_conversation_with_events
    ):
        """Test search_events with limit larger than available events."""
        event_service._conversation = mock_conversation_with_events

        result = await event_service.search_events(limit=100)

        assert len(result.items) == 5  # All available events
        assert result.next_page_id is None

    @pytest.mark.asyncio
    async def test_search_events_zero_limit(
        self, event_service, mock_conversation_with_events
    ):
        """Test search_events with zero limit."""
        event_service._conversation = mock_conversation_with_events

        result = await event_service.search_events(limit=0)

        assert len(result.items) == 0
        # Should still have next_page_id if there are events available
        assert result.next_page_id is not None

    @pytest.mark.asyncio
    async def test_search_events_exact_pagination_boundary(self, event_service):
        """Test pagination when the number of events exactly matches the limit."""
        # Create exactly 3 events
        conversation = MagicMock(spec=Conversation)
        state = MagicMock(spec=ConversationState)

        events = [
            MessageEvent(
                id=f"event{index}", source="user", llm_message=Message(role="user")
            )
            for index in range(1, 4)
        ]

        state.events = events
        state.__enter__ = MagicMock(return_value=state)
        state.__exit__ = MagicMock(return_value=None)
        conversation._state = state

        event_service._conversation = conversation

        # Request exactly 3 events (same as available)
        result = await event_service.search_events(limit=3)

        assert len(result.items) == 3
        assert result.next_page_id is None  # No more events available


class TestEventServiceCountEvents:
    """Test cases for EventService.count_events method."""

    @pytest.mark.asyncio
    async def test_count_events_inactive_service(self, event_service):
        """Test that count_events raises ValueError when service is inactive."""
        event_service._conversation = None

        with pytest.raises(ValueError, match="inactive_service"):
            await event_service.count_events()

    @pytest.mark.asyncio
    async def test_count_events_empty_result(self, event_service):
        """Test count_events with no events."""
        conversation = MagicMock(spec=Conversation)
        state = MagicMock(spec=ConversationState)
        state.events = []
        state.__enter__ = MagicMock(return_value=state)
        state.__exit__ = MagicMock(return_value=None)
        conversation._state = state

        event_service._conversation = conversation

        result = await event_service.count_events()
        assert result == 0

    @pytest.mark.asyncio
    async def test_count_events_basic(
        self, event_service, mock_conversation_with_events
    ):
        """Test basic count_events functionality."""
        event_service._conversation = mock_conversation_with_events

        result = await event_service.count_events()
        assert result == 5  # Total events in mock_conversation_with_events

    @pytest.mark.asyncio
    async def test_count_events_kind_filter(
        self, event_service, mock_conversation_with_events
    ):
        """Test counting events with kind filter."""
        event_service._conversation = mock_conversation_with_events

        # Count all events
        result = await event_service.count_events()
        assert result == 5

        # Count ActionEvent events (should be 5)
        result = await event_service.count_events(
            kind="openhands.sdk.event.llm_convertible.message.MessageEvent"
        )
        assert result == 5

        # Count non-existent event type (should be 0)
        result = await event_service.count_events(kind="NonExistentEvent")
        assert result == 0


class TestEventServiceStateUpdates:
    """Test cases for EventService state update functionality."""

    @pytest.mark.asyncio
    async def test_publish_state_update_inactive_service(self, event_service):
        """Test that _publish_state_update handles inactive service gracefully."""
        event_service._conversation = None

        # Should not raise an exception
        await event_service._publish_state_update()

    @pytest.mark.asyncio
    async def test_publish_state_update_publishes_event(self, event_service):
        """Test that _publish_state_update publishes ConversationStateUpdateEvent."""
        # Mock conversation with state
        conversation = MagicMock(spec=Conversation)
        state = MagicMock(spec=ConversationState)

        # Set up state properties
        state.id = uuid4()
        state.agent_status = AgentExecutionStatus.IDLE
        state.confirmation_policy = NeverConfirm()
        state.activated_knowledge_microagents = []
        state.agent = Agent(llm=LLM(model="gpt-4", service_id="test-llm"), tools=[])
        state.stats = MagicMock()
        state.stats.model_dump.return_value = {"total_cost": 0.0}

        # Mock context manager behavior
        state.__enter__ = MagicMock(return_value=state)
        state.__exit__ = MagicMock(return_value=None)
        conversation._state = state

        event_service._conversation = conversation

        # Mock the pub_sub to capture published events
        published_events = []

        async def mock_pub_sub(event):
            published_events.append(event)

        event_service._pub_sub = mock_pub_sub

        # Call the method
        await event_service._publish_state_update()

        # Verify that a ConversationStateUpdateEvent was published
        assert len(published_events) == 1
        event = published_events[0]
        assert isinstance(event, ConversationStateUpdateEvent)
        assert event.agent_status == "idle"
        assert event.confirmation_policy == state.confirmation_policy.model_dump()
        assert event.activated_knowledge_microagents == []
        assert event.agent == state.agent.model_dump()
        assert event.stats == {"total_cost": 0.0}

    @pytest.mark.asyncio
    async def test_subscribe_to_events_sends_initial_state(self, event_service):
        """Test that subscribe_to_events sends initial state to new subscribers."""
        # Mock conversation with state
        conversation = MagicMock(spec=Conversation)
        state = MagicMock(spec=ConversationState)

        # Set up state properties
        state.id = uuid4()
        state.agent_status = AgentExecutionStatus.RUNNING
        state.confirmation_policy = NeverConfirm()
        state.activated_knowledge_microagents = ["test-agent"]
        state.agent = Agent(llm=LLM(model="gpt-4", service_id="test-llm"), tools=[])
        state.stats = MagicMock()
        state.stats.model_dump.return_value = {"total_cost": 1.5}

        # Mock context manager behavior
        state.__enter__ = MagicMock(return_value=state)
        state.__exit__ = MagicMock(return_value=None)
        conversation._state = state

        event_service._conversation = conversation

        # Mock subscriber
        received_events = []

        async def mock_subscriber(event):
            received_events.append(event)

        # Subscribe
        subscriber_id = await event_service.subscribe_to_events(mock_subscriber)

        # Verify that initial state was sent
        assert len(received_events) == 1
        event = received_events[0]
        assert isinstance(event, ConversationStateUpdateEvent)
        assert event.agent_status == "running"
        assert event.activated_knowledge_microagents == ["test-agent"]
        assert event.stats == {"total_cost": 1.5}

        # Verify subscriber was registered
        assert subscriber_id is not None

    @pytest.mark.asyncio
    async def test_state_updates_after_operations(self, event_service):
        """Test that state updates are published after state-changing operations."""
        # Clean up any existing file store to avoid ID conflicts
        import shutil

        if event_service.file_store_path.exists():
            shutil.rmtree(event_service.file_store_path)

        # Set up the event service with a proper agent configuration
        from pydantic import SecretStr

        from openhands.sdk import LLM, Agent

        llm = LLM(model="gpt-4", api_key=SecretStr("test-key"), service_id="test-llm")
        agent = Agent(llm=llm, tools=[])

        # Update the stored configuration
        event_service.stored.agent = agent

        # Mock the pub_sub to capture published events
        published_events = []

        async def mock_pub_sub(event):
            published_events.append(event)

        event_service._pub_sub = mock_pub_sub

        # Start the event service to register the callback
        await event_service.start()

        # Get the conversation that was created
        conversation = event_service._conversation

        # Test that state changes trigger updates by directly changing state
        # (avoiding the need to mock the frozen Agent)

        # Test direct state change triggers callback
        published_events.clear()
        conversation._state.agent_status = AgentExecutionStatus.RUNNING

        # Wait a bit for the async task to complete
        import asyncio

        await asyncio.sleep(0.1)

        # Direct state change should trigger callback
        # Look for ConversationStateUpdateEvent
        state_update_events = [
            e for e in published_events if isinstance(e, ConversationStateUpdateEvent)
        ]
        assert len(state_update_events) >= 1, (
            f"Expected at least 1 ConversationStateUpdateEvent, "
            f"got {len(state_update_events)}"
        )
        assert isinstance(state_update_events[-1], ConversationStateUpdateEvent)

        # Test another state change
        published_events.clear()
        conversation._state.agent_status = AgentExecutionStatus.PAUSED

        # Wait a bit for the async task to complete
        await asyncio.sleep(0.1)

        # Another state change should trigger callback
        state_update_events = [
            e for e in published_events if isinstance(e, ConversationStateUpdateEvent)
        ]
        assert len(state_update_events) >= 1, (
            f"Expected at least 1 ConversationStateUpdateEvent, "
            f"got {len(state_update_events)}"
        )
        assert isinstance(state_update_events[-1], ConversationStateUpdateEvent)

        # Test set_confirmation_policy() publishes state update
        published_events.clear()
        from openhands.sdk.security.confirmation_policy import AlwaysConfirm

        await event_service.set_confirmation_policy(AlwaysConfirm())

        # Wait a bit for the async task to complete
        await asyncio.sleep(0.1)

        # This should change the confirmation policy, triggering callback
        state_update_events = [
            e for e in published_events if isinstance(e, ConversationStateUpdateEvent)
        ]
        assert len(state_update_events) >= 1, (
            f"Expected at least 1 ConversationStateUpdateEvent, "
            f"got {len(state_update_events)}"
        )
        assert isinstance(state_update_events[-1], ConversationStateUpdateEvent)
