"""LLM subclass with enterprise gateway support.

This module provides LLMWithGateway, which extends the base LLM class to support
OAuth 2.0 authentication flows and custom headers for enterprise API gateways.
"""

from __future__ import annotations

import threading
import time
from typing import Any

import httpx
from litellm.types.utils import ModelResponse
from pydantic import Field, PrivateAttr

from openhands.sdk.llm.llm import LLM
from openhands.sdk.logger import get_logger


logger = get_logger(__name__)

__all__ = ["LLMWithGateway"]


class LLMWithGateway(LLM):
    """LLM subclass with enterprise gateway support.

    Supports OAuth 2.0 token exchange with configurable headers and bodies.
    Designed for enterprise API gateways that require:
    1. Initial OAuth call to get a bearer token
    2. Bearer token included in subsequent LLM API calls
    3. Custom headers for routing/authentication

    Example usage:
        llm = LLMWithGateway(
            model="gpt-4",
            base_url="https://gateway.company.com/llm/v1",
            gateway_auth_url="https://gateway.company.com/oauth/token",
            gateway_auth_headers={
                "X-Client-Id": os.environ["GATEWAY_CLIENT_ID"],
                "X-Client-Secret": os.environ["GATEWAY_CLIENT_SECRET"],
            },
            gateway_auth_body={"grant_type": "client_credentials"},
            custom_headers={"X-Gateway-Key": os.environ["GATEWAY_API_KEY"]},
        )
    """

    # OAuth configuration
    gateway_auth_url: str | None = Field(
        default=None,
        description="Identity provider URL to fetch gateway tokens (OAuth endpoint).",
    )
    gateway_auth_method: str = Field(
        default="POST",
        description="HTTP method for identity provider requests.",
    )
    gateway_auth_headers: dict[str, str] | None = Field(
        default=None,
        description="Headers to include when calling the identity provider.",
    )
    gateway_auth_body: dict[str, Any] | None = Field(
        default=None,
        description="JSON body to include when calling the identity provider.",
    )
    gateway_auth_token_path: str = Field(
        default="access_token",
        description=(
            "Dot-notation path to the token in the OAuth response "
            "(e.g., 'access_token' or 'data.token')."
        ),
    )
    gateway_auth_token_ttl: int | None = Field(
        default=None,
        description=(
            "Token TTL in seconds. If not set, uses `expires_in` from the OAuth"
            " response when available, falling back to 300s (5 minutes)."
        ),
    )

    # Token header configuration
    gateway_token_header: str = Field(
        default="Authorization",
        description="Header name for the gateway token (defaults to 'Authorization').",
    )
    gateway_token_prefix: str = Field(
        default="Bearer ",
        description="Prefix prepended to the token (e.g., 'Bearer ').",
    )

    # Custom headers for all requests
    custom_headers: dict[str, str] | None = Field(
        default=None,
        description="Custom headers to include with every LLM request.",
    )

    # Private fields for token management
    _gateway_lock: threading.Lock = PrivateAttr(default_factory=threading.Lock)
    _gateway_token: str | None = PrivateAttr(default=None)
    _gateway_token_expiry: float | None = PrivateAttr(default=None)

    def model_post_init(self, __context: Any) -> None:
        """Initialize private fields after model validation."""
        super().model_post_init(__context)
        self._gateway_lock = threading.Lock()
        self._gateway_token = None
        self._gateway_token_expiry = None

    def responses(self, *args, **kwargs):
        """Override to inject gateway authentication before calling LiteLLM."""
        self._prepare_gateway_call(kwargs)
        return super().responses(*args, **kwargs)

    def _transport_call(
        self, *, messages: list[dict[str, Any]], **kwargs
    ) -> ModelResponse:
        """Inject gateway headers just before delegating to LiteLLM."""
        self._prepare_gateway_call(kwargs)
        return super()._transport_call(messages=messages, **kwargs)

    def _prepare_gateway_call(self, call_kwargs: dict[str, Any]) -> None:
        """Augment LiteLLM kwargs with gateway headers and token.

        This method:
        1. Fetches/refreshes OAuth token if needed
        2. Adds token to headers
        3. Adds custom headers
        4. Performs basic template variable replacement
        """
        if not self.gateway_auth_url and not self.custom_headers:
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

        # Add gateway token if OAuth is configured
        if self.gateway_auth_url:
            token_headers = self._get_gateway_token_headers()
            if token_headers:
                headers.update(token_headers)

        # Set headers on the call
        if headers:
            call_kwargs["extra_headers"] = headers

    def _get_gateway_token_headers(self) -> dict[str, str]:
        """Get headers containing the gateway token."""
        token = self._ensure_gateway_token()
        if not token:
            return {}

        header_name = self.gateway_token_header
        prefix = self.gateway_token_prefix
        value = f"{prefix}{token}" if prefix else token
        return {header_name: value}

    def _ensure_gateway_token(self) -> str | None:
        """Ensure we have a valid gateway token, refreshing if needed.

        Returns:
            Valid gateway token, or None if gateway auth is not configured.
        """
        if not self.gateway_auth_url:
            return None

        # Fast path: check if current token is still valid (with 5s buffer)
        now = time.time()
        if (
            self._gateway_token
            and self._gateway_token_expiry
            and now < self._gateway_token_expiry - 5
        ):
            return self._gateway_token

        # Slow path: acquire lock and refresh token
        with self._gateway_lock:
            # Double-check after acquiring lock
            if (
                self._gateway_token
                and self._gateway_token_expiry
                and time.time() < self._gateway_token_expiry - 5
            ):
                return self._gateway_token

            # Refresh token
            return self._refresh_gateway_token()

    def _refresh_gateway_token(self) -> str:
        """Fetch a new gateway token from the identity provider.

        This method is called while holding _gateway_lock.

        Returns:
            Fresh gateway token.

        Raises:
            Exception: If token fetch fails.
        """
        assert self.gateway_auth_url is not None, "gateway_auth_url must be set"
        method = self.gateway_auth_method.upper()
        headers = self._render_templates(self.gateway_auth_headers or {})
        body = self._render_templates(self.gateway_auth_body or {})

        logger.debug(
            f"Fetching gateway token from {self.gateway_auth_url} (method={method})"
        )

        try:
            response = httpx.request(
                method,
                self.gateway_auth_url,
                headers=headers if isinstance(headers, dict) else None,
                json=body if isinstance(body, dict) else None,
                timeout=self.timeout or 30,
            )
            response.raise_for_status()
        except Exception as exc:
            logger.error(f"Gateway auth request failed: {exc}")
            raise

        try:
            payload = response.json()
        except Exception as exc:
            logger.error(f"Failed to parse gateway auth response JSON: {exc}")
            raise

        # Extract token from response
        token_path = self.gateway_auth_token_path
        token_value = self._extract_from_path(payload, token_path)
        if not isinstance(token_value, str) or not token_value.strip():
            raise ValueError(
                f"Gateway auth response did not contain token at path "
                f'"{token_path}". Response: {payload}'
            )

        # Determine TTL
        ttl_seconds: float | None = None
        if self.gateway_auth_token_ttl is not None:
            try:
                ttl_seconds = float(self.gateway_auth_token_ttl)
            except (TypeError, ValueError):  # pragma: no cover - defensive
                logger.warning(
                    "Configured gateway_auth_token_ttl is not numeric; falling back"
                )
                ttl_seconds = None
        else:
            expires_in = None
            if isinstance(payload, dict):
                expires_in = payload.get("expires_in")
            if expires_in is not None:
                try:
                    ttl_seconds = float(expires_in)
                except (TypeError, ValueError):
                    logger.warning(
                        "Invalid expires_in value %r from gateway; using default",
                        expires_in,
                    )

        if ttl_seconds is None or ttl_seconds <= 0:
            ttl_seconds = 300.0

        # Update cache
        self._gateway_token = token_value.strip()
        self._gateway_token_expiry = time.time() + max(ttl_seconds, 1.0)

        logger.info(f"Gateway token refreshed successfully (expires in {ttl_seconds}s)")
        return self._gateway_token

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

    @staticmethod
    def _extract_from_path(payload: Any, path: str) -> Any:
        """Extract a value from nested dict/list using dot notation.

        Examples:
            _extract_from_path({"a": {"b": "value"}}, "a.b") -> "value"
            _extract_from_path({"data": [{"token": "x"}]}, "data.0.token") -> "x"

        Args:
            payload: Dict or list to traverse.
            path: Dot-separated path (e.g., "data.token" or "items.0.value").

        Returns:
            Value at the specified path.

        Raises:
            ValueError: If path cannot be traversed.
        """
        current = payload
        if not path:
            return current

        for part in path.split("."):
            if isinstance(current, dict):
                current = current.get(part)
                if current is None:
                    raise ValueError(
                        f'Key "{part}" not found in response '
                        f'while traversing path "{path}".'
                    )
            elif isinstance(current, list):
                try:
                    index = int(part)
                except (ValueError, TypeError):
                    raise ValueError(
                        f'Invalid list index "{part}" '
                        f'while traversing response path "{path}".'
                    ) from None
                try:
                    current = current[index]
                except (IndexError, TypeError):
                    raise ValueError(
                        f"Index {index} out of range "
                        f'while traversing response path "{path}".'
                    ) from None
            else:
                raise ValueError(
                    f'Cannot traverse path "{path}"; '
                    f'segment "{part}" not found or not accessible.'
                )

        return current
