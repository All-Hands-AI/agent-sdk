from unittest.mock import patch

from openhands.sdk import LLM, Conversation
from openhands.sdk.agent import Agent
from openhands.sdk.tool import Tool
from openhands.sdk.tool.registry import register_tool
from openhands.sdk.tool.spec import ToolSpec
from openhands.sdk.tool.tool import ActionBase, ObservationBase, ToolExecutor


class _Action(ActionBase):
    text: str


class _Obs(ObservationBase):
    out: str


class _Exec(ToolExecutor[_Action, _Obs]):
    def __call__(self, action: _Action) -> _Obs:
        return _Obs(out=action.text.upper())


def _make_tool() -> Tool:
    return Tool(
        name="upper",
        description="Uppercase",
        action_type=_Action,
        observation_type=_Obs,
        executor=_Exec(),
    )


def test_agent_initializes_tools_from_toolspec_locally(monkeypatch):
    # Register a simple local tool via registry
    register_tool("upper", _make_tool)

    llm = LLM(model="test-model")
    agent = Agent(llm=llm, tool_specs=[ToolSpec(name="upper")])

    # Build a conversation; this should call agent.initialize() internally
    convo = Conversation(agent=agent, visualize=False)

    # Access the agent's runtime tools via a small shim
    # (We don't rely on private internals; we verify init_state produced a system prompt
    # with tools included by checking that agent.step can access tools without error.)
    with patch.object(Agent, "step", wraps=agent.step):
        convo.send_message("hi")
        assert hasattr(agent, "initialize")
        agent.initialize()  # idempotent
        get_tools = getattr(agent, "get_tools")
        runtime_tools = get_tools()
        assert "upper" in runtime_tools
        assert "finish" in runtime_tools
        assert "think" in runtime_tools
