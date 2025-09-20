"""CompletionResult type for LLM completion responses.

This module provides the CompletionResult type that wraps LLM completion responses
with OpenHands-native types, eliminating the need for consumers to work directly
with LiteLLM types.
"""

from litellm.types.utils import ModelResponse
from pydantic import BaseModel

from openhands.sdk.llm.message import Message
from openhands.sdk.llm.utils.metrics import MetricsSnapshot


__all__ = ["CompletionResult"]


class CompletionResult(BaseModel):
    """Result of an LLM completion request.

    This type provides a clean interface for LLM completion results, exposing
    only OpenHands-native types to consumers while preserving access to the
    raw LiteLLM response for internal use.

    Attributes:
        message: The completion message converted to OpenHands Message type
        metrics: Snapshot of metrics from the completion request
        raw_response: The original LiteLLM ModelResponse for internal use
    """

    message: Message
    metrics: MetricsSnapshot
    raw_response: ModelResponse

    class Config:
        # Allow arbitrary types for ModelResponse
        arbitrary_types_allowed = True
