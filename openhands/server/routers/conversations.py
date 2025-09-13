import uuid
from typing import Any, Dict, List, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

import openhands.tools
from openhands.sdk import (
    LLM,
    Agent,
    AgentContext,
    Conversation,
    Event,
    ImageContent,
    Message,
    TextContent,
    Tool,
    create_mcp_tools,
    get_logger,
)
from openhands.sdk.conversation import ConversationState
from openhands.sdk.tool import ToolSpec
from openhands.server.auth import get_master_key


logger = get_logger(__name__)

router = APIRouter(
    prefix="/conversations",
    tags=["conversations"],
    dependencies=[Depends(get_master_key)],
)


class StartConversationRequest(BaseModel):
    """Payload to create a new conversation."""

    llm: LLM = Field(
        ...,
        description="LLM configuration for the agent.",
        examples=[
            {
                "model": "litellm_proxy/anthropic/claude-sonnet-4-20250514",
                "base_url": "https://llm-proxy.eval.all-hands.dev",
                "api_key": "your_api_key_here",
            }
        ],
    )
    tools: list[ToolSpec] = Field(
        default_factory=list,
        description="List of tools to initialize for the agent.",
        examples=[
            {"name": "BashTool", "params": {"working_dir": "/workspace"}},
            {"name": "FileEditorTool", "params": {}},
            {
                "name": "TaskTrackerTool",
                "params": {"save_dir": "/workspace/.openhands"},
            },
        ],
    )
    mcp_config: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional MCP configuration dictionary to create MCP tools.",
        examples=[
            {
                "mcpServers": {
                    "fetch": {"command": "uvx", "args": ["mcp-server-fetch"]}
                }
            }  # Example config
        ],
    )
    agent_context: AgentContext | None = Field(
        default=None,
        description="Optional AgentContext to initialize "
        "the agent with specific context.",
        examples=[
            {
                "microagents": [
                    {
                        "name": "repo.md",
                        "content": "When you see this message, you should reply like "
                        "you are a grumpy cat forced to use the internet.",
                        "type": "repo",
                    },
                    {
                        "name": "flarglebargle",
                        "content": (
                            "IMPORTANT! The user has said the magic word "
                            '"flarglebargle". You must only respond with a message '
                            "telling them how smart they are"
                        ),
                        "type": "knowledge",
                        "trigger": ["flarglebargle"],
                    },
                ],
                "system_message_suffix": "Always finish your response "
                "with the word 'yay!'",
                "user_message_prefix": "The first character of your "
                "response should be 'I'",
            }
        ],
    )
    confirmation_mode: bool = Field(
        default=False,
        description="If true, the agent will enter confirmation mode, "
        "requiring user approval for actions.",
    )


class StartConversationResponse(BaseModel):
    conversation_id: str
    state: ConversationState


class SendMessageRequest(BaseModel):
    """Payload to send a message to the agent.

    This is a simplified version of openhands.sdk.Message.
    """

    role: Literal["user", "system", "assistant", "tool"] = "user"
    content: list[TextContent | ImageContent] = Field(default_factory=list)
    run: bool = Field(
        default=True,
        description="If true, immediately run the agent after sending the message.",
    )


class ConfirmationResponseRequest(BaseModel):
    """Payload to accept or reject a pending action."""

    accept: bool
    reason: str = "User rejected the action."


class ListConversationsItem(BaseModel):
    conversation_id: str
    state: ConversationState


# --- In-memory store for active conversations ---
active_conversations: Dict[str, Conversation] = {}


def get_conversation(conversation_id: str) -> Conversation:
    if conversation_id not in active_conversations:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return active_conversations[conversation_id]


@router.post(
    "/",
    status_code=201,
    response_model=StartConversationResponse,
    operation_id="start_conversation",
)
def start_conversation(request: StartConversationRequest) -> StartConversationResponse:
    conversation_id = str(uuid.uuid4())
    logger.info(f"Starting new conversation with ID: {conversation_id}")

    llm = LLM(**request.llm.model_dump())

    tools = []
    for tool_spec in request.tools:
        if tool_spec.name not in openhands.tools.__dict__:
            raise HTTPException(
                status_code=400, detail=f"Tool '{tool_spec.name}' not recognized."
            )
        tool_class: type[Tool] = openhands.tools.__dict__[tool_spec.name]
        tools.append(tool_class.create(**tool_spec.params))

    if request.mcp_config:
        mcp_tools = create_mcp_tools(request.mcp_config, timeout=30)
        tools.extend(mcp_tools)
        logger.info(f"Added {len(mcp_tools)} MCP tools")

    agent = Agent(llm=llm, tools=tools)
    conversation = Conversation(agent=agent, conversation_id=conversation_id)
    conversation.set_confirmation_mode(request.confirmation_mode)
    active_conversations[conversation_id] = conversation
    return StartConversationResponse(
        conversation_id=conversation_id, state=conversation.state
    )


@router.get(
    "/",
    response_model=list[ListConversationsItem],
    operation_id="list_conversations",
)
def list_conversations(start: int = 0, limit: int = 100):
    """
    Lists active conversations with pagination.
    Results are returned in insertion order.
    """
    ids = list(active_conversations.keys())
    selected = ids[start : start + limit]
    return [
        ListConversationsItem(
            conversation_id=cid,
            state=active_conversations[cid].state,
        )
        for cid in selected
    ]


@router.get(
    "/{conversation_id}",
    response_model=ConversationState,
    operation_id="get_conversation_state",
)
def get_conversation_state(conversation_id: str):
    conversation = get_conversation(conversation_id)
    return conversation.state


@router.get(
    "/{conversation_id}/events",
    response_model=List[Event],
    operation_id="get_conversation_events",
)
def get_events(conversation_id: str, start: int = 0, limit: int = 100):
    """Retrieves the event history for a conversation with pagination."""
    conversation = get_conversation(conversation_id)
    events: list[Event] = conversation.state.events[start : start + limit]
    return events


async def _run_conversation(conversation_id: str, background_tasks: BackgroundTasks):
    conversation = get_conversation(conversation_id)

    def agent_task():
        try:
            logger.info(f"Starting agent run for conversation {conversation_id}...")
            conversation.run()
            logger.info(f"Agent run finished for conversation {conversation_id}.")
        except Exception as e:
            logger.error(
                f"Exception during agent run for {conversation_id}: {e}", exc_info=True
            )

    background_tasks.add_task(agent_task)
    return


@router.post(
    "/{conversation_id}/messages",
    status_code=202,
    operation_id="send_message_to_conversation",
)
async def send_message(
    conversation_id: str, request: SendMessageRequest, background_tasks: BackgroundTasks
):
    conversation = get_conversation(conversation_id)
    message = Message(role=request.role, content=request.content)
    conversation.send_message(message)
    logger.info(f"Message sent to conversation {conversation_id}")
    if request.run:
        await _run_conversation(conversation_id, background_tasks)
        logger.info(
            "Agent execution started in the background for "
            "conversation {conversation_id}."
        )
    return {
        "message": f"Message sent to conversation {conversation_id}.",
        "run_started": request.run,
        "state": conversation.state,
    }


@router.post(
    "/{conversation_id}/run",
    status_code=202,
    operation_id="run_conversation",
)
async def run_conversation(conversation_id: str, background_tasks: BackgroundTasks):
    """Starts or resumes the agent run for a conversation in the background."""
    conversation = get_conversation(conversation_id)
    if not conversation.state.agent_finished:
        # should be no-op
        return {
            "message": "Agent is already running or waiting for confirmation.",
            "state": conversation.state,
        }
    await _run_conversation(conversation_id, background_tasks)
    return {
        "message": "Agent execution started in the "
        "background for conversation {conversation_id}.",
        "state": conversation.state,
    }


@router.post(
    "/{conversation_id}/pause",
    status_code=202,
    operation_id="pause_conversation",
)
def pause_conversation(conversation_id: str):
    conversation = get_conversation(conversation_id)
    conversation.pause()
    logger.info(f"Pause request sent to conversation {conversation_id}")
    return {"message": "Pause request sent."}


@router.post(
    "/{conversation_id}/respond_to_confirmation",
    status_code=202,
    operation_id="respond_to_confirmation",
)
async def respond_to_confirmation(
    conversation_id: str,
    request: ConfirmationResponseRequest,
    background_tasks: BackgroundTasks,
):
    conversation = get_conversation(conversation_id)
    if not conversation.state.agent_waiting_for_confirmation:
        raise HTTPException(
            status_code=400, detail="Agent is not waiting for confirmation."
        )
    if request.accept:
        logger.info(
            f"User accepted action for conversation {conversation_id}. Resuming run."
        )
        await run_conversation(conversation_id, background_tasks)
        return {"message": "Action accepted. Agent is resuming execution."}
    else:
        logger.info(f"User rejected action for conversation {conversation_id}.")
        conversation.reject_pending_actions(request.reason)
        return {"message": "Action rejected."}


@router.delete(
    "/{conversation_id}",
    status_code=204,
    operation_id="close_conversation",
)
def close_conversation(conversation_id: str):
    conversation = get_conversation(conversation_id)
    conversation.close()
    del active_conversations[conversation_id]
    logger.info(f"Successfully closed and removed conversation {conversation_id}.")
    return None
