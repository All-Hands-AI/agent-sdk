"""Browser-use tool implementation for web automation."""

from pydantic import Field

from openhands.sdk.llm import ImageContent, TextContent
from openhands.sdk.tool import ActionBase, ObservationBase, Tool, ToolAnnotations
from openhands.sdk.utils import maybe_truncate
from openhands.tools.browser_use.impl import BrowserToolExecutor


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
        default=False, description="Whether to open in a new tab. Default: False"
    )


BROWSER_NAVIGATE_DESCRIPTION = """Navigate to a URL in the browser"""

browser_navigate_tool = Tool(
    name="browser_navigate",
    action_type=BrowserNavigateAction,
    observation_type=BrowserObservation,
    description=BROWSER_NAVIGATE_DESCRIPTION,
    annotations=ToolAnnotations(
        title="browser_navigate",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
)


class BrowserNavigateTool(Tool[BrowserNavigateAction, BrowserObservation]):
    """Tool for browser navigation."""

    @classmethod
    def create(cls, executor: BrowserToolExecutor):
        return cls(
            name=browser_navigate_tool.name,
            description=BROWSER_NAVIGATE_DESCRIPTION,
            action_type=BrowserNavigateAction,
            observation_type=BrowserObservation,
            annotations=browser_navigate_tool.annotations,
            executor=executor,
        )


# ============================================
# `browser_click`
# ============================================
class BrowserClickAction(ActionBase):
    """Schema for clicking elements."""

    index: int = Field(
        description="The index of the element to click (from browser_get_state)"
    )
    new_tab: bool = Field(
        default=False,
        description="Whether to open any resulting navigation in a new tab. Default: False",  # noqa: E501
    )


BROWSER_CLICK_DESCRIPTION = """Click an element on the page by its index"""

browser_click_tool = Tool(
    name="browser_click",
    action_type=BrowserClickAction,
    observation_type=BrowserObservation,
    description=BROWSER_CLICK_DESCRIPTION,
    annotations=ToolAnnotations(
        title="browser_click",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
)


class BrowserClickTool(Tool[BrowserClickAction, BrowserObservation]):
    """Tool for clicking browser elements."""

    @classmethod
    def create(cls, executor: BrowserToolExecutor):
        return cls(
            name=browser_click_tool.name,
            description=BROWSER_CLICK_DESCRIPTION,
            action_type=BrowserClickAction,
            observation_type=BrowserObservation,
            annotations=browser_click_tool.annotations,
            executor=executor,
        )


# ============================================
# `browser_type`
# ============================================
class BrowserTypeAction(ActionBase):
    """Schema for typing text into elements."""

    index: int = Field(
        description="The index of the input element (from browser_get_state)"
    )
    text: str = Field(description="The text to type")


BROWSER_TYPE_DESCRIPTION = """Type text into an input field"""

browser_type_tool = Tool(
    name="browser_type",
    action_type=BrowserTypeAction,
    observation_type=BrowserObservation,
    description=BROWSER_TYPE_DESCRIPTION,
    annotations=ToolAnnotations(
        title="browser_type",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
)


class BrowserTypeTool(Tool[BrowserTypeAction, BrowserObservation]):
    """Tool for typing text into browser elements."""

    @classmethod
    def create(cls, executor: BrowserToolExecutor):
        return cls(
            name=browser_type_tool.name,
            description=BROWSER_TYPE_DESCRIPTION,
            action_type=BrowserTypeAction,
            observation_type=BrowserObservation,
            annotations=browser_type_tool.annotations,
            executor=executor,
        )


# ============================================
# `browser_get_state`
# ============================================
class BrowserGetStateAction(ActionBase):
    """Schema for getting browser state."""

    include_screenshot: bool = Field(
        default=False,
        description="Whether to include a screenshot of the current page. Default: False",  # noqa: E501
    )


BROWSER_GET_STATE_DESCRIPTION = (
    """Get the current state of the page including all interactive elements"""
)

browser_get_state_tool = Tool(
    name="browser_get_state",
    action_type=BrowserGetStateAction,
    observation_type=BrowserObservation,
    description=BROWSER_GET_STATE_DESCRIPTION,
    annotations=ToolAnnotations(
        title="browser_get_state",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)


class BrowserGetStateTool(Tool[BrowserGetStateAction, BrowserObservation]):
    """Tool for getting browser state."""

    @classmethod
    def create(cls, executor: BrowserToolExecutor):
        return cls(
            name=browser_get_state_tool.name,
            description=BROWSER_GET_STATE_DESCRIPTION,
            action_type=BrowserGetStateAction,
            observation_type=BrowserObservation,
            annotations=browser_get_state_tool.annotations,
            executor=executor,
        )
