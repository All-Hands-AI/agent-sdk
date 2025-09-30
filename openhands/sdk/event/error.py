from pydantic import Field
from rich.text import Text

from openhands.sdk.event.base import EventBase
from openhands.sdk.event.types import SourceType


class LLMErrorEvent(EventBase):
    """Error event indicating a failure from the LLM provider.

    This is not an agent error. It represents issues surfaced from the upstream
    LLM provider after retries have been exhausted (or for non-retried cases).
    """

    source: SourceType = "environment"

    # Minimal, pragmatic fields for clear UX and telemetry
    provider: str | None = Field(default=None, description="LLM provider name")
    model: str | None = Field(default=None, description="Model identifier in use")
    code: str = Field(
        description=(
            "Short error code, e.g., rate_limit, service_unavailable, timeout, "
            "no_response, auth_error, provider_internal_error, provider_error"
        )
    )
    retryable: bool = Field(default=False, description="Whether a retry may succeed")
    message: str = Field(description="User-facing error message")
    details: dict | None = Field(
        default=None,
        description="Redacted/safe diagnostic details (e.g., http_status, request_id)",
    )

    @property
    def visualize(self) -> Text:
        content = Text()
        content.append("LLM Error\n", style="bold")
        if self.provider or self.model:
            provider_model = " / ".join(
                [p for p in [self.provider or "", self.model or ""] if p]
            )
            if provider_model:
                content.append(f"Provider/Model: {provider_model}\n")
        content.append(f"Code: {self.code}\n")
        content.append(f"Retryable: {'Yes' if self.retryable else 'No'}\n")
        content.append("Message:\n", style="bold")
        content.append(self.message)
        return content
