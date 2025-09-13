"""Finish tool for signaling task completion."""

from collections.abc import Sequence

from pydantic import Field
from rich.text import Text

from openhands.sdk.llm.message import ImageContent, TextContent
from openhands.sdk.tool.tool import (
    ActionBase,
    ObservationBase,
    Tool,
    ToolAnnotations,
    ToolExecutor,
)


class FinishAction(ActionBase):
    """Action for finishing a task or conversation."""

    message: str = Field(description="Final message to send to the user.")

    @property
    def visualize(self) -> Text:
        """Return Rich Text representation of this action."""
        content = Text()
        content.append("Finish with message:\n", style="bold blue")
        content.append(self.message)
        return content


class FinishObservation(ObservationBase):
    """Observation for finish action."""

    message: str = Field(description="Final message sent to the user.")

    @property
    def agent_observation(self) -> Sequence[TextContent | ImageContent]:
        """Return agent observation content."""
        return [TextContent(text=self.message)]

    @property
    def visualize(self) -> Text:
        """Return Rich Text representation - empty since action shows the message."""
        # Don't duplicate the finish message display - action already shows it
        return Text()


TOOL_DESCRIPTION = """Signals the completion of the current task or conversation.

Use this tool when:
- You have successfully completed the user's requested task
- You cannot proceed further due to technical limitations or missing information

The message should include:
- A clear summary of actions taken and their results
- Any next steps for the user
- Explanation if you're unable to complete the task
- Any follow-up questions if more information is needed
"""


class FinishExecutor(ToolExecutor):
    """Executor for finish tool."""

    def __call__(self, action: FinishAction) -> FinishObservation:
        """Execute finish action."""
        return FinishObservation(message=action.message)


FinishTool = Tool(
    name="finish",
    action_type=FinishAction,
    observation_type=FinishObservation,
    description=TOOL_DESCRIPTION,
    executor=FinishExecutor(),
    annotations=ToolAnnotations(
        title="finish",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
