"""Tests for SystemPromptEvent tools population and security_risk schema."""

from __future__ import annotations

import json

from openhands.sdk.event.llm_convertible import SystemPromptEvent
from openhands.sdk.llm import TextContent
from openhands.sdk.tool.schema import ActionBase
from openhands.sdk.tool.tool import Tool


class _SimpleArgs(ActionBase):
    foo: str


def _make_tool(add_security: bool = False):
    tool = Tool(
        name="simple_tool",
        description="Simple test tool",
        action_type=_SimpleArgs,
    )
    return tool.to_openai_tool(add_security_risk_prediction=add_security)


def test_system_prompt_event_has_tools_visualization():
    tools = [_make_tool(add_security=False)]
    event = SystemPromptEvent(
        source="agent",
        system_prompt=TextContent(text="You are a helpful assistant."),
        tools=tools,
    )

    # Basic checks
    assert len(event.tools) == 1
    viz = event.visualize
    assert "Tools Available: 1" in viz.plain


def test_system_prompt_event_tool_parameters_security_risk_included_when_enabled():
    tools = [_make_tool(add_security=True)]
    event = SystemPromptEvent(
        source="agent",
        system_prompt=TextContent(text="You are a helpful assistant."),
        tools=tools,
    )

    assert len(event.tools) == 1
    fn = event.tools[0]["function"]
    assert isinstance(fn, dict)
    assert "parameters" in fn
    params = fn["parameters"]
    assert isinstance(params, dict)
    # parameters is a JSON schema dict; properties should include security_risk
    properties = params.get("properties") or {}
    assert "security_risk" in properties

    # Also ensure the schema is serializable to JSON
    json.dumps(params)
