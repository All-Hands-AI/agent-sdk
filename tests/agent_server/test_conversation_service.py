from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from openhands.agent_server.conversation_service import ConversationService
from openhands.agent_server.event_service import EventService
from openhands.agent_server.models import (
    ConversationPage,
    ConversationSortOrder,
    StoredConversation,
)
from openhands.sdk import LLM, Agent
from openhands.sdk.conversation.state import AgentExecutionStatus
from openhands.sdk.security.confirmation_policy import NeverConfirm


@pytest.fixture
def mock_event_service():
    """Create a mock EventService with stored conversation data."""
    service = AsyncMock(spec=EventService)
    return service


@pytest.fixture
def sample_stored_conversation():
    """Create a sample StoredConversation for testing."""
    return StoredConversation(
        id=uuid4(),
        agent=Agent(llm=LLM(model="gpt-4"), tools=[]),
        confirmation_policy=NeverConfirm(),
        initial_message=None,
        metrics=None,
        created_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        updated_at=datetime(2025, 1, 1, 12, 30, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def conversation_service():
    """Create a ConversationService instance for testing."""
    service = ConversationService(
        event_services_path=Path("test_event_services"),
        workspace_path=Path("test_workspace"),
    )
    # Initialize the _event_services dict to simulate an active service
    service._event_services = {}
    return service


class TestConversationServiceSearchConversations:
    """Test cases for ConversationService.search_conversations method."""

    @pytest.mark.asyncio
    async def test_search_conversations_inactive_service(self, conversation_service):
        """Test that search_conversations raises ValueError when service is inactive."""
        conversation_service._event_services = None

        with pytest.raises(ValueError, match="inactive_service"):
            await conversation_service.search_conversations()

    @pytest.mark.asyncio
    async def test_search_conversations_empty_result(self, conversation_service):
        """Test search_conversations with no conversations."""
        result = await conversation_service.search_conversations()

        assert isinstance(result, ConversationPage)
        assert result.items == []
        assert result.next_page_id is None

    @pytest.mark.asyncio
    async def test_search_conversations_basic(
        self, conversation_service, sample_stored_conversation
    ):
        """Test basic search_conversations functionality."""
        # Create mock event service
        mock_service = AsyncMock(spec=EventService)
        mock_service.stored = sample_stored_conversation
        mock_service.get_status.return_value = AgentExecutionStatus.IDLE

        conversation_id = sample_stored_conversation.id
        conversation_service._event_services[conversation_id] = mock_service

        result = await conversation_service.search_conversations()

        assert len(result.items) == 1
        assert result.items[0].id == conversation_id
        assert result.items[0].status == AgentExecutionStatus.IDLE
        assert result.next_page_id is None

    @pytest.mark.asyncio
    async def test_search_conversations_status_filter(self, conversation_service):
        """Test filtering conversations by status."""
        # Create multiple conversations with different statuses
        conversations = []
        for i, status in enumerate(
            [
                AgentExecutionStatus.IDLE,
                AgentExecutionStatus.RUNNING,
                AgentExecutionStatus.FINISHED,
            ]
        ):
            stored_conv = StoredConversation(
                id=uuid4(),
                agent=Agent(llm=LLM(model="gpt-4"), tools=[]),
                confirmation_policy=NeverConfirm(),
                initial_message=None,
                metrics=None,
                created_at=datetime(2025, 1, 1, 12, i, 0, tzinfo=timezone.utc),
                updated_at=datetime(2025, 1, 1, 12, i + 30, 0, tzinfo=timezone.utc),
            )

            mock_service = AsyncMock(spec=EventService)
            mock_service.stored = stored_conv
            mock_service.get_status.return_value = status

            conversation_service._event_services[stored_conv.id] = mock_service
            conversations.append((stored_conv.id, status))

        # Test filtering by IDLE status
        result = await conversation_service.search_conversations(
            status=AgentExecutionStatus.IDLE
        )
        assert len(result.items) == 1
        assert result.items[0].status == AgentExecutionStatus.IDLE

        # Test filtering by RUNNING status
        result = await conversation_service.search_conversations(
            status=AgentExecutionStatus.RUNNING
        )
        assert len(result.items) == 1
        assert result.items[0].status == AgentExecutionStatus.RUNNING

        # Test filtering by non-existent status
        result = await conversation_service.search_conversations(
            status=AgentExecutionStatus.ERROR
        )
        assert len(result.items) == 0

    @pytest.mark.asyncio
    async def test_search_conversations_sorting(self, conversation_service):
        """Test sorting conversations by different criteria."""
        # Create conversations with different timestamps
        conversations = []

        for i in range(3):
            stored_conv = StoredConversation(
                id=uuid4(),
                agent=Agent(llm=LLM(model="gpt-4"), tools=[]),
                confirmation_policy=NeverConfirm(),
                initial_message=None,
                metrics=None,
                created_at=datetime(
                    2025, 1, i + 1, 12, 0, 0, tzinfo=timezone.utc
                ),  # Different days
                updated_at=datetime(2025, 1, i + 1, 12, 30, 0, tzinfo=timezone.utc),
            )

            mock_service = AsyncMock(spec=EventService)
            mock_service.stored = stored_conv
            mock_service.get_status.return_value = AgentExecutionStatus.IDLE

            conversation_service._event_services[stored_conv.id] = mock_service
            conversations.append(stored_conv)

        # Test CREATED_AT (ascending)
        result = await conversation_service.search_conversations(
            sort_order=ConversationSortOrder.CREATED_AT
        )
        assert len(result.items) == 3
        assert (
            result.items[0].created_at
            < result.items[1].created_at
            < result.items[2].created_at
        )

        # Test CREATED_AT_DESC (descending) - default
        result = await conversation_service.search_conversations(
            sort_order=ConversationSortOrder.CREATED_AT_DESC
        )
        assert len(result.items) == 3
        assert (
            result.items[0].created_at
            > result.items[1].created_at
            > result.items[2].created_at
        )

        # Test UPDATED_AT (ascending)
        result = await conversation_service.search_conversations(
            sort_order=ConversationSortOrder.UPDATED_AT
        )
        assert len(result.items) == 3
        assert (
            result.items[0].updated_at
            < result.items[1].updated_at
            < result.items[2].updated_at
        )

        # Test UPDATED_AT_DESC (descending)
        result = await conversation_service.search_conversations(
            sort_order=ConversationSortOrder.UPDATED_AT_DESC
        )
        assert len(result.items) == 3
        assert (
            result.items[0].updated_at
            > result.items[1].updated_at
            > result.items[2].updated_at
        )

    @pytest.mark.asyncio
    async def test_search_conversations_pagination(self, conversation_service):
        """Test pagination functionality."""
        # Create 5 conversations
        conversation_ids = []
        for i in range(5):
            stored_conv = StoredConversation(
                id=uuid4(),
                agent=Agent(llm=LLM(model="gpt-4"), tools=[]),
                confirmation_policy=NeverConfirm(),
                initial_message=None,
                metrics=None,
                created_at=datetime(2025, 1, 1, 12, i, 0, tzinfo=timezone.utc),
                updated_at=datetime(2025, 1, 1, 12, i + 30, 0, tzinfo=timezone.utc),
            )

            mock_service = AsyncMock(spec=EventService)
            mock_service.stored = stored_conv
            mock_service.get_status.return_value = AgentExecutionStatus.IDLE

            conversation_service._event_services[stored_conv.id] = mock_service
            conversation_ids.append(stored_conv.id)

        # Test first page with limit 2
        result = await conversation_service.search_conversations(limit=2)
        assert len(result.items) == 2
        assert result.next_page_id is not None

        # Test second page using next_page_id
        result = await conversation_service.search_conversations(
            page_id=result.next_page_id, limit=2
        )
        assert len(result.items) == 2
        assert result.next_page_id is not None

        # Test last page
        result = await conversation_service.search_conversations(
            page_id=result.next_page_id, limit=2
        )
        assert len(result.items) == 1  # Only one item left
        assert result.next_page_id is None

    @pytest.mark.asyncio
    async def test_search_conversations_combined_filter_and_sort(
        self, conversation_service
    ):
        """Test combining status filtering with sorting."""
        # Create conversations with mixed statuses and timestamps
        conversations_data = [
            (
                AgentExecutionStatus.IDLE,
                datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            ),
            (
                AgentExecutionStatus.RUNNING,
                datetime(2025, 1, 2, 12, 0, 0, tzinfo=timezone.utc),
            ),
            (
                AgentExecutionStatus.IDLE,
                datetime(2025, 1, 3, 12, 0, 0, tzinfo=timezone.utc),
            ),
            (
                AgentExecutionStatus.FINISHED,
                datetime(2025, 1, 4, 12, 0, 0, tzinfo=timezone.utc),
            ),
        ]

        for status, created_at in conversations_data:
            stored_conv = StoredConversation(
                id=uuid4(),
                agent=Agent(llm=LLM(model="gpt-4"), tools=[]),
                confirmation_policy=NeverConfirm(),
                initial_message=None,
                metrics=None,
                created_at=created_at,
                updated_at=created_at,
            )

            mock_service = AsyncMock(spec=EventService)
            mock_service.stored = stored_conv
            mock_service.get_status.return_value = status

            conversation_service._event_services[stored_conv.id] = mock_service

        # Filter by IDLE status and sort by CREATED_AT_DESC
        result = await conversation_service.search_conversations(
            status=AgentExecutionStatus.IDLE,
            sort_order=ConversationSortOrder.CREATED_AT_DESC,
        )

        assert len(result.items) == 2  # Two IDLE conversations
        # Should be sorted by created_at descending (newest first)
        assert result.items[0].created_at > result.items[1].created_at

    @pytest.mark.asyncio
    async def test_search_conversations_invalid_page_id(
        self, conversation_service, sample_stored_conversation
    ):
        """Test search_conversations with invalid page_id."""
        mock_service = AsyncMock(spec=EventService)
        mock_service.stored = sample_stored_conversation
        mock_service.get_status.return_value = AgentExecutionStatus.IDLE

        conversation_service._event_services[sample_stored_conversation.id] = (
            mock_service
        )

        # Use a non-existent page_id
        invalid_page_id = uuid4().hex
        result = await conversation_service.search_conversations(
            page_id=invalid_page_id
        )

        # Should return all items since page_id doesn't match any conversation
        assert len(result.items) == 1
        assert result.next_page_id is None


class TestConversationServiceCountConversations:
    """Test cases for ConversationService.count_conversations method."""

    @pytest.mark.asyncio
    async def test_count_conversations_inactive_service(self, conversation_service):
        """Test that count_conversations raises ValueError when service is inactive."""
        conversation_service._event_services = None

        with pytest.raises(ValueError, match="inactive_service"):
            await conversation_service.count_conversations()

    @pytest.mark.asyncio
    async def test_count_conversations_empty_result(self, conversation_service):
        """Test count_conversations with no conversations."""
        result = await conversation_service.count_conversations()
        assert result == 0

    @pytest.mark.asyncio
    async def test_count_conversations_basic(
        self, conversation_service, sample_stored_conversation
    ):
        """Test basic count_conversations functionality."""
        # Create mock event service
        mock_service = AsyncMock(spec=EventService)
        mock_service.stored = sample_stored_conversation
        mock_service.get_status.return_value = AgentExecutionStatus.IDLE

        conversation_id = sample_stored_conversation.id
        conversation_service._event_services[conversation_id] = mock_service

        result = await conversation_service.count_conversations()
        assert result == 1

    @pytest.mark.asyncio
    async def test_count_conversations_status_filter(self, conversation_service):
        """Test counting conversations with status filter."""
        # Create multiple conversations with different statuses
        statuses = [
            AgentExecutionStatus.IDLE,
            AgentExecutionStatus.RUNNING,
            AgentExecutionStatus.FINISHED,
            AgentExecutionStatus.IDLE,  # Another IDLE one
        ]

        for i, status in enumerate(statuses):
            stored_conv = StoredConversation(
                id=uuid4(),
                agent=Agent(llm=LLM(model="gpt-4"), tools=[]),
                confirmation_policy=NeverConfirm(),
                initial_message=None,
                metrics=None,
                created_at=datetime(2025, 1, 1, 12, i, 0, tzinfo=timezone.utc),
                updated_at=datetime(2025, 1, 1, 12, i + 30, 0, tzinfo=timezone.utc),
            )

            mock_service = AsyncMock(spec=EventService)
            mock_service.stored = stored_conv
            mock_service.get_status.return_value = status

            conversation_service._event_services[stored_conv.id] = mock_service

        # Test counting all conversations
        result = await conversation_service.count_conversations()
        assert result == 4

        # Test counting by IDLE status (should be 2)
        result = await conversation_service.count_conversations(
            status=AgentExecutionStatus.IDLE
        )
        assert result == 2

        # Test counting by RUNNING status (should be 1)
        result = await conversation_service.count_conversations(
            status=AgentExecutionStatus.RUNNING
        )
        assert result == 1

        # Test counting by non-existent status (should be 0)
        result = await conversation_service.count_conversations(
            status=AgentExecutionStatus.ERROR
        )
        assert result == 0
