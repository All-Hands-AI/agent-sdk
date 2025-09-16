from typing import Any

from pydantic import BaseModel, Field, field_validator


class CondenserSpec(BaseModel):
    """Defines a condenser to be initialized for the agent.

    Attributes:
        name (str): Name of the condenser class, e.g., 'LLMSummarizingCondenser',
            must be importable from openhands.sdk.context.condenser
        params (dict): Input parameters required for the condenser.
    """

    name: str = Field(
        ...,
        description="Name of the condenser class. "
        "Must be importable from openhands.sdk.context.condenser.",
        examples=["LLMSummarizingCondenser"],
    )
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters for the condenser's .create() method.",
        examples=[
            {
                "llm": {"model": "gpt-5", "api_key": "sk-XXX"},
                "max_size": 80,
                "keep_first": 10,
            }
        ],
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate that name is not empty."""
        if not v or not v.strip():
            raise ValueError("Condenser name cannot be empty")
        return v

    @field_validator("params", mode="before")
    @classmethod
    def validate_params(cls, v: dict[str, Any] | None) -> dict[str, Any]:
        """Convert None params to empty dict."""
        return v if v is not None else {}
