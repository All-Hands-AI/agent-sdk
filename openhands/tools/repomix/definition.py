"""Repomix tool implementation for codebase packaging and analysis."""

from pydantic import Field
from rich.text import Text

from openhands.sdk.llm import ImageContent, TextContent
from openhands.sdk.logger import get_logger
from openhands.sdk.mcp import MCPToolObservation, create_mcp_tools
from openhands.sdk.tool import (
    ActionBase,
    Tool,
    ToolAnnotations,
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
            "usage by ~70% while preserving semantic meaning. Generally not needed "
            "since you can use grep to do incremental content retrieval. "
            "Use only when you specifically need the entire codebase content "
            "for large repositories (default: false)."
        ),
    )
    include_patterns: str | None = Field(
        default=None,
        description=(
            "Specify files to include using fast-glob patterns. Multiple patterns "
            "can be comma-separated (e.g., '**/*.{js,ts}', 'src/**,docs/**'). "
            "Only matching files will be processed. "
            "Useful for focusing on specific parts of the codebase."
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
            "for codebase analysis (default: 10)."
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
            content.append("\n🗜️  Compression: enabled")
        if self.include_patterns:
            content.append(f"\n📁 Include: {self.include_patterns}")
        if self.ignore_patterns:
            content.append(f"\n🚫 Ignore: {self.ignore_patterns}")
        if self.top_files_length != 10:
            content.append(f"\n📊 Top files: {self.top_files_length}")

        return content


class PackCodebaseObservation(MCPToolObservation):
    """Observation from packing a codebase with repomix.

    It has the same set of fields as MCPToolObservation.
    """

    @property
    def visualize(self) -> Text:
        """Return Rich Text representation with repomix output styling."""
        content = Text()

        if self.is_error:
            content.append("❌ Repomix Errored", style="red bold")

        content.append("📦 Repomix Output", style="blue bold")
        for item in self.content:
            if isinstance(item, TextContent):
                content.append(f"\n{item.text}", style="white")
            elif isinstance(item, ImageContent):
                content.append(
                    f"\n[Image: {
                        ', '.join([u[:50] + '...' for u in item.image_urls])
                    }]",
                    style="white",
                )
            else:
                content.append("\n[Unknown content type]", style="white")
        return content


TOOL_DESCRIPTION = (
    "Package a local code directory into a consolidated XML file for AI analysis. "
    "This tool analyzes the codebase structure, extracts relevant code content, "
    "and generates a comprehensive report including metrics, file tree, "
    "and formatted code content. "
    "Supports Tree-sitter compression for efficient token usage."
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
        tools = create_mcp_tools(
            {
                "mcpServers": {
                    "repomix": {
                        "command": "npx",
                        "args": ["-y", "repomix@1.4.2", "--mcp"],
                    },
                }
            }
        )
        assert any(t.name == "pack_codebase" for t in tools), "Repomix tool not found"
        repomix_tool = next(t for t in tools if t.name == "pack_codebase")
        assert repomix_tool.executor is not None, "Repomix tool has no executor"

        # Initialize the parent Tool with the executor
        return cls(
            name="pack_codebase",
            description=TOOL_DESCRIPTION,
            action_type=PackCodebaseAction,
            observation_type=PackCodebaseObservation,
            annotations=pack_codebase_tool.annotations,
            executor=repomix_tool.executor,  # use the MCP executor
        )
