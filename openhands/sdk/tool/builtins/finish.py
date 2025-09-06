from pydantic import Field

from openhands.sdk.llm.message import ImageContent, TextContent
from openhands.sdk.tool.tool import (
    ActionBase,
    ObservationBase,
    Tool,
    ToolAnnotations,
    ToolExecutor,
)


class FinishAction(ActionBase):
    message: str = Field(description="Final message to send to the user.")


class FinishObservation(ObservationBase):
    message: str = Field(description="Final message sent to the user.")

    @property
    def agent_observation(self) -> list[TextContent | ImageContent]:
        return [TextContent(text=self.message)]


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
    def __call__(self, action: FinishAction) -> FinishObservation:
        return FinishObservation(message=action.message)


FinishTool = Tool(
    name="finish",
    input_schema=FinishAction,
    output_schema=FinishObservation,
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
