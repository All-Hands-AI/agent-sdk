from typing import Literal

from litellm import ChatCompletionMessageToolCall, ResponseFunctionToolCall
from pydantic import BaseModel, Field


class LLMToolCall(BaseModel):
    """Transport-agnostic tool call representation.

    One canonical id is used for linking across actions/observations and
    for Responses function_call_output call_id.
    """

    id: str = Field(..., description="Canonical tool call id")
    name: str = Field(..., description="Tool/function name")
    arguments_json: str = Field(..., description="JSON string of arguments")
    origin: Literal["completion", "responses"] = Field(
        ..., description="Originating API family"
    )
    raw: ChatCompletionMessageToolCall | ResponseFunctionToolCall | None = Field(
        default=None, description="Original provider object for advanced consumers"
    )
