"""Conversation router for OpenHands SDK."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, HTTPException, Query, status
from pydantic import SecretStr

from openhands.agent_server.config import get_default_config
from openhands.agent_server.conversation_service import (
    get_default_conversation_service,
)
from openhands.agent_server.models import (
    ConversationInfo,
    ConversationPage,
    ConversationSortOrder,
    SendMessageRequest,
    StartConversationRequest,
    Success,
)
from openhands.sdk import LLM, Agent, TextContent, ToolSpec
from openhands.sdk.conversation.state import AgentExecutionStatus


router = APIRouter(prefix="/api/conversations")
conversation_service = get_default_conversation_service()
config = get_default_config()

# Examples

START_CONVERSATION_EXAMPLES = [
    StartConversationRequest(
        agent=Agent(
            llm=LLM(
                model="litellm_proxy/anthropic/claude-sonnet-4-20250514",
                base_url="https://llm-proxy.app.all-hands.dev",
                api_key=SecretStr("secret"),
            ),
            tools=[
                ToolSpec(
                    name="BashTool", params={"working_dir": config.workspace_path}
                ),
                ToolSpec(
                    name="FileEditorTool",
                    params={"workspace_root": config.workspace_path},
                ),
                ToolSpec(
                    name="TaskTrackerTool",
                    # task tracker json is a type of metadata,
                    # so we save it in conversations_path
                    params={"save_dir": f"{config.conversations_path}"},
                ),
            ],
        ),
        initial_message=SendMessageRequest(
            role="user", content=[TextContent(text="Flip a coin!")]
        ),
    ).model_dump(exclude_defaults=True)
]


# Read methods


@router.get("/search")
async def search_conversations(
    page_id: Annotated[
        str | None,
        Query(title="Optional next_page_id from the previously returned page"),
    ] = None,
    limit: Annotated[
        int,
        Query(title="The max number of results in the page", gt=0, lte=100),
    ] = 100,
    status: Annotated[
        AgentExecutionStatus | None,
        Query(title="Optional filter by agent execution status"),
    ] = None,
    sort_order: Annotated[
        ConversationSortOrder,
        Query(title="Sort order for conversations"),
    ] = ConversationSortOrder.CREATED_AT_DESC,
) -> ConversationPage:
    """Search / List conversations"""
    assert limit > 0
    assert limit <= 100
    return await conversation_service.search_conversations(
        page_id, limit, status, sort_order
    )


@router.get("/count")
async def count_conversations(
    status: Annotated[
        AgentExecutionStatus | None,
        Query(title="Optional filter by agent execution status"),
    ] = None,
) -> int:
    """Count conversations matching the given filters"""
    count = await conversation_service.count_conversations(status)
    return count


@router.get("/{conversation_id}", responses={404: {"description": "Item not found"}})
async def get_conversation(conversation_id: UUID) -> ConversationInfo:
    """Given an id, get a conversation"""
    conversation = await conversation_service.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return conversation


@router.get("/")
async def batch_get_conversations(
    ids: Annotated[list[UUID], Query()],
) -> list[ConversationInfo | None]:
    """Get a batch of conversations given their ids, returning null for
    any missing item"""
    assert len(ids) < 100
    conversations = await conversation_service.batch_get_conversations(ids)
    return conversations


# Write Methods


@router.post("/")
async def start_conversation(
    request: Annotated[
        StartConversationRequest, Body(examples=START_CONVERSATION_EXAMPLES)
    ],
) -> ConversationInfo:
    """Start a conversation in the local environment."""
    info = await conversation_service.start_conversation(request)
    return info


@router.post(
    "/{conversation_id}/pause", responses={404: {"description": "Item not found"}}
)
async def pause_conversation(conversation_id: UUID) -> Success:
    """Pause a conversation, allowing it to be resumed later."""
    paused = await conversation_service.pause_conversation(conversation_id)
    if not paused:
        raise HTTPException(status.HTTP_400_BAD_REQUEST)
    return Success()


@router.post(
    "/{conversation_id}/resume", responses={404: {"description": "Item not found"}}
)
async def resume_conversation(conversation_id: UUID) -> Success:
    """Resume a paused conversation."""
    resumed = await conversation_service.resume_conversation(conversation_id)
    if not resumed:
        raise HTTPException(status.HTTP_400_BAD_REQUEST)
    return Success()


@router.delete("/{conversation_id}", responses={404: {"description": "Item not found"}})
async def delete_conversation(conversation_id: UUID) -> Success:
    """Permanently delete a conversation."""
    deleted = await conversation_service.delete_conversation(conversation_id)
    if not deleted:
        raise HTTPException(status.HTTP_400_BAD_REQUEST)
    return Success()
