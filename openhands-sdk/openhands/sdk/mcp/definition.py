"""MCPTool definition and implementation."""

import json
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

    tool_name: str = Field(description="Name of the tool that was called")

    @classmethod
    def from_call_tool_result(
        cls, tool_name: str, result: mcp.types.CallToolResult
    ) -> "MCPToolObservation":
        """Create an MCPToolObservation from a CallToolResult."""
        content: list[mcp.types.ContentBlock] = result.content
        text_parts = []
        output_content: list[TextContent | ImageContent] = []

        for block in content:
            if isinstance(block, mcp.types.TextContent):
                text_parts.append(block.text)
            elif isinstance(block, mcp.types.ImageContent):
                output_content.append(
                    ImageContent(
                        image_urls=[f"data:{block.mimeType};base64,{block.data}"],
                    )
                )
            else:
                logger.warning(
                    f"Unsupported MCP content block type: {type(block)}. Ignoring."
                )

        header = f"[Tool '{tool_name}' executed.]"
        text_content = "\n".join(text_parts) if text_parts else ""

        # Populate error or output field based on result status
        if result.isError:
            error_msg = (
                f"{header}\n[An error occurred during execution.]\n{text_content}"
            )
            # When there is an error, don't populate output
            return cls(
                error=error_msg,
                tool_name=tool_name,
            )
        else:
            # When success, don't populate error
            # Combine text and images in output
            if text_content:
                output_msg = f"{header}\n{text_content}"
                output_content.insert(0, TextContent(text=output_msg))
            else:
                output_content.insert(0, TextContent(text=header))

            return cls(
                output=output_content,
                tool_name=tool_name,
            )

    @property
    def visualize(self) -> Text:
        """Return Rich Text representation of this observation."""
        content = Text()
        content.append(f"[MCP Tool '{self.tool_name}' Observation]\n", style="bold")

        if self.has_error:
            content.append("[Error during execution]\n", style="bold red")
            if self.error:
                content.append(self.error + "\n")
        elif self.output:
            # Display all content blocks
            for block in self.output:
                if isinstance(block, TextContent):
                    # Try to parse as JSON for better display
                    try:
                        parsed = json.loads(block.text)
                        content.append(display_dict(parsed))
                    except (json.JSONDecodeError, TypeError):
                        content.append(block.text + "\n")
                elif isinstance(block, ImageContent):
                    content.append(f"[Image with {len(block.image_urls)} URLs]\n")

        return content
