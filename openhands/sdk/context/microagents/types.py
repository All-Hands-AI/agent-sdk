from datetime import datetime, timezone
from enum import Enum

from fastmcp.mcp_config import MCPConfig
from pydantic import BaseModel, Field


class MicroagentType(str, Enum):
    """Type of microagent."""

    KNOWLEDGE = "knowledge"  # Optional microagent, triggered by keywords
    REPO_KNOWLEDGE = "repo"  # Always active microagent
    TASK = "task"  # Special type for task microagents that require user input


class InputMetadata(BaseModel):
    """Metadata for task microagent inputs."""

    name: str = Field(..., description="Name of the input parameter")
    description: str = Field(..., description="Description of the input parameter")


class MicroagentMetadata(BaseModel):
    """Metadata for all microagents."""

    name: str = Field("default", description="Unique name of the microagent")
    type: MicroagentType = Field(default=MicroagentType.REPO_KNOWLEDGE)
    triggers: list[str] = []  # optional, only exists for knowledge microagents
    inputs: list[InputMetadata] = []  # optional, only exists for task microagents
    mcp_tools: MCPConfig | None = (
        None  # optional, for microagents that provide additional MCP tools
    )


class MicroagentKnowledge(BaseModel):
    """Represents knowledge from a triggered microagent."""

    name: str = Field(description="The name of the microagent that was triggered")
    trigger: str = Field(description="The word that triggered this microagent")
    content: str = Field(description="The actual content/knowledge from the microagent")


class MicroagentResponse(BaseModel):
    """Response model for microagents endpoint.

    Note: This model only includes basic metadata that can be determined
    without parsing microagent content. Use the separate content API
    to get detailed microagent information.
    """

    name: str = Field(description="The name of the microagent")
    path: str = Field(description="The path or identifier of the microagent")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the microagent was created",
    )


class MicroagentContentResponse(BaseModel):
    """Response model for individual microagent content endpoint."""

    content: str = Field(description="The full content of the microagent")
    path: str = Field(description="The path or identifier of the microagent")
    triggers: list[str] = Field(
        description="List of triggers associated with the microagent"
    )
    git_provider: str | None = Field(
        None,
        description="Git provider if the microagent is sourced from a Git repository",
    )
