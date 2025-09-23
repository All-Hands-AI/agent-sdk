from __future__ import annotations

from typing import Any
from unittest.mock import patch

from litellm.types.llms.openai import ResponsesAPIResponse
from pydantic import SecretStr

from openhands.sdk import LLM, Agent, Conversation, Message, TextContent


def _mk_agent():
    llm = LLM(model="openai/gpt-5-test", api_key=SecretStr("x"))
    return Agent(llm=llm, tools=[])


def _run(conv: Conversation):
    conv.send_message(message=Message(role="user", content=[TextContent(text="t")]))
    conv.run()


def test_parse_text_and_reasoning_and_tool_calls():
    agent = _mk_agent()
    conv = Conversation(agent=agent, callbacks=[])

    with patch("openhands.sdk.llm.llm.litellm_responses") as mock_responses:
        payload: dict[str, Any] = {
            "id": "resp_2",
            "created_at": 0,
            "model": "gpt-5-test",
            "parallel_tool_calls": True,
            "tool_choice": "auto",
            "tools": [],
            "top_p": 1.0,
            "output": [
                {
                    "type": "reasoning",
                    "id": "r",
                    "status": "completed",
                    "content": [{"type": "output_text", "text": "think 1"}],
                    "summary": [{"type": "summary_text", "text": "sum"}],
                },
                {
                    "type": "message",
                    "id": "m",
                    "role": "assistant",
                    "status": "completed",
                    "content": [
                        {"type": "output_text", "text": "final text"},
                        {"type": "output_text", "text": "more"},
                    ],
                },
                {
                    "type": "function_call",
                    "name": "finish",
                    "arguments": '{"message": "done"}',
                    "call_id": "tc_1",
                },
            ],
            "usage": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
        }
        mock_responses.return_value = ResponsesAPIResponse(**payload)

        _run(conv)

    # Last event should be an action (finish) queued and executed by Agent
    # We verify through conversation state: agent status should be FINISHED
    from openhands.sdk.conversation.state import AgentExecutionStatus

    assert conv.state.agent_status in {
        AgentExecutionStatus.FINISHED,
        AgentExecutionStatus.WAITING_FOR_CONFIRMATION,
    }


def test_parse_no_tools_message_only_reasoning():
    agent = _mk_agent()
    conv = Conversation(agent=agent, callbacks=[])

    with patch("openhands.sdk.llm.llm.litellm_responses") as mock_responses:
        payload: dict[str, Any] = {
            "id": "resp_3",
            "created_at": 0,
            "model": "gpt-5-test",
            "parallel_tool_calls": False,
            "tool_choice": "none",
            "tools": [],
            "top_p": 1.0,
            "output": [
                {
                    "type": "reasoning",
                    "id": "r2",
                    "status": "completed",
                    "content": [{"type": "output_text", "text": "internal"}],
                },
                {
                    "type": "message",
                    "id": "m2",
                    "role": "assistant",
                    "status": "completed",
                    "content": [
                        {"type": "output_text", "text": "hello"},
                    ],
                },
            ],
            "usage": {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3},
        }
        mock_responses.return_value = ResponsesAPIResponse(**payload)

        _run(conv)

    # Conversation should have produced a terminal message event (no tools)
    from openhands.sdk.conversation.state import AgentExecutionStatus

    assert conv.state.agent_status == AgentExecutionStatus.FINISHED


def test_parse_image_generation_output():
    agent = _mk_agent()
    conv = Conversation(agent=agent, callbacks=[])

    with patch("openhands.sdk.llm.llm.litellm_responses") as mock_responses:
        payload: dict[str, Any] = {
            "id": "resp_img",
            "created_at": 0,
            "model": "gpt-5-test",
            "parallel_tool_calls": False,
            "tool_choice": "none",
            "tools": [],
            "top_p": 1.0,
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "status": "completed",
                    "content": [{"type": "output_text", "text": "here is an image"}],
                },
                {
                    "type": "image_generation_call",
                    "id": "img1",
                    "status": "completed",
                    "result": "https://example.com/image.png",
                },
            ],
            "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        }
        mock_responses.return_value = ResponsesAPIResponse(**payload)

        # Drive the conversation
        _run(conv)

        # Check last event: message with image surfaced

        events = conv.state.events
        from openhands.sdk.event.llm_convertible import MessageEvent as _MessageEvent

        msg_events = [
            e
            for e in events
            if isinstance(e, _MessageEvent) and e.llm_message.role == "assistant"
        ]
        assert msg_events, "No assistant MessageEvent found"
        last_msg_event = msg_events[-1]
        msg = last_msg_event.llm_message
        assert any(getattr(c, "type", None) == "image" for c in msg.content)


def test_parse_multiple_images_and_mixed_content_order():
    agent = _mk_agent()
    conv = Conversation(agent=agent, callbacks=[])

    with patch("openhands.sdk.llm.llm.litellm_responses") as mock_responses:
        payload: dict[str, Any] = {
            "id": "resp_img_multi",
            "created_at": 0,
            "model": "gpt-5-test",
            "parallel_tool_calls": False,
            "tool_choice": "none",
            "tools": [],
            "top_p": 1.0,
            "output": [
                {
                    "type": "message",
                    "id": "m3",
                    "role": "assistant",
                    "status": "completed",
                    "content": [
                        {"type": "output_text", "text": "first text"},
                        {"type": "output_text", "text": "second text"},
                    ],
                },
                {
                    "type": "image_generation_call",
                    "id": "img1",
                    "status": "completed",
                    "result": "https://example.com/image1.png",
                },
                {
                    "type": "image_generation_call",
                    "id": "img2",
                    "status": "completed",
                    "result": "https://example.com/image2.png",
                },
            ],
            "usage": {"input_tokens": 2, "output_tokens": 3, "total_tokens": 5},
        }
        mock_responses.return_value = ResponsesAPIResponse(**payload)

        _run(conv)

        events = conv.state.events
        from openhands.sdk.event.llm_convertible import MessageEvent as _MessageEvent

        msg_events = [
            e
            for e in events
            if isinstance(e, _MessageEvent) and e.llm_message.role == "assistant"
        ]
        assert msg_events, "No assistant MessageEvent found"
        last_msg_event = msg_events[-1]
        msg = last_msg_event.llm_message
        # Validate text merged then images appended
        from openhands.sdk import TextContent as _TextContent

        texts = [c.text for c in msg.content if isinstance(c, _TextContent)]
        assert "first text" in texts[0] and "second text" in texts[0]
        from openhands.sdk import ImageContent as _ImageContent

        images = [c for c in msg.content if isinstance(c, _ImageContent)]
        urls = [u for c in images for u in getattr(c, "image_urls", [])]
        assert urls == [
            "https://example.com/image1.png",
            "https://example.com/image2.png",
        ]
