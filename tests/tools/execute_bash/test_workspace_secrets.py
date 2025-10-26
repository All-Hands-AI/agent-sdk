from typing import cast

from openhands.sdk.agent import Agent
from openhands.sdk.conversation.impl.local_conversation import LocalConversation
from openhands.sdk.llm import LLM
from openhands.sdk.tool import Tool, register_tool
from openhands.tools.execute_bash import BashTool
from openhands.tools.execute_bash.definition import ExecuteBashAction
from openhands.tools.execute_bash.impl import BashExecutor


def test_bash_tool_uses_workspace_secrets(tmp_path):
    register_tool("BashTool", BashTool)
    tools = [Tool(name="BashTool")]
    llm = LLM(model="gpt-4o-mini", api_key=None, usage_id="test-llm")
    agent = Agent(llm=llm, tools=tools)
    conv = LocalConversation(agent, workspace=str(tmp_path))

    # Update secrets via workspace directly (simulate LocalConversation.update_secrets)
    conv.workspace.secrets.update_secrets(
        {
            "API_TOKEN": "abc123",
        }
    )

    bash_tool = agent.tools_map["execute_bash"]
    executor = cast(BashExecutor, bash_tool.executor)

    # Ensure provider is wired implicitly from workspace
    assert executor.env_provider is not None
    env = executor.env_provider("echo $API_TOKEN")
    assert env == {"API_TOKEN": "abc123"}

    # Masking should work too
    action = ExecuteBashAction(command="echo $API_TOKEN")
    result = executor(action)
    assert "abc123" not in result.output
    assert "<secret-hidden>" in result.output
