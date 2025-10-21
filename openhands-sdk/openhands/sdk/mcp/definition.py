"""MCPTool definition and implementation."""

import json
from collections.abc import Sequence
from typing import Any

import mcp.types
from pydantic import Field
from rich.text import Text

from openhands.sdk.llm import ImageContent, TextContent
from openhands.sdk.logger import get_logger
from openhands.sdk.tool import (
    Observation,
)
from openhands.sdk.tool.schema import Action
from openhands.sdk.utils.visualize import display_dict


logger = get_logger(__name__)


# NOTE: We don't define MCPToolAction because it
# will be dynamically created from the MCP tool schema.


class MCPToolAction(Action):
    """Schema for MCP input action.

    It is just a thin wrapper around raw JSON and does
    not do any validation.

    Validation will be performed by MCPTool.__call__
    by constructing dynamically created Pydantic model
    from the MCP tool input schema.
    """

    data: dict[str, Any] = Field(
        default_factory=dict, description="Dynamic data fields from the tool call"
    )

    def to_mcp_arguments(self) -> dict:
        """Return the data field as MCP tool call arguments.

        This is used to convert this action to MCP tool call arguments.
        The data field contains the dynamic fields from the tool call.
        """
        return self.data


class MCPToolObservation(Observation):
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
    def to_llm_content(self) -> Sequence[TextContent | ImageContent]:
        """Format the observation for agent display."""
        initial_message = f"[Tool '{self.tool_name}' executed.]\n"
        if self.is_error:
            initial_message += "[An error occurred during execution.]\n"
        return [TextContent(text=initial_message)] + self.content

    @property
    def visualize(self) -> Text:
        """Return Rich Text representation of this observation."""
        content = Text()
        content.append(f"[MCP Tool '{self.tool_name}' Observation]\n", style="bold")
        if self.is_error:
            content.append("[Error during execution]\n", style="bold red")
        for block in self.content:
            if isinstance(block, TextContent):
                # try to see if block.text is a JSON
                try:
                    parsed = json.loads(block.text)
                    content.append(display_dict(parsed))
                    continue
                except (json.JSONDecodeError, TypeError):
                    content.append(block.text + "\n")
            elif isinstance(block, ImageContent):
                content.append(f"[Image with {len(block.image_urls)} URLs]\n")
        return content
