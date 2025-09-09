import copy
from typing import cast

from litellm import ChatCompletionMessageToolCall, ChatCompletionToolParam
from pydantic import ConfigDict, Field, computed_field

from openhands.sdk.event.base import N_CHAR_PREVIEW, LLMConvertibleEvent
from openhands.sdk.event.types import SourceType
from openhands.sdk.llm import ImageContent, Message, TextContent, content_to_str
from openhands.sdk.llm.utils.metrics import MetricsSnapshot
from openhands.sdk.tool import Action, Observation


class SystemPromptEvent(LLMConvertibleEvent):
    """System prompt added by the agent."""

    source: SourceType = "agent"
    system_prompt: TextContent = Field(..., description="The system prompt text")
    tools: list[ChatCompletionToolParam] = Field(
        ..., description="List of tools in OpenAI tool format"
    )

    def to_llm_message(self) -> Message:
        return Message(role="system", content=[self.system_prompt])

    def __str__(self) -> str:
        """Plain text string representation for SystemPromptEvent."""
        base_str = f"{self.__class__.__name__} ({self.source})"
        prompt_preview = (
            self.system_prompt.text[:N_CHAR_PREVIEW] + "..."
            if len(self.system_prompt.text) > N_CHAR_PREVIEW
            else self.system_prompt.text
        )
        tool_count = len(self.tools)
        return (
            f"{base_str}\n  System: {prompt_preview}\n  Tools: {tool_count} available"
        )


class ActionEvent(LLMConvertibleEvent):
    source: SourceType = "agent"
    thought: list[TextContent] = Field(
        ..., description="The thought process of the agent before taking this action"
    )
    reasoning_content: str | None = Field(
        default=None,
        description="Intermediate reasoning/thinking content from reasoning models",
    )
    action: Action = Field(..., description="Single action (tool call) returned by LLM")
    tool_name: str = Field(..., description="The name of the tool being called")
    tool_call_id: str = Field(
        ..., description="The unique id returned by LLM API for this tool call"
    )
    tool_call: ChatCompletionMessageToolCall = Field(
        ...,
        description=(
            "The tool call received from the LLM response. We keep a copy of it "
            "so it is easier to construct it into LLM message"
        ),
    )
    llm_response_id: str = Field(
        ...,
        description=(
            "Groups related actions from same LLM response. This helps in tracking "
            "and managing results of parallel function calling from the same LLM "
            "response."
        ),
    )
    metrics: MetricsSnapshot | None = Field(
        default=None,
        description=(
            "Snapshot of LLM metrics (token counts and costs). Only attached "
            "to the last action when multiple actions share the same LLM response."
        ),
    )

    def to_llm_message(self) -> Message:
        """Individual message - may be incomplete for multi-action batches"""
        content: list[TextContent | ImageContent] = cast(
            list[TextContent | ImageContent], self.thought
        )
        return Message(
            role="assistant",
            content=content,
            tool_calls=[self.tool_call],
            reasoning_content=self.reasoning_content,
        )

    def __str__(self) -> str:
        """Plain text string representation for ActionEvent."""
        base_str = f"{self.__class__.__name__} ({self.source})"
        thought_text = " ".join([t.text for t in self.thought])
        thought_preview = (
            thought_text[:N_CHAR_PREVIEW] + "..."
            if len(thought_text) > N_CHAR_PREVIEW
            else thought_text
        )
        action_name = self.action.__class__.__name__
        return f"{base_str}\n  Thought: {thought_preview}\n  Action: {action_name}"


class ObservationEvent(LLMConvertibleEvent):
    source: SourceType = "environment"
    observation: Observation = Field(
        ..., description="The observation (tool call) sent to LLM"
    )

    action_id: str = Field(
        ..., description="The action id that this observation is responding to"
    )
    tool_name: str = Field(
        ..., description="The tool name that this observation is responding to"
    )
    tool_call_id: str = Field(
        ..., description="The tool call id that this observation is responding to"
    )

    def to_llm_message(self) -> Message:
        return Message(
            role="tool",
            content=self.observation.agent_observation,
            name=self.tool_name,
            tool_call_id=self.tool_call_id,
        )

    def __str__(self) -> str:
        """Plain text string representation for ObservationEvent."""
        base_str = f"{self.__class__.__name__} ({self.source})"
        content_str = "".join(content_to_str(self.observation.agent_observation))
        obs_preview = (
            content_str[:N_CHAR_PREVIEW] + "..."
            if len(content_str) > N_CHAR_PREVIEW
            else content_str
        )
        return f"{base_str}\n  Tool: {self.tool_name}\n  Result: {obs_preview}"


class MessageEvent(LLMConvertibleEvent):
    """Message from either agent or user.

    This is originally the "MessageAction", but it suppose not to be tool call."""

    model_config = ConfigDict(extra="ignore")

    source: SourceType
    llm_message: Message = Field(
        ..., description="The exact LLM message for this message event"
    )
    metrics: MetricsSnapshot | None = Field(
        default=None,
        description=(
            "Snapshot of LLM metrics (token counts and costs) for this message. "
            "Only attached to messages from agent."
        ),
    )

    # context extensions stuff / microagent can go here
    activated_microagents: list[str] = Field(
        default_factory=list, description="List of activated microagent name"
    )
    extended_content: list[TextContent] = Field(
        default_factory=list, description="List of content added by agent context"
    )

    @computed_field
    def reasoning_content(self) -> str:
        return self.llm_message.reasoning_content or ""

    def to_llm_message(self) -> Message:
        msg = copy.deepcopy(self.llm_message)
        msg.content.extend(self.extended_content)
        return msg

    def __str__(self) -> str:
        """Plain text string representation for MessageEvent."""
        base_str = f"{self.__class__.__name__} ({self.source})"
        # Extract text content from the message
        text_parts = []
        message = self.to_llm_message()
        for content in message.content:
            if isinstance(content, TextContent):
                text_parts.append(content.text)
            elif isinstance(content, ImageContent):
                text_parts.append(f"[Image: {len(content.image_urls)} URLs]")

        if text_parts:
            content_preview = " ".join(text_parts)
            if len(content_preview) > N_CHAR_PREVIEW:
                content_preview = content_preview[: N_CHAR_PREVIEW - 3] + "..."
            microagent_info = (
                f" [Microagents: {', '.join(self.activated_microagents)}]"
                if self.activated_microagents
                else ""
            )
            return f"{base_str}\n  {message.role}: {content_preview}{microagent_info}"
        else:
            return f"{base_str}\n  {message.role}: [no text content]"


class UserRejectObservation(LLMConvertibleEvent):
    """Observation when user rejects an action in confirmation mode."""

    source: SourceType = "user"
    action_id: str = Field(
        ..., description="The action id that this rejection is responding to"
    )
    tool_name: str = Field(
        ..., description="The tool name that this rejection is responding to"
    )
    tool_call_id: str = Field(
        ..., description="The tool call id that this rejection is responding to"
    )
    rejection_reason: str = Field(
        default="User rejected the action",
        description="Reason for rejecting the action",
    )

    def to_llm_message(self) -> Message:
        return Message(
            role="tool",
            content=[TextContent(text=f"Action rejected: {self.rejection_reason}")],
            name=self.tool_name,
            tool_call_id=self.tool_call_id,
        )

    def __str__(self) -> str:
        """Plain text string representation for UserRejectObservation."""
        base_str = f"{self.__class__.__name__} ({self.source})"
        reason_preview = (
            self.rejection_reason[:N_CHAR_PREVIEW] + "..."
            if len(self.rejection_reason) > N_CHAR_PREVIEW
            else self.rejection_reason
        )
        return f"{base_str}\n  Tool: {self.tool_name}\n  Reason: {reason_preview}"


class AgentErrorEvent(LLMConvertibleEvent):
    """Error triggered by the agent.

    Note: This event should not contain model "thought" or "reasoning_content". It
    represents an error produced by the agent/scaffold, not model output.
    """

    source: SourceType = "agent"
    error: str = Field(..., description="The error message from the scaffold")
    metrics: MetricsSnapshot | None = Field(
        default=None,
        description=(
            "Snapshot of LLM metrics (token counts and costs). Only attached "
            "to the last action when multiple actions share the same LLM response."
        ),
    )

    def to_llm_message(self) -> Message:
        return Message(role="user", content=[TextContent(text=self.error)])

    def __str__(self) -> str:
        """Plain text string representation for AgentErrorEvent."""
        base_str = f"{self.__class__.__name__} ({self.source})"
        error_preview = (
            self.error[:N_CHAR_PREVIEW] + "..."
            if len(self.error) > N_CHAR_PREVIEW
            else self.error
        )
        return f"{base_str}\n  Error: {error_preview}"
