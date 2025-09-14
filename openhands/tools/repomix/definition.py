"""Repomix tool implementation for codebase packaging and analysis."""

import asyncio
import os
from collections.abc import Sequence
from typing import Any

from pydantic import Field
from rich.text import Text

from openhands.sdk.llm import ImageContent, TextContent
from openhands.sdk.logger import get_logger
from openhands.sdk.mcp import MCPClient
from openhands.sdk.tool import (
    ActionBase,
    ObservationBase,
    Tool,
    ToolAnnotations,
    ToolExecutor,
)


logger = get_logger(__name__)


class PackCodebaseAction(ActionBase):
    """Schema for packing a codebase using repomix."""

    directory: str = Field(description="Absolute path to the directory to pack")
    compress: bool = Field(
        default=False,
        description=(
            "Enable Tree-sitter compression to extract essential code signatures "
            "and structure while removing implementation details. Reduces token "
            "usage by ~70% while preserving semantic meaning."
        ),
    )
    include_patterns: str | None = Field(
        default=None,
        description=(
            "Specify files to include using fast-glob patterns. Multiple patterns "
            "can be comma-separated (e.g., '**/*.{js,ts}', 'src/**,docs/**'). "
            "Only matching files will be processed."
        ),
    )
    ignore_patterns: str | None = Field(
        default=None,
        description=(
            "Specify additional files to exclude using fast-glob patterns. "
            "Multiple patterns can be comma-separated (e.g., 'test/**,*.spec.js', "
            "'node_modules/**,dist/**'). These patterns supplement .gitignore "
            "and built-in exclusions."
        ),
    )
    top_files_length: int = Field(
        default=10,
        description=(
            "Number of largest files by size to display in the metrics summary "
            "for codebase analysis."
        ),
    )

    @property
    def visualize(self) -> Text:
        """Return Rich Text representation with repomix styling."""
        content = Text()

        # Add repomix icon and command
        content.append("📦 ", style="blue")
        content.append("Pack Codebase", style="blue bold")

        # Add directory path
        content.append(f"\nDirectory: {self.directory}", style="white")

        # Add options if set
        if self.compress:
            content.append("\n🗜️  Compression: enabled", style="green")

        if self.include_patterns:
            content.append(f"\n📁 Include: {self.include_patterns}", style="cyan")

        if self.ignore_patterns:
            content.append(f"\n🚫 Ignore: {self.ignore_patterns}", style="yellow")

        if self.top_files_length != 10:
            content.append(f"\n📊 Top files: {self.top_files_length}", style="magenta")

        return content


class PackCodebaseObservation(ObservationBase):
    """Observation from packing a codebase with repomix."""

    output: str = Field(description="The packed codebase content")
    directory: str = Field(description="The directory that was packed")
    output_id: str | None = Field(
        default=None, description="ID of the output for future reference"
    )
    error: bool = Field(default=False, description="Whether there was an error")
    error_message: str | None = Field(
        default=None, description="Error message if there was an error"
    )

    @property
    def agent_observation(self) -> Sequence[TextContent | ImageContent]:
        if self.error and self.error_message:
            return [
                TextContent(
                    text=f"Error packing codebase from {self.directory}: "
                    f"{self.error_message}"
                )
            ]

        # Truncate output if it's too long for the observation
        max_length = 50000  # Reasonable limit for agent observation
        output_text = self.output
        if len(output_text) > max_length:
            output_text = (
                output_text[:max_length]
                + f"\n\n[Output truncated - total length: {len(self.output)} "
                "characters]"
            )

        return [
            TextContent(
                text=f"Successfully packed codebase from {self.directory}. "
                f"Output length: {len(self.output)} characters.\n\n{output_text}"
            )
        ]

    @property
    def visualize(self) -> Text:
        """Return Rich Text representation with repomix output styling."""
        content = Text()

        if self.error:
            content.append("❌ ", style="red bold")
            content.append("Repomix Error", style="red")
            if self.error_message:
                content.append(f"\n{self.error_message}", style="red")
        else:
            content.append("✅ ", style="green bold")
            content.append("Codebase Packed Successfully", style="green")
            content.append(f"\n📁 Directory: {self.directory}", style="white")
            content.append(
                f"\n📊 Output size: {len(self.output):,} characters", style="cyan"
            )

            if self.output_id:
                content.append(f"\n🆔 Output ID: {self.output_id}", style="magenta")

        return content


class RepomixExecutor(ToolExecutor):
    """Executor for the repomix tool using MCP client."""

    def __init__(self):
        """Initialize RepomixExecutor with MCP client configuration."""
        # Configure MCP client for repomix
        self.mcp_config = {
            "mcpServers": {
                "repomix": {
                    "command": "npx",
                    "args": ["-y", "repomix", "--mcp"],
                }
            }
        }

    def __call__(self, action: PackCodebaseAction) -> PackCodebaseObservation:
        """Execute the pack codebase action using repomix MCP server."""
        try:
            # Run the MCP call in an async context
            return asyncio.run(self._pack_codebase_async(action))
        except Exception as e:
            logger.error(f"Error in repomix executor: {e}")
            return PackCodebaseObservation(
                output="",
                directory=action.directory,
                error=True,
                error_message=str(e),
            )

    async def _pack_codebase_async(
        self, action: PackCodebaseAction
    ) -> PackCodebaseObservation:
        """Async implementation of pack_codebase using MCP client."""
        from fastmcp.mcp_config import MCPConfig

        try:
            # Validate directory exists
            if not os.path.exists(action.directory):
                return PackCodebaseObservation(
                    output="",
                    directory=action.directory,
                    error=True,
                    error_message=f"Directory does not exist: {action.directory}",
                )

            # Convert to absolute path
            abs_directory = os.path.abspath(action.directory)

            # Create MCP client
            config = MCPConfig.model_validate(self.mcp_config)
            client = MCPClient(config)

            async with client:
                # Prepare arguments for pack_codebase
                args: dict[str, Any] = {"directory": abs_directory}

                if action.compress:
                    args["compress"] = action.compress

                if action.include_patterns:
                    args["includePatterns"] = action.include_patterns

                if action.ignore_patterns:
                    args["ignorePatterns"] = action.ignore_patterns

                if action.top_files_length != 10:
                    args["topFilesLength"] = action.top_files_length

                # Call the pack_codebase tool
                result = await client.call_tool("pack_codebase", args)

                # Extract the output content
                if result and hasattr(result, "content") and result.content:
                    # Get the first content item (should be text)
                    content_item = result.content[0]
                    # Use getattr to safely access text attribute
                    text_content = getattr(content_item, "text", None)
                    if text_content is not None:
                        output = str(text_content)
                    else:
                        output = str(content_item)
                else:
                    output = "No output received from repomix"

                return PackCodebaseObservation(
                    output=output,
                    directory=abs_directory,
                    error=False,
                )

        except Exception as e:
            logger.error(f"Error calling repomix MCP server: {e}")
            return PackCodebaseObservation(
                output="",
                directory=action.directory,
                error=True,
                error_message=f"MCP server error: {str(e)}",
            )


TOOL_DESCRIPTION = (
    "Pack a codebase into a consolidated XML file for AI analysis using repomix.\n"
    "\n"
    "This tool uses repomix (https://repomix.com/) to analyze a codebase structure, "
    "extract relevant code content, and generate a comprehensive report including "
    "metrics, file tree, and formatted code content.\n"
    "\n"
    "### Features\n"
    "* **Codebase Analysis**: Analyzes directory structure and extracts code content\n"
    "* **Compression**: Optional Tree-sitter compression to reduce token usage by ~70%\n"  # noqa: E501
    "* **Pattern Filtering**: Include/exclude files using fast-glob patterns\n"
    "* **Metrics**: Provides file size metrics and codebase statistics\n"
    "* **AI-Optimized**: Generates output specifically formatted for AI analysis\n"
    "\n"
    "### Parameters\n"
    "* `directory`: (Required) Absolute path to the directory to pack\n"
    "* `compress`: (Optional) Enable compression to reduce token usage\n"
    "* `include_patterns`: (Optional) Comma-separated glob patterns for files to "
    "include\n"
    "* `ignore_patterns`: (Optional) Comma-separated glob patterns for files to "
    "exclude\n"
    "* `top_files_length`: (Optional) Number of largest files to show in metrics\n"
    "\n"
    "### Examples\n"
    "```python\n"
    "# Basic usage\n"
    'action = PackCodebaseAction(directory="/path/to/project")\n'
    "\n"
    "# With compression and filtering\n"
    "action = PackCodebaseAction(\n"
    '    directory="/path/to/project",\n'
    "    compress=True,\n"
    '    include_patterns="src/**/*.py,**/*.md",\n'
    '    ignore_patterns="test/**,*.log"\n'
    ")\n"
    "```\n"
    "\n"
    "### Requirements\n"
    "This tool requires repomix to be available via npx. It will automatically install "
    "repomix if not present when using npx -y repomix.\n"
    "\n"
    "### Source\n"
    "Based on repomix MCP server: https://repomix.com/guide/mcp-server\n"
    "Repomix repository: https://github.com/yamadashy/repomix"
)

pack_codebase_tool = Tool(
    name="pack_codebase",
    action_type=PackCodebaseAction,
    observation_type=PackCodebaseObservation,
    description=TOOL_DESCRIPTION,
    annotations=ToolAnnotations(
        title="pack_codebase",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)


class RepomixTool(Tool[PackCodebaseAction, PackCodebaseObservation]):
    """A Tool subclass that automatically initializes a RepomixExecutor."""

    @classmethod
    def create(cls) -> "RepomixTool":
        """Initialize RepomixTool with a RepomixExecutor.

        Returns:
            RepomixTool: Configured repomix tool instance
        """
        executor = RepomixExecutor()

        # Initialize the parent Tool with the executor
        return cls(
            name="pack_codebase",
            description=TOOL_DESCRIPTION,
            action_type=PackCodebaseAction,
            observation_type=PackCodebaseObservation,
            annotations=pack_codebase_tool.annotations,
            executor=executor,
        )
