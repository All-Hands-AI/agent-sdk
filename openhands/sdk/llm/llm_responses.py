from __future__ import annotations

from typing import Any


with __import__("warnings").catch_warnings():  # noqa: E702
    __import__("warnings").simplefilter("ignore")
    from litellm import responses as litellm_responses

from openhands.sdk.llm.message import Message
from openhands.sdk.llm.utils.responses_converter import messages_to_responses_items


class NativeResponsesSession:
    """Thin stateful wrapper around LiteLLM Responses API.

    - Persists previous_response_id for follow-up calls when `store=True`
    - Accepts either `messages` (list[Message|dict]) or raw `input` (str or items)
    - Returns the provider-typed ResponsesAPIResponse object unmodified
    """

    def __init__(
        self,
        *,
        model: str,
        api_key: str | None,
        base_url: str | None,
        api_version: str | None,
        timeout: int | None,
    ) -> None:
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.api_version = api_version
        self.timeout = timeout
        self.previous_response_id: str | None = None

    def send(
        self,
        *,
        messages: list[dict[str, Any]] | list[Message] | None = None,
        input: Any | None = None,
        tools: list[Any] | None = None,
        store: bool = True,
        previous_response_id: str | None = None,
        **kwargs,
    ) -> Any:
        if input is None and messages is None:
            raise ValueError("Either 'messages' or 'input' must be provided")

        # Prepare input payload
        if input is None:
            assert messages is not None
            if (
                messages
                and isinstance(messages, list)
                and isinstance(messages[0], Message)
            ):
                # Convert Message objects to simple dicts, then to Responses input items
                msg_dicts = [m.to_llm_dict() for m in messages]  # type: ignore[attr-defined]
            else:
                msg_dicts = messages  # type: ignore[assignment]
            input_payload: Any = messages_to_responses_items(msg_dicts)  # type: ignore[arg-type]
        else:
            input_payload = input

        # Build kwargs for Responses API
        call_kwargs = dict(kwargs)
        # tools passthrough (accept OpenAI-style definitions or already-converted)
        if tools is not None:
            call_kwargs["tools"] = tools

        # Enable persistence by default and propagate previous_response_id
        call_kwargs.setdefault("store", store)
        pri = previous_response_id or self.previous_response_id
        if pri is not None:
            call_kwargs["previous_response_id"] = pri

        # Reasoning defaults: prefer explicit kwargs from caller
        # We don't force include=... as providers can reject unsupported values

        # Perform call via LiteLLM
        resp = litellm_responses(
            model=self.model,
            api_key=self.api_key,
            api_base=self.base_url,
            api_version=self.api_version,
            timeout=self.timeout,
            input=input_payload,
            **call_kwargs,
        )

        # Persist previous_response_id if available
        try:
            rid = getattr(resp, "id", None)
            if isinstance(rid, str) and call_kwargs.get("store", False):
                self.previous_response_id = rid
        except Exception:
            pass

        return resp
