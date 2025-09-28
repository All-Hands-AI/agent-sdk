from typing import Any

from pydantic import BaseModel, Field, field_validator


class ToolSpec(BaseModel):
    """Defines a tool to be initialized for the agent.

    This is only used in agent-sdk for type schema for server use.
    """

    name: str = Field(
        ...,
        description=(
            "Name of the tool class, e.g., 'BashTool'. "
            "Import it from an `openhands.tools.<module>` subpackage."
        ),
        examples=["BashTool", "FileEditorTool", "TaskTrackerTool"],
    )
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters for the tool's .create() method,"
        " e.g., {'working_dir': '/app'}",
        examples=[{"working_dir": "/workspace"}],
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate that name is not empty."""
        if not v or not v.strip():
            raise ValueError("Tool name cannot be empty")
        return v

    @field_validator("params", mode="before")
    @classmethod
    def validate_params(cls, v: dict[str, Any] | None) -> dict[str, Any]:
        """Convert None params to empty dict."""
        return v if v is not None else {}

    def resolve_diff_from_deserialized(self, persisted: "ToolSpec") -> "ToolSpec":
        """Resolve differences between a deserialized ToolSpec and the current instance.

        Tools must match by name, but directory-related parameters
        (working_dir, persistent_dir, save_dir, workspace_root) can be overridden
        from the runtime tool.

        Args:
            persisted: The persisted ToolSpec to reconcile with

        Returns:
            A new ToolSpec instance equivalent to `persisted` but with
            directory-related parameters taken from `self`.

        Raises:
            ValueError: If tools don't match (excluding allowed parameter differences)
        """
        if self.name != persisted.name:
            raise ValueError(
                f"Cannot resolve_diff_from_deserialized between tools with different "
                f"names: runtime='{self.name}', persisted='{persisted.name}'"
            )

        # Directory-related parameters that can be overridden
        OVERRIDABLE_PARAMS = {
            "working_dir",
            "persistent_dir",
            "save_dir",
            "workspace_root",
        }

        # Start with persisted tool params
        reconciled_params = persisted.params.copy()

        # Override directory-related parameters from runtime tool
        for param_name in OVERRIDABLE_PARAMS:
            if param_name in self.params:
                reconciled_params[param_name] = self.params[param_name]

        # Check that non-overridable parameters match
        for param_name, param_value in persisted.params.items():
            if param_name not in OVERRIDABLE_PARAMS:
                runtime_value = self.params.get(param_name)
                if runtime_value != param_value:
                    raise ValueError(
                        f"Tool '{self.name}' parameter '{param_name}' doesn't "
                        f"match: runtime={runtime_value}, persisted={param_value}"
                    )

        # Check that runtime tool doesn't have extra non-overridable parameters
        for param_name, param_value in self.params.items():
            if (
                param_name not in OVERRIDABLE_PARAMS
                and param_name not in persisted.params
            ):
                raise ValueError(
                    f"Tool '{self.name}' has extra parameter '{param_name}' "
                    f"in runtime agent"
                )

        # Create reconciled tool spec
        return ToolSpec(name=self.name, params=reconciled_params)
