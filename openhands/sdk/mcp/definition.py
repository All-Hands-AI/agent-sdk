"""MCPTool definition and implementation."""

import mcp.types
from pydantic import Field

from openhands.sdk.llm import ImageContent, TextContent
from openhands.sdk.logger import get_logger
from openhands.sdk.tool import (
    ObservationBase,
)


logger = get_logger(__name__)


# NOTE: We don't define MCPToolAction because it
# will be dynamically created from the MCP tool schema.


class MCPToolObservation(ObservationBase):
    """Observation from MCP tool execution."""

    content: list[TextContent | ImageContent] = Field(
        default_factory=list,
        description="Content returned from the MCP tool converted "
        "to LLM Ready TextContent or ImageContent",
    )
    is_error: bool = Field(
        default=False, description="Whether the call resulted in an error"
    )
    tool_name: str = Field(description="Name of the tool that was called")

    @classmethod
    def from_call_tool_result(
        cls, tool_name: str, result: mcp.types.CallToolResult
    ) -> "MCPToolObservation":
        """Create an MCPToolObservation from a CallToolResult."""
        content: list[mcp.types.ContentBlock] = result.content
        convrted_content = []
        for block in content:
            if isinstance(block, mcp.types.TextContent):
                convrted_content.append(TextContent(text=block.text))
            elif isinstance(block, mcp.types.ImageContent):
                convrted_content.append(
                    ImageContent(
                        image_urls=[f"data:{block.mimeType};base64,{block.data}"],
                        # ImageContent is inherited from mcp.types.ImageContent
                        # so we need to pass these fields
                        data=block.data,
                        mimeType=block.mimeType,
                    )
                )
            else:
                logger.warning(
                    f"Unsupported MCP content block type: {type(block)}. Ignoring."
                )
        return cls(
            content=convrted_content,
            is_error=result.isError,
            tool_name=tool_name,
        )

    @property
    def agent_observation(self) -> list[TextContent | ImageContent]:
        """Format the observation for agent display."""
        initial_message = f"[Tool '{self.tool_name}' executed.]\n"
        if self.is_error:
            initial_message += "[An error occurred during execution.]\n"
        return [TextContent(text=initial_message)] + self.content
