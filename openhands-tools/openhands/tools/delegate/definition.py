"""Delegate tool definitions for OpenHands agents."""

from collections.abc import Sequence
from typing import TYPE_CHECKING, Literal

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

    operation: Literal["spawn", "send"] = Field(
        description="The delegation operation to perform"
    )
    message: str | None = Field(
        default=None,
        description=(
            "Message content: for spawn operation, this is the task description; "
            "for send operation, this is the message to send to sub-agent"
        ),
    )
    sub_conversation_id: str | None = Field(
        default=None,
        description="ID of the sub-conversation (only supported for send operation)",
    )

    @property
    def visualize(self) -> Text:
        """Return Rich Text representation of this action."""
        content = Text()
        content.append(f"Delegate {self.operation}:\n", style="bold blue")

        if self.operation == "spawn" and self.message:
            content.append(f"Task: {self.message}")
        elif self.operation == "send" and self.message and self.sub_conversation_id:
            content.append(f"To {self.sub_conversation_id}: {self.message}")

        return content


class DelegateObservation(Observation):
    """Observation from delegation operations."""

    operation: Literal["spawn", "send"] = Field(
        description="The delegation operation that was performed"
    )
    success: bool = Field(description="Whether the operation was successful")
    sub_conversation_id: str | None = Field(
        default=None, description="ID of the sub-conversation (for spawn/send)"
    )
    message: str = Field(description="Result message from the operation")

    @property
    def visualize(self) -> Text:
        """Return Rich Text representation of this observation."""
        content = Text()
        status = "✅" if self.success else "❌"
        content.append(f"{status} Delegate {self.operation}: ", style="bold")
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

This tool allows the main agent to spawn and communicate with sub-agents:

**Operations:**
- `spawn`: Create a new sub-agent and send it a message (using the message field)
- `send`: Send a message to an existing sub-agent (requires sub_conversation_id)

**Usage Examples:**
1. Spawn a sub-agent: `{"operation": "spawn", "message": "Analyze the code for bugs"}`
2. Send message: `{"operation": "send", "sub_conversation_id": "sub_123", `
   `"message": "Please focus on security issues"}`

**Important Notes:**
- Sub-agents work in the same workspace as the main agent
- Sub-agents can only communicate with the main agent (no sub-to-sub communication)
- Use spawn to create specialized agents for different aspects of complex tasks
- Sub-agents are automatically cleaned up when they complete their tasks
- sub_conversation_id is only supported for send operations
- After spawning sub-agents, use FinishAction to pause and wait for
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
        max_children: int = 10,
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
