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
    return LLM(
        model="gpt-4o-mini", api_key=SecretStr("test-key"), service_id="test-llm"
    )


@pytest.fixture
def tools() -> list[ToolSpec]:
    register_tool("BashTool", BashTool)
    return [ToolSpec(name="BashTool")]


@pytest.fixture
def agent(llm: LLM, tools: list[ToolSpec]) -> Agent:
    return Agent(llm=llm, tools=tools)


@pytest.fixture
def conversation(agent: Agent, tmp_path) -> LocalConversation:
    return LocalConversation(agent, working_dir=str(tmp_path))


@pytest.fixture
def bash_executor(conversation: LocalConversation) -> BashExecutor:
    tools_map = conversation.agent.tools_map
    bash_tool = tools_map["execute_bash"]
    return cast(BashExecutor, bash_tool.executor)


@pytest.fixture
def agent_no_bash(llm: LLM) -> Agent:
    return Agent(llm=llm, tools=[])


@pytest.fixture
def conversation_no_bash(agent_no_bash: Agent, tmp_path) -> LocalConversation:
    return LocalConversation(agent_no_bash, working_dir=str(tmp_path))


def test_agent_configures_bash_tools_env_provider(
    conversation: LocalConversation, bash_executor: BashExecutor, agent: Agent
):
    """Test that agent configures bash tools with env provider."""
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

    # Check that env_provider is configured
    bash_executor = cast(BashExecutor, bash_tool.executor)
    assert bash_executor.env_provider is not None

    # Test that env_provider works correctly
    env_vars = bash_executor.env_provider("echo $API_KEY")
    assert env_vars == {"API_KEY": "test-api-key"}

    env_vars = bash_executor.env_provider("echo $NOT_A_KEY")
    assert env_vars == {}


def test_agent_env_provider_with_callable_secrets(
    conversation: LocalConversation, bash_executor: BashExecutor
):
    """Test that agent env provider works with callable secrets."""

    # Add callable secrets
    def get_dynamic_token():
        return "dynamic-token-123"

    conversation.update_secrets(
        {
            "STATIC_KEY": "static-value",
            "DYNAMIC_TOKEN": get_dynamic_token,
        }
    )

    assert bash_executor.env_provider is not None
    env_vars = bash_executor.env_provider("export DYNAMIC_TOKEN=$DYNAMIC_TOKEN")
    assert env_vars == {"DYNAMIC_TOKEN": "dynamic-token-123"}


def test_agent_env_provider_handles_exceptions(
    conversation: LocalConversation, bash_executor: BashExecutor
):
    """Test that agent env provider handles exceptions gracefully."""

    # Add a failing callable secret
    def failing_secret():
        raise ValueError("Secret retrieval failed")

    conversation.update_secrets(
        {
            "WORKING_KEY": "working-value",
            "FAILING_KEY": failing_secret,
        }
    )

    assert bash_executor.env_provider is not None

    # Should not raise exception, should return empty dict
    env_vars = bash_executor.env_provider("export FAILING_KEY=$FAILING_KEY")
    assert env_vars == {}

    # Working key should still work
    env_vars = bash_executor.env_provider("export WORKING_KEY=$WORKING_KEY")
    assert env_vars == {"WORKING_KEY": "working-value"}


def test_agent_env_provider_no_matches(
    conversation: LocalConversation, bash_executor: BashExecutor
):
    """Test agent env provider when command has no secret matches."""

    conversation.update_secrets({"API_KEY": "test-value"})

    # Test env provider with command that doesn't reference secrets
    assert bash_executor.env_provider is not None
    env_vars = bash_executor.env_provider("echo hello world")

    assert env_vars == {}


def test_agent_without_bash_throws_warning(llm):
    """Test that agent works correctly when no bash tools are present."""
    from unittest.mock import patch

    with patch("openhands.sdk.agent.agent.logger") as mock_logger:
        _ = Conversation(agent=Agent(llm=llm, tools=[]))

        # Check that the warning was logged
        mock_logger.warning.assert_called_once_with(
            "Skipped wiring SecretsManager: missing bash tool"
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

    # Single secret
    assert bash_executor.env_provider is not None
    env_vars = bash_executor.env_provider("curl -H 'X-API-Key: $API_KEY'")
    assert env_vars == {"API_KEY": "static-api-key-123"}

    # Multiple secrets
    command = "export API_KEY=$API_KEY && export AUTH_TOKEN=$AUTH_TOKEN"
    assert bash_executor.env_provider is not None
    env_vars = bash_executor.env_provider(command)
    assert env_vars == {
        "API_KEY": "static-api-key-123",
        "AUTH_TOKEN": "bearer-token-456",
    }

    # No secrets referenced
    assert bash_executor.env_provider is not None
    env_vars = bash_executor.env_provider("echo hello world")
    assert env_vars == {}

    # Step 5: Update secrets and verify changes propagate
    conversation.update_secrets({"API_KEY": "updated-api-key-789"})

    assert bash_executor.env_provider is not None
    env_vars = bash_executor.env_provider("curl -H 'X-API-Key: $API_KEY'")
    assert env_vars == {"API_KEY": "updated-api-key-789"}


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
    raised_on_second = False

    def dynamic_secret() -> str:
        nonlocal counter, raised_on_second
        counter += 1

        if counter == 1:
            return f"changing-secret-{counter}"
        else:
            raised_on_second = True
            raise Exception("Blip occured, failed to refresh token")

    conversation.update_secrets(
        {
            "DB_PASSWORD": dynamic_secret,
        }
    )

    try:
        action = ExecuteBashAction(command="echo $DB_PASSWORD")
        result = bash_executor(action)
        print(result)
        assert "changing-secret" not in result.output
        assert "<secret-hidden>" in result.output

        action = ExecuteBashAction(command="echo $DB_PASSWORD")
        result = bash_executor(action)
        assert "changing-secret" not in result.output
        assert "<secret-hidden>" in result.output
        assert raised_on_second

    finally:
        bash_executor.close()
