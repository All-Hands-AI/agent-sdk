"""Browser-use tool implementation for web automation."""

from pydantic import Field

from openhands.sdk.llm import ImageContent, TextContent
from openhands.sdk.tool import ActionBase, ObservationBase, Tool, ToolAnnotations
from openhands.sdk.utils import maybe_truncate


# Maximum output size for browser observations
MAX_BROWSER_OUTPUT_SIZE = 50000


class BrowserObservation(ObservationBase):
    """Base observation for browser operations."""

    output: str = Field(description="The output message from the browser operation")
    error: str | None = Field(default=None, description="Error message if any")

    @property
    def agent_observation(self) -> list[TextContent | ImageContent]:
        if self.error:
            return [TextContent(text=f"Error: {self.error}")]
        return [TextContent(text=maybe_truncate(self.output, MAX_BROWSER_OUTPUT_SIZE))]


# ============================================
# `go_to_url`
# ============================================
class BrowserNavigateAction(ActionBase):
    """Schema for browser navigation."""

    url: str = Field(description="The URL to navigate to")
    new_tab: bool = Field(
        default=False, description="Whether to open in a new tab. Default to False"
    )


class BrowserNavigateObservation(BrowserObservation):
    """Observation for browser navigation."""

    pass


BROWSER_NAVIGATE_DESCRIPTION = """Navigate to a URL in the browser"""

browser_navigate_tool = Tool(
    name="browser_navigate",
    action_type=BrowserNavigateAction,
    observation_type=BrowserNavigateObservation,
    description=BROWSER_NAVIGATE_DESCRIPTION,
    annotations=ToolAnnotations(
        title="browser_navigate",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
)


class BrowserNavigateTool(Tool[BrowserNavigateAction, BrowserNavigateObservation]):
    """Tool for browser navigation."""

    def __init__(self, **config):
        from openhands.tools.browser_use.impl import BrowserToolExecutor

        executor = BrowserToolExecutor(**config)
        super().__init__(
            name=browser_navigate_tool.name,
            description=BROWSER_NAVIGATE_DESCRIPTION,
            action_type=BrowserNavigateAction,
            observation_type=BrowserNavigateObservation,
            annotations=browser_navigate_tool.annotations,
            executor=executor,
        )


# ============================================
# `browser_get_state`
# ============================================
class BrowserGetStateAction(ActionBase):
    """Schema for getting browser state."""

    include_screenshot: bool = Field(
        default=False,
        description="Whether to include a screenshot of the current page. Default to False",  # noqa: E501
    )


class BrowserGetStateObservation(BrowserObservation):
    """Observation for getting browser state."""

    pass


BROWSER_GET_STATE_DESCRIPTION = (
    """Get the current state of the page including all interactive elements"""
)

browser_get_state_tool = Tool(
    name="browser_get_state",
    action_type=BrowserGetStateAction,
    observation_type=BrowserGetStateObservation,
    description=BROWSER_GET_STATE_DESCRIPTION,
    annotations=ToolAnnotations(
        title="browser_get_state",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)


class BrowserGetStateTool(Tool[BrowserGetStateAction, BrowserGetStateObservation]):
    """Tool for getting browser state."""

    def __init__(self, **config):
        from openhands.tools.browser_use.impl import BrowserToolExecutor

        executor = BrowserToolExecutor(**config)
        super().__init__(
            name=browser_get_state_tool.name,
            description=BROWSER_GET_STATE_DESCRIPTION,
            action_type=BrowserGetStateAction,
            observation_type=BrowserGetStateObservation,
            annotations=browser_get_state_tool.annotations,
            executor=executor,
        )
