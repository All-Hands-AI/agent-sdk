"""Delegation tool definitions for OpenHands agents."""

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
from openhands.tools.delegation.impl import DelegateExecutor


class DelegateAction(Action):
    """Action for delegating tasks to sub-agents."""

    operation: Literal["spawn", "send", "status", "close"] = Field(
        description="The delegation operation to perform"
    )
    task: str | None = Field(
        default=None, description="Task description for spawn operation"
    )
    sub_conversation_id: str | None = Field(
        default=None,
        description="ID of the sub-conversation for send/status/close operations",
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
        elif self.operation in ["status", "close"] and self.sub_conversation_id:
            content.append(f"Sub-agent: {self.sub_conversation_id}")

        return content


class DelegateObservation(Observation):
    """Observation from delegation operations."""

    sub_conversation_id: str | None = Field(
        default=None, description="ID of the sub-conversation"
    )
    status: str = Field(description="Status of the operation")
    result: str | None = Field(
        default=None, description="Result or additional information"
    )
    message: str = Field(description="Human-readable message about the operation")

    @property
    def to_llm_content(self) -> Sequence[TextContent | ImageContent]:
        content_parts = [f"Status: {self.status}"]

        if self.sub_conversation_id:
            content_parts.append(f"Sub-agent ID: {self.sub_conversation_id}")

        if self.result:
            content_parts.append(f"Result: {self.result}")

        content_parts.append(f"Message: {self.message}")

        return [TextContent(text="\n".join(content_parts))]

    @property
    def visualize(self) -> Text:
        """Return Rich Text representation of this observation."""
        content = Text()
        content.append(f"Delegation {self.status}:\n", style="bold green")
        content.append(self.message)

        if self.result:
            content.append(f"\nResult: {self.result}")

        return content


TOOL_DESCRIPTION = """Delegate tasks to sub-agents for parallel processing.

This tool allows the main agent to spawn sub-agents, send them messages,
check their status, and close them when done.

Operations:
- spawn: Create a new sub-agent with a specific task
- send: Send a message to an existing sub-agent
- status: Check the status of a sub-agent
- close: Close a sub-agent and clean up resources

The main agent should use FinishAction to pause itself when waiting
for sub-agents to complete their work. Sub-agents will send their
results back to the main agent, which will reactivate it.

Example workflow:
1. spawn: Create sub-agent with task "Analyze sales data"
2. spawn: Create another sub-agent with task "Analyze customer data"
3. finish: "Waiting for sub-agents to complete analysis..."
4. (Sub-agents work and send results back)
5. close: Close both sub-agents
6. Process and combine results
"""


DelegationTool = ToolDefinition(
    name="delegate",
    action_type=DelegateAction,
    observation_type=DelegateObservation,
    description=TOOL_DESCRIPTION,
    executor=DelegateExecutor(),
    annotations=ToolAnnotations(
        title="delegate",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
)
