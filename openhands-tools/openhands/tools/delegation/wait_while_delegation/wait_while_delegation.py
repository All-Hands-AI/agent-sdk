from collections.abc import Sequence

from pydantic import Field
from rich.text import Text

from openhands.sdk.llm.message import ImageContent, TextContent
from openhands.sdk.tool.tool import (
    Action,
    Observation,
    ToolAnnotations,
    ToolDefinition,
    ToolExecutor,
)


class WaitWhileDelegationAction(Action):
    message: str = Field(description="Message explaining what the agent is waiting for")

    @property
    def visualize(self) -> Text:
        """Return Rich Text representation of this action."""
        content = Text()
        content.append("Waiting for sub-agents:\n", style="bold yellow")
        content.append(self.message)
        return content


class WaitWhileDelegationObservation(Observation):
    message: str = Field(description="Confirmation message about waiting state")

    @property
    def to_llm_content(self) -> Sequence[TextContent | ImageContent]:
        return [TextContent(text=self.message)]

    @property
    def visualize(self) -> Text:
        """Return Rich Text representation - empty since action shows the message."""
        return Text()


TOOL_DESCRIPTION = (
    "Pause the main agent's execution while waiting for sub-agents to complete "
    "their delegated tasks.\n\n"
    "Use this tool when:\n"
    "- You have spawned sub-agents and need to wait for their results\n"
    "- Sub-agents are working independently and will send results back\n"
    "- You want to avoid generating responses while waiting\n\n"
    "The message should explain what you're waiting for from the sub-agents."
)


class WaitWhileDelegationExecutor(ToolExecutor):
    def __call__(
        self, action: WaitWhileDelegationAction
    ) -> WaitWhileDelegationObservation:
        return WaitWhileDelegationObservation(message=action.message)


WaitWhileDelegationTool = ToolDefinition(
    name="wait_while_delegation",
    action_type=WaitWhileDelegationAction,
    observation_type=WaitWhileDelegationObservation,
    description=TOOL_DESCRIPTION,
    executor=WaitWhileDelegationExecutor(),
    annotations=ToolAnnotations(
        title="wait_while_delegation",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
