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
    SetConfirmationPolicyRequest,
    StartConversationRequest,
    Success,
    UpdateSecretsRequest,
)
from openhands.sdk import LLM, Agent, TextContent, ToolSpec
from openhands.sdk.conversation.state import AgentExecutionStatus


conversation_router = APIRouter(prefix="/conversations", tags=["Conversations"])
conversation_service = get_default_conversation_service()
config = get_default_config()

# Examples

START_CONVERSATION_EXAMPLES = [
    StartConversationRequest(
        agent=Agent(
            llm=LLM(
                service_id="test-llm",
                model="litellm_proxy/anthropic/claude-sonnet-4-5-20250929",
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


@conversation_router.get("/search")
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


@conversation_router.get("/count")
async def count_conversations(
    status: Annotated[
        AgentExecutionStatus | None,
        Query(title="Optional filter by agent execution status"),
    ] = None,
) -> int:
    """Count conversations matching the given filters"""
    count = await conversation_service.count_conversations(status)
    return count


@conversation_router.get(
    "/{conversation_id}", responses={404: {"description": "Item not found"}}
)
async def get_conversation(conversation_id: UUID) -> ConversationInfo:
    """Given an id, get a conversation"""
    conversation = await conversation_service.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return conversation


@conversation_router.get("/")
async def batch_get_conversations(
    ids: Annotated[list[UUID], Query()],
) -> list[ConversationInfo | None]:
    """Get a batch of conversations given their ids, returning null for
    any missing item"""
    assert len(ids) < 100
    conversations = await conversation_service.batch_get_conversations(ids)
    return conversations


# Write Methods


@conversation_router.post("/")
async def start_conversation(
    request: Annotated[
        StartConversationRequest, Body(examples=START_CONVERSATION_EXAMPLES)
    ],
) -> ConversationInfo:
    """Start a conversation in the local environment."""
    info = await conversation_service.start_conversation(request)
    return info


@conversation_router.post(
    "/{conversation_id}/pause", responses={404: {"description": "Item not found"}}
)
async def pause_conversation(conversation_id: UUID) -> Success:
    """Pause a conversation, allowing it to be resumed later."""
    paused = await conversation_service.pause_conversation(conversation_id)
    if not paused:
        raise HTTPException(status.HTTP_400_BAD_REQUEST)
    return Success()


@conversation_router.delete(
    "/{conversation_id}", responses={404: {"description": "Item not found"}}
)
async def delete_conversation(conversation_id: UUID) -> Success:
    """Permanently delete a conversation."""
    deleted = await conversation_service.delete_conversation(conversation_id)
    if not deleted:
        raise HTTPException(status.HTTP_400_BAD_REQUEST)
    return Success()


@conversation_router.post(
    "/{conversation_id}/run",
    responses={
        404: {"description": "Item not found"},
        409: {"description": "Conversation is already running"},
    },
)
async def run_conversation(conversation_id: UUID) -> Success:
    """Start running the conversation in the background."""
    event_service = await conversation_service.get_event_service(conversation_id)
    if event_service is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)

    try:
        await event_service.run()
    except ValueError as e:
        if str(e) == "conversation_already_running":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Conversation already running. Wait for completion or pause first."
                ),
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return Success()


@conversation_router.post(
    "/{conversation_id}/secrets", responses={404: {"description": "Item not found"}}
)
async def update_conversation_secrets(
    conversation_id: UUID, request: UpdateSecretsRequest
) -> Success:
    """Update secrets for a conversation."""
    event_service = await conversation_service.get_event_service(conversation_id)
    if event_service is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    # Strings are valid SecretValue (SecretValue = str | SecretProvider)
    from typing import cast

    from openhands.sdk.conversation.secrets_manager import SecretValue

    secrets = cast(dict[str, SecretValue], request.secrets)
    await event_service.update_secrets(secrets)
    return Success()


@conversation_router.post(
    "/{conversation_id}/confirmation_policy",
    responses={404: {"description": "Item not found"}},
)
async def set_conversation_confirmation_policy(
    conversation_id: UUID, request: SetConfirmationPolicyRequest
) -> Success:
    """Set the confirmation policy for a conversation."""
    event_service = await conversation_service.get_event_service(conversation_id)
    if event_service is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    await event_service.set_confirmation_policy(request.policy)
    return Success()
