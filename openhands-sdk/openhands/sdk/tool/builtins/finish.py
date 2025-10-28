from typing import TYPE_CHECKING

from pydantic import Field
from rich.text import Text

from openhands.sdk.tool.tool import (
    Action,
    Observation,
    ToolAnnotations,
    ToolDefinition,
    ToolExecutor,
)


if TYPE_CHECKING:
    from openhands.sdk.conversation.base import BaseConversation


class FinishAction(Action):
    message: str = Field(description="Final message to send to the user.")

    @property
    def visualize(self) -> Text:
        """Return Rich Text representation of this action."""
        content = Text()
        content.append("Finish with message:\n", style="bold blue")
        content.append(self.message)
        return content


class FinishObservation(Observation):
    """
    Observation returned after finishing a task.
    The FinishAction itself contains the message sent to the user so no
    extra fields are needed here.
    """


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
    def __call__(
        self,
        action: FinishAction,
        conversation: "BaseConversation | None" = None,  # noqa: ARG002
    ) -> FinishObservation:
        return FinishObservation(output=action.message)


FinishTool = ToolDefinition(
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
