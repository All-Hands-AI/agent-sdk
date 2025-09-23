from unittest.mock import patch

from litellm.types.llms.openai import ResponsesAPIResponse
from pydantic import SecretStr

from openhands.sdk import LLM, Message, TextContent


def test_store_true_default_and_telemetry_called():
    llm = LLM(model="openai/gpt-5-test", api_key=SecretStr("x"))

    with (
        patch("openhands.sdk.llm.llm.litellm_responses") as mock_responses,
        patch.object(llm, "_telemetry") as mock_tel,
    ):
        payload = {
            "id": "resp_meta",
            "created_at": 0,
            "model": "gpt-5-test",
            "parallel_tool_calls": False,
            "tool_choice": "none",
            "tools": [],
            "top_p": 1.0,
            "output": [],
            "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        }
        mock_responses.return_value = ResponsesAPIResponse(**payload)

        llm.responses(messages=[Message(role="user", content=[TextContent(text="x")])])

        # Ensure store default was set on call
        assert mock_responses.call_count == 1
        call_kwargs = mock_responses.call_args.kwargs
        assert call_kwargs.get("store") is True

        # Telemetry should be invoked on request and response
        assert mock_tel.on_request.called
        assert mock_tel.on_response.called
