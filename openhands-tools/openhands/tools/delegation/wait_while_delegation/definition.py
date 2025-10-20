"""Wait while delegation tool definition for OpenHands agents."""

from collections.abc import Sequence

from pydantic import Field
from rich.text import Text

from openhands.sdk.llm.message import ImageContent, TextContent
from openhands.sdk.tool.tool import (
    Action,
    Observation,
    ToolAnnotations,
    ToolDefinition,
)
from openhands.tools.delegation.wait_while_delegation.impl import (
    WaitWhileDelegationExecutor,
)


class WaitWhileDelegationAction(Action):
    """Action for waiting while sub-agents complete their tasks."""

    message: str = Field(
        default="Waiting for sub-agents to complete their tasks...",
        description="Message to display while waiting",
    )

    @property
    def visualize(self) -> Text:
        """Return Rich Text representation of this action."""
        content = Text()
        content.append("Wait while delegation:\n", style="bold blue")
        content.append(self.message)
        return content


class WaitWhileDelegationObservation(Observation):
    """Observation from wait while delegation operation."""

    content: Sequence[TextContent | ImageContent] = Field(
        default_factory=list, description="Content from the wait operation"
    )

    @property
    def visualize(self) -> Text:
        """Return Rich Text representation of this observation."""
        content = Text()
        content.append("⏳ ", style="bold yellow")
        content.append("Main agent paused - waiting for sub-agents")
        return content

    def to_text(self) -> str:
        """Convert observation to plain text."""
        text_parts = []
        for content in self.content:
            if isinstance(content, TextContent):
                text_parts.append(content.text)
            elif isinstance(content, ImageContent):
                text_parts.append(f"[Image: {content.image_url}]")
        return "\n".join(text_parts) if text_parts else "Waiting for sub-agents..."

    def to_rich_text(self) -> Text:
        """Convert observation to rich text representation."""
        return Text(self.to_text())

    def to_llm_content(self) -> Sequence[TextContent | ImageContent]:
        """Get the observation content to show to the agent."""
        return self.content


WAIT_WHILE_DELEGATION_TOOL_DESCRIPTION = """Pause the main agent's execution
while waiting for sub-agents to complete their delegated tasks.

This tool allows the main agent to pause and wait for sub-agents to finish their work:

**Usage:**
- Use this tool after spawning sub-agents to pause the main agent
- The main agent will wait until sub-agents send their results back
- Sub-agents will continue working independently and send messages when complete
- The conversation will resume when sub-agents provide their results

**Important Notes:**
- This tool sets the conversation status to FINISHED, pausing the main agent
- Sub-agents continue working in parallel and will send results back
- Use this instead of continuing to generate responses while waiting
- The main agent will resume when it receives messages from sub-agents

**Example:**
After spawning sub-agents with delegate tool, use this to wait:
`{"message": "Waiting for code analysis from both sub-agents..."}`
"""

WaitWhileDelegationTool = ToolDefinition(
    name="wait_while_delegation",
    action_type=WaitWhileDelegationAction,
    observation_type=WaitWhileDelegationObservation,
    description=WAIT_WHILE_DELEGATION_TOOL_DESCRIPTION,
    executor=WaitWhileDelegationExecutor(),
    annotations=ToolAnnotations(
        title="wait_while_delegation",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
