from __future__ import annotations

from typing import Any, Dict, Optional, Union

import httpx

from .models import (
    RuntimeActionRequest,
    RuntimeActionResponse,
    RuntimeStartRequest,
    RuntimeStartResponse,
)


class RuntimeClientError(RuntimeError):
    """Raised when the runtime server returns an unexpected error."""


class RuntimeNotFound(RuntimeClientError):
    """Raised when the runtime server cannot locate the requested runtime."""


RequestType = Union[RuntimeStartRequest, RuntimeActionRequest, Dict[str, Any]]


class RuntimeServerClient:
    """Blocking HTTP client for interacting with the runtime server API."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout: Optional[float] = 10.0,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        if http_client is not None:
            if not base_url and not getattr(http_client, "base_url", ""):
                raise ValueError("Provide base_url or configure it on the http_client")
            self._client = http_client
            self._owns_client = False
        else:
            if not base_url:
                raise ValueError("base_url must be provided")
            self._client = httpx.Client(
                base_url=base_url.rstrip("/"),
                timeout=timeout,
            )
            self._owns_client = True

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "RuntimeServerClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def start_runtime(self, request: RequestType) -> RuntimeStartResponse:
        payload = _ensure_model(RuntimeStartRequest, request)
        response = self._client.post("/start", json=payload.model_dump(mode="json"))
        return _parse_response(response, RuntimeStartResponse)

    def stop_runtime(self, request: RequestType) -> RuntimeActionResponse:
        payload = _ensure_model(RuntimeActionRequest, request)
        response = self._client.post("/stop", json=payload.model_dump(mode="json"))
        return _parse_response(response, RuntimeActionResponse)

    def pause_runtime(self, request: RequestType) -> RuntimeActionResponse:
        payload = _ensure_model(RuntimeActionRequest, request)
        response = self._client.post("/pause", json=payload.model_dump(mode="json"))
        return _parse_response(response, RuntimeActionResponse)

    def resume_runtime(self, request: RequestType) -> RuntimeActionResponse:
        payload = _ensure_model(RuntimeActionRequest, request)
        response = self._client.post("/resume", json=payload.model_dump(mode="json"))
        return _parse_response(response, RuntimeActionResponse)


def _ensure_model(model_cls, value: RequestType):
    if isinstance(value, model_cls):
        return value
    if isinstance(value, dict):
        return model_cls.model_validate(value)
    raise TypeError(
        f"Expected {model_cls.__name__} or dict, received {type(value).__name__}"
    )


def _parse_response(response: httpx.Response, model_cls):
    if 200 <= response.status_code < 300:
        return model_cls.model_validate(response.json())

    if response.status_code == 404:
        raise RuntimeNotFound(response.text)

    raise RuntimeClientError(
        f"Runtime server responded with {response.status_code}: {response.text}"
    )
