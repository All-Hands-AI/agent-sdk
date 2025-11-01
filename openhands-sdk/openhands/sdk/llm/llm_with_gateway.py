"""LLM subclass with enterprise gateway support.

This module provides LLMWithGateway, which extends the base LLM class to support
custom headers for enterprise API gateways.
"""

from __future__ import annotations

from typing import Any

from litellm.types.utils import ModelResponse
from pydantic import Field

from openhands.sdk.llm.llm import LLM


__all__ = ["LLMWithGateway"]


class LLMWithGateway(LLM):
    """LLM subclass with enterprise gateway support.

    Supports adding custom headers on each request with optional template
    rendering against LLM attributes.
    """

    custom_headers: dict[str, str] | None = Field(
        default=None,
        description="Custom headers to include with every LLM request.",
    )

    def responses(self, *args, **kwargs):
        """Override to inject gateway headers before calling LiteLLM."""
        self._prepare_gateway_call(kwargs)
        return super().responses(*args, **kwargs)

    def _transport_call(
        self, *, messages: list[dict[str, Any]], **kwargs
    ) -> ModelResponse:
        """Inject gateway headers just before delegating to LiteLLM."""
        self._prepare_gateway_call(kwargs)
        return super()._transport_call(messages=messages, **kwargs)

    def _prepare_gateway_call(self, call_kwargs: dict[str, Any]) -> None:
        """Augment LiteLLM kwargs with gateway headers.

        This method:
        1. Adds custom headers
        2. Performs basic template variable replacement
        """
        if not self.custom_headers:
            return

        # Start with existing headers
        headers: dict[str, str] = {}
        existing_headers = call_kwargs.get("extra_headers")
        if isinstance(existing_headers, dict):
            headers.update(existing_headers)

        # Add custom headers (with template replacement)
        if self.custom_headers:
            rendered_headers = self._render_templates(self.custom_headers)
            if isinstance(rendered_headers, dict):
                headers.update(rendered_headers)

        # Set headers on the call
        if headers:
            call_kwargs["extra_headers"] = headers

    def _render_templates(self, value: Any) -> Any:
        """Replace template variables in strings with actual values.

        Supports:
        - {{llm_model}} -> self.model
        - {{llm_base_url}} -> self.base_url
        - {{llm_api_key}} -> self.api_key (if set)

        Args:
            value: String, dict, list, or other value to render.

        Returns:
            Value with templates replaced.
        """
        if isinstance(value, str):
            replacements: dict[str, str] = {
                "{{llm_model}}": self.model,
                "{{llm_base_url}}": self.base_url or "",
            }
            if self.api_key:
                replacements["{{llm_api_key}}"] = self.api_key.get_secret_value()

            result = value
            for placeholder, actual in replacements.items():
                result = result.replace(placeholder, actual)
            return result

        if isinstance(value, dict):
            return {k: self._render_templates(v) for k, v in value.items()}

        if isinstance(value, list):
            return [self._render_templates(v) for v in value]

        return value
