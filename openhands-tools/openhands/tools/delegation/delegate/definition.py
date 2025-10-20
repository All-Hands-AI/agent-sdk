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
from openhands.tools.delegation.delegate.impl import DelegateExecutor


class DelegateAction(Action):
    """Action for delegating tasks to sub-agents."""

    operation: Literal["spawn", "send", "close"] = Field(
        description="The delegation operation to perform"
    )
    task: str | None = Field(
        default=None, description="Task description for spawn operation"
    )
    sub_conversation_id: str | None = Field(
        default=None,
        description="ID of the sub-conversation for send/close operations",
    )
    message: str | None = Field(
        default=None, description="Message to send to sub-agent (for send operation)"
    )

    @property
    def visualize(self) -> Text:
        """Return Rich Text representation of this action."""
        content = Text()
        content.append(f"Delegate {self.operation}:\n", style="bold blue")

        if self.operation == "spawn" and self.task:
            content.append(f"Task: {self.task}")
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
    content: Sequence[TextContent | ImageContent] = Field(
        default_factory=list, description="Additional content from the operation"
    )

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
        text_parts = [self.message]
        for content in self.content:
            if isinstance(content, TextContent):
                text_parts.append(content.text)
            elif isinstance(content, ImageContent):
                text_parts.append(f"[Image: {content.image_url}]")
        return "\n".join(text_parts) if text_parts else self.message

    def to_rich_text(self) -> Text:
        """Convert observation to rich text representation."""
        return Text(self.to_text())

    def to_llm_content(self) -> Sequence[TextContent | ImageContent]:
        """Get the observation content to show to the agent."""
        base_content = [TextContent(text=self.message)]
        return base_content + list(self.content)


DELEGATE_TOOL_DESCRIPTION = """Delegate tasks to sub-agents for parallel processing.

This tool allows the main agent to spawn, communicate with, and manage sub-agents:

**Operations:**
- `spawn`: Create a new sub-agent with a specific task
- `send`: Send a message to an existing sub-agent
- `close`: Terminate a sub-agent and clean up resources

**Usage Examples:**
1. Spawn a sub-agent: `{"operation": "spawn", "task": "Analyze the code for bugs"}`
2. Send message: `{"operation": "send", "sub_conversation_id": "sub_123", `
   `"message": "Please focus on security issues"}`
3. Close sub-agent: `{"operation": "close", "sub_conversation_id": "sub_123"}`

**Important Notes:**
- Sub-agents work in the same workspace as the main agent
- Sub-agents can only communicate with the main agent (no sub-to-sub communication)
- Use spawn to create specialized agents for different aspects of complex tasks
- Always close sub-agents when their work is complete to free resources
"""

DelegationTool = ToolDefinition(
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
