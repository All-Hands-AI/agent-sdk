from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


VALID_MICROAGENT_TYPES = ["knowledge", "repo", "task"]
MicroagentType = Literal[
    "knowledge",
    "repo",
    "task",
]


class InputMetadata(BaseModel):
    """Metadata for task microagent inputs."""

    name: str = Field(description="Name of the input parameter")
    description: str = Field(description="Description of the input parameter")


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
        default_factory=lambda: datetime.now(UTC),
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
