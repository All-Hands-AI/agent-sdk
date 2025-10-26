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


class SpawnAction(Action):
    """Action for spawning sub-agents with specific IDs."""

    ids: list[str] = Field(
        description="List of IDs to initialize sub-conversations/agents with"
    )

    @property
    def visualize(self) -> Text:
        """Return Rich Text representation of this action."""
        content = Text()
        content.append("Spawn Sub-agents:\n", style="bold green")
        content.append(f"IDs: {', '.join(self.ids)}")
        return content


class DelegateAction(Action):
    """Action for delegating tasks to sub-agents and waiting for results."""

    tasks: list[str] = Field(
        description="List of task descriptions to delegate to sub-agents"
    )

    @property
    def visualize(self) -> Text:
        """Return Rich Text representation of this action."""
        content = Text()
        content.append("Delegate Tasks:\n", style="bold blue")
        for i, task in enumerate(self.tasks, 1):
            content.append(f"Task {i}: {task}\n")
        return content


class SpawnObservation(Observation):
    """Observation from spawn operations."""

    success: bool = Field(description="Whether the spawn action was successful")
    spawned_ids: list[str] = Field(
        default_factory=list, description="List of spawned sub-agent IDs"
    )
    message: str = Field(description="Result message from the action")

    @property
    def visualize(self) -> Text:
        """Return Rich Text representation of this observation."""
        content = Text()
        status = "✅" if self.success else "❌"
        content.append(f"{status} Spawn: ", style="bold")
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


class DelegateObservation(Observation):
    """Observation from delegation operations."""

    success: bool = Field(description="Whether the delegation was successful")
    results: list[str] = Field(
        default_factory=list, description="Results from all sub-agents"
    )
    message: str = Field(description="Summary message from the delegation")

    @property
    def visualize(self) -> Text:
        """Return Rich Text representation of this observation."""
        content = Text()
        status = "✅" if self.success else "❌"
        content.append(f"{status} Delegate: ", style="bold")
        content.append(self.message)
        if self.results:
            content.append("\n\nResults:\n", style="bold")
            for i, result in enumerate(self.results, 1):
                content.append(f"{i}. {result}\n")
        return content

    def to_text(self) -> str:
        """Convert observation to plain text."""
        if self.results:
            results_text = "\n".join(
                f"{i}. {result}" for i, result in enumerate(self.results, 1)
            )
            return f"{self.message}\n\nResults:\n{results_text}"
        return self.message

    def to_rich_text(self) -> Text:
        """Convert observation to rich text representation."""
        return Text(self.to_text())

    @property
    def to_llm_content(self) -> Sequence[TextContent | ImageContent]:
        """Get the observation content to show to the agent."""
        return [TextContent(text=self.to_text())]


SPAWN_TOOL_DESCRIPTION = (
    "Spawn sub-agents with specific IDs for later task delegation.\n"
    "\n"
    "This tool initializes sub-conversations/agents with the provided IDs.\n"
    "\n"
    "**Usage:**\n"
    "- Use this to create sub-agents before delegating tasks to them\n"
    "- Each ID will create a separate sub-agent conversation"
)

DELEGATE_TOOL_DESCRIPTION = (
    "Delegate tasks to sub-agents and wait for results.\n"
    "\n"
    "This tool sends tasks to sub-agents, runs them in parallel, "
    "and waits for all to complete.\n"
    "\n"
    "**Important Notes:**\n"
    "- Sub-agents work in the same workspace as you, the main agent\n"
    "- This is a blocking operation - it waits for all sub-agents to complete\n"
    "- Returns a single observation containing results from all sub-agents"
)

spawn_tool = ToolDefinition(
    name="spawn",
    action_type=SpawnAction,
    observation_type=SpawnObservation,
    description=SPAWN_TOOL_DESCRIPTION,
    annotations=ToolAnnotations(
        title="spawn",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
)

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


class SpawnTool(ToolDefinition[SpawnAction, SpawnObservation]):
    """Tool definition for spawning sub-agents."""

    pass


class DelegateTool(ToolDefinition[DelegateAction, DelegateObservation]):
    """Tool definition for delegating tasks to sub-agents."""

    pass


def create_delegation_tools(
    conv_state: "ConversationState",  # noqa: ARG001
    max_children: int = 5,
) -> Sequence[ToolDefinition]:
    """Create both spawn and delegate tools with shared executor.

    Args:
        conv_state: Conversation state (not used, but required by tool registry)
        max_children: Maximum number of concurrent sub-agents (default: 5)

    Returns:
        List containing both spawn and delegate tool definitions
    """
    # Import here to avoid circular imports
    from openhands.tools.delegate.impl import DelegateExecutor

    # Initialize the executor without parent conversation
    # (will be set on first call)
    executor = DelegateExecutor(max_children=max_children)

    # Create both tools with the same executor
    spawn_tool_instance = SpawnTool(
        name=spawn_tool.name,
        description=SPAWN_TOOL_DESCRIPTION,
        action_type=SpawnAction,
        observation_type=SpawnObservation,
        annotations=spawn_tool.annotations,
        executor=executor,
    )

    delegate_tool_instance = DelegateTool(
        name=delegate_tool.name,
        description=DELEGATE_TOOL_DESCRIPTION,
        action_type=DelegateAction,
        observation_type=DelegateObservation,
        annotations=delegate_tool.annotations,
        executor=executor,
    )

    return [spawn_tool_instance, delegate_tool_instance]


# For backward compatibility, keep the old DelegateTool.create method
def _create_delegate_tools(cls, conv_state, max_children=5):  # noqa: ARG001
    return create_delegation_tools(conv_state, max_children)


DelegateTool.create = classmethod(_create_delegate_tools)
