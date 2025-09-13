from typing import cast

from litellm.types.llms.openai import (
    ChatCompletionRedactedThinkingBlock,
    ChatCompletionThinkingBlock,
)
from litellm.types.utils import Message as LiteLLMMessage


# Helper builders that adapt to current LiteLLM TypedDict keys


def _tb(text: str, signature: str = "sig") -> ChatCompletionThinkingBlock:
    return cast(
        ChatCompletionThinkingBlock,
        {"type": "thinking", "thinking": text, "signature": signature},
    )


def _rtb(data: str) -> ChatCompletionRedactedThinkingBlock:
    return cast(
        ChatCompletionRedactedThinkingBlock,
        {"type": "redacted_thinking", "data": data},
    )


def test_message_from_litellm_message_thinking_blocks():
    from openhands.sdk.llm.message import Message

    litellm_message = LiteLLMMessage(role="assistant", content="Hello")
    # Inject typed thinking blocks on the LiteLLM message
    blocks: list[ChatCompletionThinkingBlock | ChatCompletionRedactedThinkingBlock] = [
        _tb("step 1"),
        _rtb("[redacted]"),
    ]
    litellm_message.thinking_blocks = blocks

    msg = Message.from_litellm_message(litellm_message)
    assert msg.thinking_blocks == blocks


def test_message_to_llm_dict_includes_thinking_blocks():
    from openhands.sdk.llm.message import Message, TextContent

    blocks: list[ChatCompletionThinkingBlock | ChatCompletionRedactedThinkingBlock] = [
        _tb("abc"),
    ]
    msg = Message(
        role="assistant", content=[TextContent(text="ok")], thinking_blocks=blocks
    )

    d = msg.to_llm_dict()
    assert d.get("thinking_blocks") == blocks


def test_combine_action_events_preserves_thinking_blocks():
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

    blocks: list[ChatCompletionThinkingBlock | ChatCompletionRedactedThinkingBlock] = [
        _tb("a")
    ]

    ev1 = ActionEvent(
        thought=[TextContent(text="thinking")],
        action=_TestAction(),
        tool_name="test_tool",
        tool_call_id="tc1",
        tool_call=tool_call_1,
        llm_response_id="resp-1",
        reasoning_content="rc",
        thinking_blocks=blocks,
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
    assert m.thinking_blocks == blocks


def test_non_native_fc_restores_thinking_blocks(monkeypatch):
    # Simulate NonNativeToolCallingMixin behavior directly
    from litellm.types.utils import Choices, ModelResponse, Usage

    from openhands.sdk.llm.mixins.non_native_fc import NonNativeToolCallingMixin
    from openhands.sdk.llm.utils.model_features import ModelFeatures

    class Host(NonNativeToolCallingMixin):
        model: str = "test-model"
        disable_stop_word: bool | None = None

        def is_function_calling_active(self) -> bool:
            return False

    # Mock get_features to indicate stop words supported
    monkeypatch.setattr(
        "openhands.sdk.llm.mixins.non_native_fc.get_features",
        lambda _model: ModelFeatures(
            supports_function_calling=False,
            supports_reasoning_effort=False,
            supports_prompt_cache=False,
            supports_stop_words=True,
        ),
    )

    host = Host()

    # Original non-fncall assistant message with thinking
    orig = LiteLLMMessage(role="assistant", content="hi")
    orig.reasoning_content = "rc"
    blocks: list[ChatCompletionThinkingBlock | ChatCompletionRedactedThinkingBlock] = [
        _tb("x")
    ]
    orig.thinking_blocks = blocks
    orig.provider_specific_fields = {"anthropic": {"thinking": "t"}}

    resp = ModelResponse(
        id="r1",
        choices=[Choices(index=0, finish_reason="stop", message=orig)],
        created=0,
        model="m",
        object="chat.completion",
        usage=Usage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
    )

    nonfn_msgs = [{"role": "user", "content": "u"}]
    tools: list = []

    out = host.post_response_prompt_mock(resp, nonfn_msgs, tools)
    choice0 = cast(Choices, out.choices[0])
    msg = choice0.message
    assert getattr(msg, "reasoning_content", None) == "rc"
    assert getattr(msg, "thinking_blocks", None) == blocks
    assert getattr(msg, "provider_specific_fields", None) == {
        "anthropic": {"thinking": "t"}
    }
