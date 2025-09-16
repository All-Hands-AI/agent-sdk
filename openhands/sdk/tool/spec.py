from typing import Any

from pydantic import BaseModel, Field


class ToolSpec(BaseModel):
    """Defines a tool to be initialized for the agent.

    This is only used in agent-sdk for type schema for server use.
    """

    name: str = Field(
        ...,
        description="Name of the tool class, e.g., 'BashTool', "
        "must be importable from openhands.tools",
        examples=["BashTool", "FileEditorTool", "TaskTrackerTool"],
    )
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters for the tool's .create() method,"
        " e.g., {'working_dir': '/app'}",
        examples=[{"working_dir": "/workspace"}],
    )
