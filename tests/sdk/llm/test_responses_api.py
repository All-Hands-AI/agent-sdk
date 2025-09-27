"""Tests for non-streaming Responses API integration (GPT-5 family).

Covers:
- Routing by model (Agent calls LLM.responses)
- previous_response_id propagation across turns
- Strict mismatch error when previous_response_id set on non-supported model
- Tool-calls and reasoning parsing on LLM.responses
- Telemetry usage mapping on LLM.responses
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from litellm import ResponsesAPIResponse
from litellm.types.utils import Usage
from openai.types.responses.response_function_tool_call import (
    ResponseFunctionToolCall,
)
from openai.types.responses.response_output_message import ResponseOutputMessage
from openai.types.responses.response_reasoning_item import ResponseReasoningItem
from pydantic import SecretStr

from openhands.sdk import LLM, Agent, Conversation, Message, TextContent


def make_responses_obj(
    *,
    id: str = "resp_1",
    output_text: str | None = "Hello",
    output: list[Any] | None = None,
    usage: Usage | None = None,
) -> ResponsesAPIResponse:
    # Build a minimal, valid ResponsesAPIResponse payload
    payload: dict[str, Any] = {
        "id": id,
        "created_at": 0,
        "output": output
        if output is not None
        else [
            ResponseOutputMessage(
                id="om_1",
                content=[],
                role="assistant",
                status="completed",
                type="message",
            )
        ],
        "parallel_tool_calls": True,
        "tool_choice": "auto",
        "tools": [],
        "top_p": None,
    }
    if usage is not None:
        # Map litellm Usage to ResponseAPIUsage shape
        payload["usage"] = {
            "input_tokens": usage.prompt_tokens,
            "output_tokens": usage.completion_tokens,
            "total_tokens": usage.total_tokens,
            "input_tokens_details": None,
            "output_tokens_details": None,
        }
    # litellm's ResponsesAPIResponse will validate and coerce this dict
    obj = ResponsesAPIResponse.model_validate(payload)
    # Attach convenience attribute output_text so LLM.responses can read it
    setattr(obj, "output_text", output_text or "")
    # Provide a dict-shaped usage for Telemetry._record_usage (expects litellm Usage)
    if getattr(obj, "usage", None) is not None:
        u = obj.usage
        try:
            prompt = getattr(u, "input_tokens", None)
            completion = getattr(u, "output_tokens", None)
            total = getattr(u, "total_tokens", None)
            setattr(
                obj,
                "usage",
                {
                    "prompt_tokens": int(prompt) if prompt is not None else 0,
                    "completion_tokens": int(completion)
                    if completion is not None
                    else 0,
                    "total_tokens": int(total) if total is not None else 0,
                    "prompt_tokens_details": None,
                    "completion_tokens_details": None,
                },
            )
        except Exception:
            pass
    return obj


class _FnCall(ResponseFunctionToolCall):
    def __init__(self, call_id: str, name: str, arguments: str) -> None:
        super().__init__(
            arguments=arguments,
            call_id=call_id,
            name=name,
            type="function_call",
            id=f"fc_{call_id}",
            status="completed",
        )


def make_reasoning(
    summary_texts: list[str] | None = None,
    content_texts: list[str] | None = None,
) -> ResponseReasoningItem:
    return ResponseReasoningItem.model_validate(
        {
            "id": "rs_1",
            "summary": [
                {"type": "summary_text", "text": t} for t in (summary_texts or [])
            ],
            "content": [
                {"type": "reasoning_text", "text": t} for t in (content_texts or [])
            ],
            "type": "reasoning",
            "status": "completed",
        }
    )


@patch("openhands.sdk.llm.llm.litellm.responses")
def test_agent_routes_to_responses_and_sets_previous_id(mock_responses):
    # Arrange: mock a simple text response (no tool-calls)
    mock_responses.return_value = make_responses_obj(id="resp_1", output_text="Hi")

    llm = LLM(model="gpt-5", service_id="test-llm", api_key=SecretStr("k"))
    agent = Agent(llm=llm, tools=[])
    conv = Conversation(agent=agent)

    conv.send_message(Message(role="user", content=[TextContent(text="Hello")]))

    # Act
    conv.run()

    # Assert: LLM.responses called once; state.previous_response_id set
    assert mock_responses.call_count == 1
    kwargs = mock_responses.call_args.kwargs
    assert kwargs.get("model") == "gpt-5"
    assert (
        "previous_response_id" not in kwargs or kwargs["previous_response_id"] is None
    )
    assert conv.state.previous_response_id == "resp_1"


@patch("openhands.sdk.llm.llm.litellm.responses")
def test_previous_response_id_propagates_to_next_turn(mock_responses):
    # First turn -> resp_1, second turn -> resp_2
    mock_responses.side_effect = [
        make_responses_obj(id="resp_1", output_text="Step1"),
        make_responses_obj(id="resp_2", output_text="Step2"),
    ]

    llm = LLM(model="gpt-5-mini", service_id="test-llm", api_key=SecretStr("k"))
    agent = Agent(llm=llm, tools=[])
    conv = Conversation(agent=agent)

    # First user turn
    conv.send_message(Message(role="user", content=[TextContent(text="Hi")]))
    conv.run()
    assert conv.state.previous_response_id == "resp_1"

    # Second user turn (new message) should include previous_response_id
    conv.send_message(Message(role="user", content=[TextContent(text="Next")]))
    conv.run()

    assert conv.state.previous_response_id == "resp_2"
    # Verify second call included previous_response_id="resp_1"
    assert mock_responses.call_count == 2
    second_kwargs = mock_responses.call_args_list[1].kwargs
    assert second_kwargs.get("previous_response_id") == "resp_1"


def test_strict_mismatch_error_on_non_supported_model_with_prev_id():
    # No patch needed; error is raised before transport call
    llm = LLM(model="gpt-4o", service_id="test-llm", api_key=SecretStr("k"))
    agent = Agent(llm=llm, tools=[])
    conv = Conversation(agent=agent)

    # Seed previous_response_id manually to simulate continuation on non-supported model
    conv.state.previous_response_id = "resp_999"
    conv.send_message(Message(role="user", content=[TextContent(text="Hello")]))

    with pytest.raises(
        RuntimeError,
        match="previous_response_id is set but model lacks Responses support",
    ):
        conv.run()


@patch("openhands.sdk.llm.llm.litellm.responses")
def test_llm_responses_parses_tool_calls_and_reasoning(mock_responses):
    # Arrange: function-call + reasoning blocks
    items = [
        _FnCall(call_id="call_1", name="echo", arguments='{"text":"hi"}'),
        make_reasoning(summary_texts=["plan"], content_texts=["think1", "think2"]),
    ]
    mock_responses.return_value = make_responses_obj(
        id="resp_1", output_text="ok", output=items
    )

    llm = LLM(model="gpt-5", service_id="test-llm", api_key=SecretStr("k"))

    # Act
    out = llm.responses(instructions="sys", inputs=[], tools=None)

    # Assert
    msg = out.message
    assert msg.tool_calls is not None and len(msg.tool_calls) == 1
    tc = msg.tool_calls[0]
    assert (
        tc.id == "call_1" and tc.name == "echo" and tc.arguments_json == '{"text":"hi"}'
    )
    assert msg.reasoning_content is not None
    assert "plan" in msg.reasoning_content and "think1" in msg.reasoning_content


@patch("openhands.sdk.llm.llm.litellm.responses")
def test_llm_responses_telemetry_usage_mapping(mock_responses):
    usage = Usage(prompt_tokens=7, completion_tokens=3, total_tokens=10)
    mock_responses.return_value = make_responses_obj(
        id="resp_tele", output_text="x", usage=usage
    )

    llm = LLM(model="gpt-5", service_id="test-llm", api_key=SecretStr("k"))

    _ = llm.responses(instructions="sys", inputs=[], tools=None)

    # Telemetry should have recorded a token usage entry
    m = llm.metrics
    assert len(m.token_usages) >= 1
    last = m.token_usages[-1]
    assert last.prompt_tokens == 7
    assert last.completion_tokens == 3
