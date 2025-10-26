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


CommandLiteral = Literal["spawn", "delegate"]


class DelegateAction(Action):
    """Schema for delegation operations."""

    command: CommandLiteral = Field(
        description="The commands to run. Allowed options are: `spawn`, `delegate`."
    )
    ids: list[str] | None = Field(
        default=None,
        description="Required parameter of `spawn` command. "
        "List of identifiers to initialize sub-agents with.",
    )
    tasks: dict[str, str] | None = Field(
        default=None,
        description=(
            "Required parameter of `delegate` command. "
            "Dictionary mapping sub-agent identifiers to task descriptions."
        ),
    )

    @property
    def visualize(self) -> Text:
        """Return Rich Text representation of this action."""
        content = Text()
        if self.command == "spawn":
            content.append("Spawn Sub-agents:\n", style="bold green")
            if self.ids:
                content.append(f"IDs: {', '.join(self.ids)}")
        elif self.command == "delegate":
            content.append("Delegate Tasks:\n", style="bold blue")
            if self.tasks:
                for agent_id, task in self.tasks.items():
                    content.append(f"Agent {agent_id}: {task}\n")
        return content


class DelegateObservation(Observation):
    """Observation from delegation operations."""

    command: CommandLiteral = Field(
        description="The command that was executed. Either `spawn` or `delegate`."
    )
    success: bool = Field(description="Whether the operation was successful")
    message: str = Field(description="Result message from the operation")
    spawned_ids: list[str] | None = Field(
        default=None, description="List of spawned sub-agent IDs (spawn command only)"
    )
    results: list[str] | None = Field(
        default=None, description="Results from all sub-agents (delegate command only)"
    )

    @property
    def visualize(self) -> Text:
        """Return Rich Text representation of this observation."""
        content = Text()
        status = "✅" if self.success else "❌"

        if self.command == "spawn":
            content.append(f"{status} Spawn: ", style="bold")
            content.append(self.message)
        elif self.command == "delegate":
            content.append(f"{status} Delegate: ", style="bold")
            content.append(self.message)
            if self.results:
                content.append("\n\nResults:\n", style="bold")
                for i, result in enumerate(self.results, 1):
                    content.append(f"{i}. {result}\n")
        return content

    def to_text(self) -> str:
        """Convert observation to plain text."""
        if self.command == "delegate" and self.results:
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


TOOL_DESCRIPTION = (
    "Delegation tool for spawning sub-agents and delegating tasks to them.\n"
    "\n"
    "This tool provides two commands:\n"
    "\n"
    "**spawn**: Initialize sub-agents with meaningful identifiers\n"
    "- Use descriptive identifiers that make sense for your use case "
    "(e.g., 'refactoring', 'run_tests', 'research')\n"
    "- Each identifier creates a separate sub-agent conversation\n"
    '- Example: `{"command": "spawn", "ids": ["research", "implementation", '
    '"testing"]}`\n'
    "\n"
    "**delegate**: Send tasks to specific sub-agents and wait for results\n"
    "- Use a dictionary mapping sub-agent identifiers to task descriptions\n"
    "- This is a blocking operation - waits for all sub-agents to complete\n"
    "- Returns a single observation containing results from all sub-agents\n"
    '- Example: `{"command": "delegate", "tasks": {"research": '
    '"Find best practices for async code", "implementation": '
    '"Refactor the MyClass class"}}`\n'
    "\n"
    "**Important Notes:**\n"
    "- Sub-agents work in the same workspace as the main agent\n"
    "- Identifiers used in delegate must match those used in spawn\n"
    "- All operations are blocking and return comprehensive results\n"
)

delegate_tool = ToolDefinition(
    name="delegate",
    action_type=DelegateAction,
    observation_type=DelegateObservation,
    description=TOOL_DESCRIPTION,
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
        """Initialize DelegateTool with a DelegateExecutor.

        Args:
            conv_state: Conversation state (not used, but required by tool registry)
            max_children: Maximum number of concurrent sub-agents (default: 5)

        Returns:
            List containing a single delegate tool definition
        """
        # Import here to avoid circular imports
        from openhands.tools.delegate.impl import DelegateExecutor

        # Initialize the executor without parent conversation
        # (will be set on first call)
        executor = DelegateExecutor(max_children=max_children)

        # Initialize the parent Tool with the executor
        return [
            cls(
                name=delegate_tool.name,
                description=TOOL_DESCRIPTION,
                action_type=DelegateAction,
                observation_type=DelegateObservation,
                annotations=delegate_tool.annotations,
                executor=executor,
            )
        ]
