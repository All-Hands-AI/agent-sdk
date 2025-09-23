from typing import Any
from unittest.mock import patch

import pytest
from litellm.types.llms.openai import ResponsesAPIResponse
from litellm.types.utils import Choices, Message as LiteLLMMessage, ModelResponse, Usage
from pydantic import SecretStr

from openhands.sdk import LLM, Agent, Conversation, Message, TextContent
from openhands.sdk.tool import ToolSpec, register_tool
from openhands.tools.execute_bash import BashTool
from openhands.tools.str_replace_editor import FileEditorTool


@pytest.fixture()
def agent_and_conversation(tmp_path):
    # Tools as in examples
    register_tool("BashTool", BashTool)
    register_tool("FileEditorTool", FileEditorTool)
    tool_specs = [
        ToolSpec(name="BashTool", params={"working_dir": str(tmp_path)}),
        ToolSpec(name="FileEditorTool"),
    ]

    # LLM defaults to non-Responses model
    llm = LLM(model="claude-sonnet-4", api_key=SecretStr("test"))
    agent = Agent(llm=llm, tools=tool_specs)
    conv = Conversation(agent=agent, callbacks=[])
    return agent, conv, tool_specs


def _send_simple_user_msg(conv: Conversation):
    conv.send_message(
        message=Message(role="user", content=[TextContent(text="test request")])
    )


def test_routes_chat_path_when_unsupported(agent_and_conversation):
    agent, conv, _ = agent_and_conversation

    with patch("openhands.sdk.llm.llm.litellm_completion") as mock_completion:
        # Mock a plain text response
        resp = ModelResponse(
            id="r1",
            choices=[
                Choices(
                    index=0,
                    message=LiteLLMMessage(role="assistant", content="ok"),
                    finish_reason="stop",
                )
            ],
            usage=Usage(prompt_tokens=1, completion_tokens=2, total_tokens=3),
        )
        mock_completion.return_value = resp

        _send_simple_user_msg(conv)
        conv.run()

        assert mock_completion.call_count == 1


def test_routes_responses_path_for_gpt5(agent_and_conversation):
    agent, conv, tool_specs = agent_and_conversation
    # Recreate agent with gpt-5* model and same tools to respect frozen model
    agent = Agent(
        llm=LLM(model="openai/gpt-5-test", api_key=SecretStr("x")), tools=tool_specs
    )
    conv = Conversation(agent=agent, callbacks=[])

    # Patch litellm.responses used in LLM.responses
    with patch("openhands.sdk.llm.llm.litellm_responses") as mock_responses:
        # Minimal Responses payload: assistant text only
        payload: dict[str, Any] = {
            "id": "resp_1",
            "created_at": 0,
            "model": "gpt-5-test",
            "parallel_tool_calls": True,
            "tool_choice": "auto",
            "tools": [],
            "top_p": 1.0,
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "status": "completed",
                    "content": [{"type": "output_text", "text": "ok from responses"}],
                }
            ],
            "usage": {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3},
        }
        mock_responses.return_value = ResponsesAPIResponse(**payload)

        _send_simple_user_msg(conv)
        conv.run()

        assert mock_responses.call_count == 1
