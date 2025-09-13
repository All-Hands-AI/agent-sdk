from litellm.types.utils import Message as LiteLLMMessage


def test_message_from_litellm_message_provider_specific_fields():
    from openhands.sdk.llm.message import Message

    litellm_message = LiteLLMMessage(role="assistant", content="Hello")
    litellm_message.provider_specific_fields = {
        "anthropic": {
            "thinking": "thoughts...",
            "thinking_blocks": [
                {"id": "t1", "type": "thinking", "text": "block 1"},
                {"id": "t2", "type": "thinking", "text": "block 2"},
            ],
        }
    }

    msg = Message.from_litellm_message(litellm_message)
    assert msg.provider_specific_fields == litellm_message.provider_specific_fields


def test_message_to_llm_dict_includes_provider_specific_fields():
    from openhands.sdk.llm.message import Message, TextContent

    psf = {"anthropic": {"thinking": "hidden", "thinking_blocks": []}}
    msg = Message(
        role="assistant",
        content=[TextContent(text="ok")],
        provider_specific_fields=psf,
    )

    d = msg.to_llm_dict()
    assert d.get("provider_specific_fields") == psf


def test_combine_action_events_preserves_provider_specific_fields():
    from litellm import ChatCompletionMessageToolCall
    from litellm.types.utils import Function

    from openhands.sdk.event.base import LLMConvertibleEvent
    from openhands.sdk.event.llm_convertible import ActionEvent
    from openhands.sdk.llm.message import TextContent
    from openhands.sdk.tool import ActionBase

    class _TestAction(ActionBase):
        action: str = "test"

    tool_call_1 = ChatCompletionMessageToolCall(
        id="tc1",
        function=Function(name="test_tool", arguments="{}"),
        type="function",
    )
    tool_call_2 = ChatCompletionMessageToolCall(
        id="tc2",
        function=Function(name="test_tool", arguments="{}"),
        type="function",
    )

    psf = {"anthropic": {"thinking": "some", "thinking_blocks": [{"id": "x"}]}}

    ev1 = ActionEvent(
        thought=[TextContent(text="thinking")],
        action=_TestAction(),
        tool_name="test_tool",
        tool_call_id="tc1",
        tool_call=tool_call_1,
        llm_response_id="resp-1",
        reasoning_content="rc",
        provider_specific_fields=psf,
    )
    ev2 = ActionEvent(
        thought=[],
        action=_TestAction(),
        tool_name="test_tool",
        tool_call_id="tc2",
        tool_call=tool_call_2,
        llm_response_id="resp-1",
    )

    msgs = LLMConvertibleEvent.events_to_messages([ev1, ev2])
    assert len(msgs) == 1
    m = msgs[0]
    assert m.provider_specific_fields == psf
