"""Tests for agent integration with secrets manager."""

from typing import cast
from unittest.mock import patch

import pytest
from pydantic import SecretStr

from openhands.sdk.agent import Agent
from openhands.sdk.conversation import Conversation
from openhands.sdk.conversation.impl.local_conversation import LocalConversation
from openhands.sdk.conversation.secret_source import LookupSecret, SecretSource
from openhands.sdk.llm import LLM
from openhands.sdk.tool import Tool, register_tool
from openhands.tools.execute_bash import BashTool
from openhands.tools.execute_bash.definition import ExecuteBashAction
from openhands.tools.execute_bash.impl import BashExecutor


# -----------------------
# Fixtures
# -----------------------


@pytest.fixture
def llm() -> LLM:
    return LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"), usage_id="test-llm")


@pytest.fixture
def tools() -> list[Tool]:
    register_tool("BashTool", BashTool)
    return [Tool(name="BashTool")]


@pytest.fixture
def agent(llm: LLM, tools: list[Tool]) -> Agent:
    return Agent(llm=llm, tools=tools)


@pytest.fixture
def conversation(agent: Agent, tmp_path) -> LocalConversation:
    return LocalConversation(agent, workspace=str(tmp_path))


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
    return LocalConversation(agent_no_bash, workspace=str(tmp_path))


def test_agent_configures_bash_tools_env_provider(
    conversation: LocalConversation, bash_executor: BashExecutor, agent: Agent
):
    """Test that bash executor works with conversation secrets."""
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

    # Test that secrets are accessible via conversation
    secrets_manager = conversation.state.secrets_manager
    env_vars = secrets_manager.get_secrets_as_env_vars("echo $API_KEY")
    assert env_vars == {"API_KEY": "test-api-key"}

    env_vars = secrets_manager.get_secrets_as_env_vars("echo $NOT_A_KEY")
    assert env_vars == {}


def test_agent_env_provider_with_callable_secrets(
    conversation: LocalConversation, bash_executor: BashExecutor
):
    """Test that conversation secrets work with callable secrets."""

    # Add callable secrets
    class MySecretSource(SecretSource):
        def get_value(self):
            return "dynamic-token-123"

    conversation.update_secrets(
        {
            "STATIC_KEY": "static-value",
            "DYNAMIC_TOKEN": MySecretSource(),
        }
    )

    secrets_manager = conversation.state.secrets_manager
    env_vars = secrets_manager.get_secrets_as_env_vars(
        "export DYNAMIC_TOKEN=$DYNAMIC_TOKEN"
    )
    assert env_vars == {"DYNAMIC_TOKEN": "dynamic-token-123"}


def test_agent_env_provider_handles_exceptions(
    conversation: LocalConversation, bash_executor: BashExecutor
):
    """Test that conversation secrets handle exceptions gracefully."""

    # Add a failing callable secret
    class MyFailingSecretSource(SecretSource):
        def get_value(self):
            raise ValueError("Secret retrieval failed")

    conversation.update_secrets(
        {
            "WORKING_KEY": "working-value",
            "FAILING_KEY": MyFailingSecretSource(),
        }
    )

    secrets_manager = conversation.state.secrets_manager

    # Should not raise exception, should return empty dict
    env_vars = secrets_manager.get_secrets_as_env_vars(
        "export FAILING_KEY=$FAILING_KEY"
    )
    assert env_vars == {}

    # Working key should still work
    env_vars = secrets_manager.get_secrets_as_env_vars(
        "export WORKING_KEY=$WORKING_KEY"
    )
    assert env_vars == {"WORKING_KEY": "working-value"}


def test_agent_env_provider_no_matches(
    conversation: LocalConversation, bash_executor: BashExecutor
):
    """Test conversation secrets when command has no secret matches."""

    conversation.update_secrets({"API_KEY": "test-value"})

    # Test secrets manager with command that doesn't reference secrets
    secrets_manager = conversation.state.secrets_manager
    env_vars = secrets_manager.get_secrets_as_env_vars("echo hello world")

    assert env_vars == {}


def test_agent_without_bash_throws_warning(llm):
    """Test that agent works correctly when no bash tools are present."""
    # This test is no longer relevant since we removed
    # _configure_bash_tools_env_provider
    # Agent no longer logs warnings about missing bash tools
    # Creating conversation without bash tools should work fine
    conversation = Conversation(agent=Agent(llm=llm, tools=[]))
    assert conversation is not None
    conversation.close()


def test_agent_secrets_integration_workflow(
    conversation: LocalConversation, bash_executor: BashExecutor, agent: Agent
):
    """Test complete workflow of conversation secrets integration."""

    # Add secrets with mixed types

    with patch("httpx.get") as mock_get:
        mock_get.return_value.text = "bearer-token-456"

        conversation.update_secrets(
            {
                "API_KEY": "static-api-key-123",
                "AUTH_TOKEN": LookupSecret(url="https://my-idp.com/"),
                "DATABASE_URL": "postgresql://localhost/test",
            }
        )

        secrets_manager = conversation.state.secrets_manager

        # Single secret
        env_vars = secrets_manager.get_secrets_as_env_vars(
            "curl -H 'X-API-Key: $API_KEY'"
        )
        assert env_vars == {"API_KEY": "static-api-key-123"}

        # Multiple secrets
        command = "export API_KEY=$API_KEY && export AUTH_TOKEN=$AUTH_TOKEN"
        env_vars = secrets_manager.get_secrets_as_env_vars(command)
        assert env_vars == {
            "API_KEY": "static-api-key-123",
            "AUTH_TOKEN": "bearer-token-456",
        }

        # No secrets referenced
        env_vars = secrets_manager.get_secrets_as_env_vars("echo hello world")
        assert env_vars == {}

    # Step 5: Update secrets and verify changes propagate
    conversation.update_secrets({"API_KEY": "updated-api-key-789"})

    secrets_manager = conversation.state.secrets_manager
    env_vars = secrets_manager.get_secrets_as_env_vars("curl -H 'X-API-Key: $API_KEY'")
    assert env_vars == {"API_KEY": "updated-api-key-789"}


def test_mask_secrets(
    conversation: LocalConversation, bash_executor: BashExecutor, agent: Agent
):
    """Test that bash executor masks secrets when conversation is passed."""

    class MyDynamicSecretSource(SecretSource):
        def get_value(self):
            return "dynamic-secret"

    # Add secrets to conversation
    conversation.update_secrets(
        {
            "API_KEY": "test-api-key",
            "DB_PASSWORD": MyDynamicSecretSource(),
        }
    )

    try:
        action = ExecuteBashAction(command="echo $API_KEY")
        result = bash_executor(action, conversation=conversation)
        assert "test-api-key" not in result.output
        assert "<secret-hidden>" in result.output

        action = ExecuteBashAction(command="echo $DB_PASSWORD")
        result = bash_executor(action, conversation=conversation)
        assert "dynamic-secret" not in result.output
        assert "<secret-hidden>" in result.output

    finally:
        bash_executor.close()


def test_mask_changing_secrets(
    conversation: LocalConversation, bash_executor: BashExecutor, agent: Agent
):
    class MyChangingDynamicSecretSource(SecretSource):
        counter: int = 0

        def get_value(self):
            self.counter += 1
            return f"changing-secret-{self.counter}"

    conversation.update_secrets(
        {
            "DB_PASSWORD": MyChangingDynamicSecretSource(),
        }
    )

    try:
        action = ExecuteBashAction(command="echo $DB_PASSWORD")
        result = bash_executor(action, conversation=conversation)
        assert "changing-secret" not in result.output
        assert "<secret-hidden>" in result.output

        action = ExecuteBashAction(command="echo $DB_PASSWORD")
        result = bash_executor(action, conversation=conversation)
        assert "changing-secret" not in result.output
        assert "<secret-hidden>" in result.output

    finally:
        bash_executor.close()


def test_masking_persists(
    conversation: LocalConversation, bash_executor: BashExecutor, agent: Agent
):
    class MyChangingFailingDynamicSecretSource(SecretSource):
        counter: int = 0
        raised_on_second: bool = False

        def get_value(self):
            self.counter += 1
            if self.counter == 1:
                return f"changing-secret-{self.counter}"
            else:
                self.raised_on_second = True
                raise Exception("Blip occured, failed to refresh token")

    dynamic_secret = MyChangingFailingDynamicSecretSource()
    conversation.update_secrets(
        {
            "DB_PASSWORD": dynamic_secret,
        }
    )

    try:
        action = ExecuteBashAction(command="echo $DB_PASSWORD")
        result = bash_executor(action, conversation=conversation)
        print(result)
        assert "changing-secret" not in result.output
        assert "<secret-hidden>" in result.output

        action = ExecuteBashAction(command="echo $DB_PASSWORD")
        result = bash_executor(action, conversation=conversation)
        assert "changing-secret" not in result.output
        assert "<secret-hidden>" in result.output
        assert dynamic_secret.raised_on_second

    finally:
        bash_executor.close()
