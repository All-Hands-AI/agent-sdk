from typing import Any

from pydantic import BaseModel, Field


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
