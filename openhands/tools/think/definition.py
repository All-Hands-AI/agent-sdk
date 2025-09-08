"""Think tool definition for agent-sdk."""

from pydantic import Field

from openhands.sdk import ImageContent, TextContent
from openhands.sdk.tool import (
    ActionBase,
    ObservationBase,
    Tool,
    ToolAnnotations,
    ToolExecutor,
)


class ThinkAction(ActionBase):
    """Action for logging a thought without making any changes."""

    thought: str = Field(description="The thought to log.")


class ThinkObservation(ObservationBase):
    """Observation returned after logging a thought."""

    content: str = Field(
        default="Your thought has been logged.", description="Confirmation message."
    )

    @property
    def agent_observation(self) -> list[TextContent | ImageContent]:
        return [TextContent(text=self.content)]


THINK_DESCRIPTION = """Use the tool to think about something. It will not obtain new information or make any changes to the repository, but just log the thought. Use it when complex reasoning or brainstorming is needed.

Common use cases:
1. When exploring a repository and discovering the source of a bug, call this tool to brainstorm several unique ways of fixing the bug, and assess which change(s) are likely to be simplest and most effective.
2. After receiving test results, use this tool to brainstorm ways to fix failing tests.
3. When planning a complex refactoring, use this tool to outline different approaches and their tradeoffs.
4. When designing a new feature, use this tool to think through architecture decisions and implementation details.
5. When debugging a complex issue, use this tool to organize your thoughts and hypotheses.

The tool simply logs your thought process for better transparency and does not execute any code or make changes."""  # noqa: E501


class ThinkExecutor(ToolExecutor):
    def __call__(self, _: ThinkAction) -> ThinkObservation:
        return ThinkObservation()


think_tool = Tool(
    name="think",
    description=THINK_DESCRIPTION,
    input_schema=ThinkAction,
    output_schema=ThinkObservation,
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)


class ThinkTool(Tool[ThinkAction, ThinkObservation]):
    """A Tool subclass that automatically initializes a ThinkExecutor."""

    def __init__(self):
        """Initialize ThinkTool with a ThinkExecutor."""
        executor = ThinkExecutor()

        # Initialize the parent Tool with the executor
        super().__init__(
            name=think_tool.name,
            description=THINK_DESCRIPTION,
            input_schema=ThinkAction,
            output_schema=ThinkObservation,
            annotations=think_tool.annotations,
            executor=executor,
        )
