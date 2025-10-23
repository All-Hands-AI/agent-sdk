"""Delegate tool definitions for OpenHands agents."""

from collections.abc import Sequence
from typing import Literal

from pydantic import Field
from rich.text import Text

from openhands.sdk.llm.message import ImageContent, TextContent
from openhands.sdk.tool.tool import (
    Action,
    Observation,
    ToolAnnotations,
    ToolDefinition,
)


class DelegateAction(Action):
    """Action for delegating tasks to sub-agents."""

    operation: Literal["spawn", "send", "close"] = Field(
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
        description=(
            "ID of the sub-conversation (only supported for send/close operations)"
        ),
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
        elif self.operation == "close" and self.sub_conversation_id:
            content.append(f"Sub-agent: {self.sub_conversation_id}")

        return content


class DelegateObservation(Observation):
    """Observation from delegation operations."""

    operation: Literal["spawn", "send", "close"] = Field(
        description="The delegation operation that was performed"
    )
    success: bool = Field(description="Whether the operation was successful")
    sub_conversation_id: str | None = Field(
        default=None, description="ID of the sub-conversation (for spawn/send/close)"
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

This tool allows the main agent to spawn, communicate with, and manage sub-agents:

**Operations:**
- `spawn`: Create a new sub-agent with a specific task (use message field for task)
- `send`: Send a message to an existing sub-agent (requires sub_conversation_id)
- `close`: Terminate a sub-agent and clean up resources (requires sub_conversation_id)

**Usage Examples:**
1. Spawn a sub-agent: `{"operation": "spawn", "message": "Analyze the code for bugs"}`
2. Send message: `{"operation": "send", "sub_conversation_id": "sub_123", `
   `"message": "Please focus on security issues"}`
3. Close sub-agent: `{"operation": "close", "sub_conversation_id": "sub_123"}`

**Important Notes:**
- Sub-agents work in the same workspace as the main agent
- Sub-agents can only communicate with the main agent (no sub-to-sub communication)
- Use spawn to create specialized agents for different aspects of complex tasks
- Always close sub-agents when their work is complete to free resources
- sub_conversation_id is only supported for send/close operations
"""


def _get_delegation_tool():
    """Lazy initialization of DelegationTool to avoid circular imports."""
    from openhands.tools.delegate.impl import DelegateExecutor

    return ToolDefinition(
        name="delegate",
        action_type=DelegateAction,
        observation_type=DelegateObservation,
        description=DELEGATE_TOOL_DESCRIPTION,
        executor=DelegateExecutor(),
        annotations=ToolAnnotations(
            title="delegate",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=True,
        ),
    )


DelegationTool = _get_delegation_tool()
