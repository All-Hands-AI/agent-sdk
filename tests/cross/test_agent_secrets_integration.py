"""Tests for agent integration with secrets manager."""

from typing import cast

import pytest
from pydantic import SecretStr

from openhands.sdk.agent import Agent
from openhands.sdk.conversation import Conversation
from openhands.sdk.conversation.impl.local_conversation import LocalConversation
from openhands.sdk.llm import LLM
from openhands.sdk.tool import ToolSpec, register_tool
from openhands.tools.execute_bash import BashTool
from openhands.tools.execute_bash.definition import ExecuteBashAction
from openhands.tools.execute_bash.impl import BashExecutor


# -----------------------
# Fixtures
# -----------------------


@pytest.fixture
def llm() -> LLM:
    return LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"))


@pytest.fixture
def tools(tmp_path) -> list[ToolSpec]:
    register_tool("BashTool", BashTool)
    return [ToolSpec(name="BashTool", params={"working_dir": str(tmp_path)})]


@pytest.fixture
def agent(llm: LLM, tools: list[ToolSpec]) -> Agent:
    agent = Agent(llm=llm, tools=tools)
    agent._initialize()
    return agent


@pytest.fixture
def conversation(agent: Agent) -> LocalConversation:
    return LocalConversation(agent)


@pytest.fixture
def bash_executor(agent: Agent) -> BashExecutor:
    tools_map = agent.tools_map
    bash_tool = tools_map["execute_bash"]
    return cast(BashExecutor, bash_tool.executor)


@pytest.fixture
def agent_no_bash(llm: LLM) -> Agent:
    return Agent(llm=llm, tools=[])


@pytest.fixture
def conversation_no_bash(agent_no_bash: Agent) -> LocalConversation:
    return LocalConversation(agent_no_bash)


def test_agent_exports_secrets_to_bash(
    conversation: LocalConversation, bash_executor: BashExecutor, agent: Agent
):
    """Test that agent exports secrets to bash session."""
    # Add secrets to conversation
    conversation.update_secrets(
        {
            "API_KEY": "test-api-key",
            "DB_PASSWORD": "test-password",
        }
    )

    # Get the bash tool from agent
    bash_tool = agent.tools_map["execute_bash"]

    assert bash_tool is not None
    assert bash_tool.executor is not None

    # Test that secrets are available in bash session
    action = ExecuteBashAction(command="echo API_KEY=$API_KEY")
    result = bash_executor(action)
    # The output should be masked but the command should work
    assert "API_KEY=" in result.output
    assert result.metadata.exit_code == 0

    action = ExecuteBashAction(command="echo DB_PASSWORD=$DB_PASSWORD")
    result = bash_executor(action)
    assert "DB_PASSWORD=" in result.output
    assert result.metadata.exit_code == 0


def test_agent_exports_callable_secrets(
    conversation: LocalConversation, bash_executor: BashExecutor
):
    """Test that agent exports callable secrets to bash session."""

    # Add callable secrets
    def get_dynamic_token():
        return "dynamic-token-123"

    conversation.update_secrets(
        {
            "STATIC_KEY": "static-value",
            "DYNAMIC_TOKEN": get_dynamic_token,
        }
    )

    # Test that callable secrets are available in bash session
    action = ExecuteBashAction(command="echo DYNAMIC_TOKEN=$DYNAMIC_TOKEN")
    result = bash_executor(action)
    assert "DYNAMIC_TOKEN=" in result.output
    assert result.metadata.exit_code == 0


def test_agent_handles_failing_callable_secrets(
    conversation: LocalConversation, bash_executor: BashExecutor
):
    """Test that agent handles failing callable secrets gracefully."""

    # Add a failing callable secret
    def failing_secret():
        raise ValueError("Secret retrieval failed")

    conversation.update_secrets(
        {
            "WORKING_KEY": "working-value",
            "FAILING_KEY": failing_secret,
        }
    )

    # Working key should still be available
    action = ExecuteBashAction(command="echo WORKING_KEY=$WORKING_KEY")
    result = bash_executor(action)
    assert "WORKING_KEY=" in result.output
    assert result.metadata.exit_code == 0

    # Failing key should not be set (empty value)
    action = ExecuteBashAction(command="echo FAILING_KEY=$FAILING_KEY")
    result = bash_executor(action)
    assert "FAILING_KEY=" in result.output
    assert result.metadata.exit_code == 0


def test_agent_bash_works_without_secrets(
    conversation: LocalConversation, bash_executor: BashExecutor
):
    """Test that bash commands work normally when no secrets are referenced."""

    conversation.update_secrets({"API_KEY": "test-value"})

    # Test command that doesn't reference secrets
    action = ExecuteBashAction(command="echo hello world")
    result = bash_executor(action)
    assert "hello world" in result.output
    assert result.metadata.exit_code == 0


def test_agent_without_bash_throws_warning(llm):
    """Test that agent works correctly when no bash tools are present."""
    from unittest.mock import patch

    with patch("openhands.sdk.agent.agent.logger") as mock_logger:
        _ = Conversation(agent=Agent(llm=llm, tools=[]))

        # Check that the warning was logged
        mock_logger.warning.assert_called_once_with(
            "Skipped configuring bash tools secrets: missing bash tool"
        )


def test_agent_secrets_integration_workflow(
    conversation: LocalConversation, bash_executor: BashExecutor, agent: Agent
):
    """Test complete workflow of agent secrets integration."""

    # Add secrets with mixed types
    def get_auth_token():
        return "bearer-token-456"

    conversation.update_secrets(
        {
            "API_KEY": "static-api-key-123",
            "AUTH_TOKEN": get_auth_token,
            "DATABASE_URL": "postgresql://localhost/test",
        }
    )

    # Test that secrets are available in bash session
    action = ExecuteBashAction(command="echo API_KEY=$API_KEY")
    result = bash_executor(action)
    assert "API_KEY=" in result.output
    assert result.metadata.exit_code == 0

    # Test multiple secrets
    action = ExecuteBashAction(command="echo API_KEY=$API_KEY AUTH_TOKEN=$AUTH_TOKEN")
    result = bash_executor(action)
    assert "API_KEY=" in result.output
    assert "AUTH_TOKEN=" in result.output
    assert result.metadata.exit_code == 0

    # Test command without secrets
    action = ExecuteBashAction(command="echo hello world")
    result = bash_executor(action)
    assert "hello world" in result.output
    assert result.metadata.exit_code == 0

    # Update secrets and verify changes propagate
    conversation.update_secrets({"API_KEY": "updated-api-key-789"})

    # Test that updated secret is available
    action = ExecuteBashAction(command="echo API_KEY=$API_KEY")
    result = bash_executor(action)
    assert "API_KEY=" in result.output
    assert result.metadata.exit_code == 0


def test_mask_secrets(
    conversation: LocalConversation, bash_executor: BashExecutor, agent: Agent
):
    """Test that agent configures bash tools with env provider."""

    def dynamic_secret() -> str:
        return "dynamic-secret"

    # Add secrets to conversation
    conversation.update_secrets(
        {
            "API_KEY": "test-api-key",
            "DB_PASSWORD": dynamic_secret,
        }
    )

    try:
        action = ExecuteBashAction(command="echo $API_KEY")
        result = bash_executor(action)
        assert "test-api-key" not in result.output
        assert "<secret-hidden>" in result.output

        action = ExecuteBashAction(command="echo $DB_PASSWORD")
        result = bash_executor(action)
        assert "dynamic-secret" not in result.output
        assert "<secret-hidden>" in result.output

    finally:
        bash_executor.close()


def test_mask_changing_secrets(
    conversation: LocalConversation, bash_executor: BashExecutor, agent: Agent
):
    counter = 0

    def dynamic_secret() -> str:
        nonlocal counter
        counter += 1
        return f"changing-secret-{counter}"

    conversation.update_secrets(
        {
            "DB_PASSWORD": dynamic_secret,
        }
    )

    try:
        action = ExecuteBashAction(command="echo $DB_PASSWORD")
        result = bash_executor(action)
        assert "changing-secret" not in result.output
        assert "<secret-hidden>" in result.output

        action = ExecuteBashAction(command="echo $DB_PASSWORD")
        result = bash_executor(action)
        assert "changing-secret" not in result.output
        assert "<secret-hidden>" in result.output

    finally:
        bash_executor.close()


def test_masking_persists(
    conversation: LocalConversation, bash_executor: BashExecutor, agent: Agent
):
    counter = 0

    def dynamic_secret() -> str:
        nonlocal counter
        counter += 1
        return f"changing-secret-{counter}"

    # First update - should call function once and export the value
    conversation.update_secrets(
        {
            "DB_PASSWORD": dynamic_secret,
        }
    )

    try:
        # First bash execution - should use exported value and mask it
        action = ExecuteBashAction(command="echo $DB_PASSWORD")
        result = bash_executor(action)
        assert "changing-secret" not in result.output
        assert "<secret-hidden>" in result.output

        # Second bash execution - should still use same exported value and mask it
        action = ExecuteBashAction(command="echo $DB_PASSWORD")
        result = bash_executor(action)
        assert "changing-secret" not in result.output
        assert "<secret-hidden>" in result.output

        # Function should have been called only once during update_secrets
        assert counter == 1

        # Now update secrets again - this should call the function again
        conversation.update_secrets(
            {
                "DB_PASSWORD": dynamic_secret,
            }
        )

        # Function should have been called again
        assert counter == 2

    finally:
        bash_executor.close()
