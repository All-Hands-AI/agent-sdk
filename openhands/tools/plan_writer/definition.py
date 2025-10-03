"""Plan writer tool implementation."""

from collections.abc import Sequence
from typing import TYPE_CHECKING, Literal

from pydantic import Field


if TYPE_CHECKING:
    from openhands.sdk.conversation.state import ConversationState

from openhands.sdk.llm import ImageContent, TextContent
from openhands.sdk.tool import (
    Action,
    Observation,
    ToolAnnotations,
    ToolDefinition,
)


class PlanWriterAction(Action):
    """Schema for plan writing operations."""

    command: Literal["write", "append"] = Field(
        description="The command to run. 'write' creates or overwrites the plan file, "
        "'append' adds content to the existing plan file."
    )
    content: str = Field(
        description="The markdown content to write or append to the plan file."
    )
    filename: str = Field(
        default="PLAN.md",
        description="The filename for the plan (default: PLAN.md). Must end with .md",
    )


class PlanWriterObservation(Observation):
    """Observation from plan writing operations."""

    command: Literal["write", "append"] = Field(
        description="The command that was executed."
    )
    output: str = Field(default="", description="Success message or error details.")
    filename: str | None = Field(
        default=None, description="The plan file that was written."
    )
    error: str | None = Field(default=None, description="Error message if any.")

    @property
    def to_llm_content(self) -> Sequence[TextContent | ImageContent]:
        if self.error:
            return [TextContent(text=self.error)]
        return [TextContent(text=self.output)]


TOOL_DESCRIPTION = """Plan writer tool for creating and updating markdown plan files.
This tool allows planning agents to document their analysis and create structured plans.

* Use 'write' command to create or overwrite a plan file with new content
* Use 'append' command to add additional content to an existing plan file
* Plans are written in markdown format for better readability
* Default filename is PLAN.md but can be customized
* Only allows writing to .md files for safety

This tool is specifically designed for planning agents to output their structured
analysis and implementation plans in a format that can be easily read by other
agents or humans.

Examples:
- write "# Project Analysis\n\n## Overview\n..." - Create new plan
- append "\n## Next Steps\n- Step 1\n- Step 2" - Add to existing plan
"""


plan_writer_tool = ToolDefinition(
    name="plan_writer",
    action_type=PlanWriterAction,
    description=TOOL_DESCRIPTION,
    annotations=ToolAnnotations(
        title="plan_writer",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=False,
    ),
)


class PlanWriterTool(ToolDefinition[PlanWriterAction, PlanWriterObservation]):
    """A plan writer tool for planning agents."""

    @classmethod
    def create(
        cls,
        conv_state: "ConversationState",
    ) -> Sequence["PlanWriterTool"]:
        """Initialize PlanWriterTool with a PlanWriterExecutor.

        Args:
            conv_state: Conversation state to get working directory from.
        """
        # Import here to avoid circular imports
        from openhands.tools.plan_writer.impl import PlanWriterExecutor

        # Initialize the executor
        executor = PlanWriterExecutor(workspace_root=conv_state.workspace.working_dir)

        # Add working directory information to the tool description
        working_dir = conv_state.workspace.working_dir
        enhanced_description = (
            f"{TOOL_DESCRIPTION}\n\n"
            f"Plans will be written to: {working_dir}\n"
            f"The plan file will be accessible to other agents in the workflow."
        )

        # Initialize the parent Tool with the executor
        return [
            cls(
                name=plan_writer_tool.name,
                description=enhanced_description,
                action_type=PlanWriterAction,
                observation_type=PlanWriterObservation,
                annotations=plan_writer_tool.annotations,
                executor=executor,
            )
        ]
