"""Delegate tool definitions for OpenHands agents."""

from collections.abc import Sequence
from typing import TYPE_CHECKING

from pydantic import Field
from rich.text import Text

from openhands.sdk.llm.message import ImageContent, TextContent
from openhands.sdk.tool.tool import (
    Action,
    Observation,
    ToolAnnotations,
    ToolDefinition,
)


if TYPE_CHECKING:
    from openhands.sdk.conversation.state import ConversationState


class DelegateAction(Action):
    """Action for delegating tasks to sub-agents."""

    task: str = Field(description="The task description to delegate to a sub-agent")

    @property
    def visualize(self) -> Text:
        """Return Rich Text representation of this action."""
        content = Text()
        content.append("Delegate Task:\n", style="bold blue")
        content.append(f"Task: {self.task}")
        return content


class DelegateObservation(Observation):
    """Observation from delegation operations."""

    success: bool = Field(description="Whether the action was successful")
    sub_conversation_id: str | None = Field(
        default=None, description="ID of the sub-conversation created"
    )
    message: str = Field(description="Result message from the action")

    @property
    def visualize(self) -> Text:
        """Return Rich Text representation of this observation."""
        content = Text()
        status = "✅" if self.success else "❌"
        content.append(f"{status} Delegate: ", style="bold")
        content.append(self.message)
        return content

    def to_text(self) -> str:
        """Convert observation to plain text."""
        return self.message

    def to_rich_text(self) -> Text:
        """Convert observation to rich text representation."""
        return Text(self.to_text())

    @property
    def to_llm_content(self) -> Sequence[TextContent | ImageContent]:
        """Get the observation content to show to the agent."""
        return [TextContent(text=self.message)]


DELEGATE_TOOL_DESCRIPTION = """Delegate tasks to sub-agents for parallel processing.

This tool allows the main agent to delegate tasks to sub-agents that run independently.


**Important Notes:**
- Sub-agents work in the same workspace as the main agent
- Sub-agents will send back their findings to the main agent upon completion
- After delegating tasks to sub-agents, use FinishAction to pause and wait for
    their results when necessary.
"""


delegate_tool = ToolDefinition(
    name="delegate",
    action_type=DelegateAction,
    observation_type=DelegateObservation,
    description=DELEGATE_TOOL_DESCRIPTION,
    annotations=ToolAnnotations(
        title="delegate",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
)


class DelegateTool(ToolDefinition[DelegateAction, DelegateObservation]):
    """A ToolDefinition subclass that automatically initializes a DelegateExecutor."""

    @classmethod
    def create(
        cls,
        conv_state: "ConversationState",  # noqa: ARG003
        max_children: int = 5,
    ) -> Sequence["DelegateTool"]:
        """Initialize DelegateTool with executor parameters.

        The parent conversation will be injected later when the tool is first used.

        Args:
            conv_state: Conversation state (not used, but required by tool registry)
            max_children: Maximum number of concurrent sub-agents (default: 10)
        """
        # Import here to avoid circular imports
        from openhands.tools.delegate.impl import DelegateExecutor

        # Initialize the executor without parent conversation
        # (will be set on first call)
        executor = DelegateExecutor(max_children=max_children)

        # Initialize the parent ToolDefinition with the executor
        return [
            cls(
                name=delegate_tool.name,
                description=DELEGATE_TOOL_DESCRIPTION,
                action_type=DelegateAction,
                observation_type=DelegateObservation,
                annotations=delegate_tool.annotations,
                executor=executor,
            )
        ]
