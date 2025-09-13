"""Tests for agent integration with secrets manager."""

import tempfile
from typing import cast

from pydantic import SecretStr

from openhands.sdk.agent import Agent
from openhands.sdk.conversation import Conversation
from openhands.sdk.llm import LLM
from openhands.sdk.tool import Tool
from openhands.tools import BashTool
from openhands.tools.execute_bash.impl import BashExecutor


def test_agent_configures_bash_tools_env_provider():
    """Test that agent configures bash tools with env provider."""
    # Create LLM and tools
    llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"))

    with tempfile.TemporaryDirectory() as temp_dir:
        tools = [BashTool.create(working_dir=temp_dir)]

        # Create agent and conversation
        agent = Agent(llm=llm, tools=tools)
        conversation = Conversation(agent)

        # Add secrets to conversation
        conversation.update_secrets(
            {
                "API_KEY": "test-api-key",
                "DB_PASSWORD": "test-password",
            }
        )

        # Get the bash tool from agent
        tools_dict = cast(dict[str, Tool], agent.tools)
        bash_tool = tools_dict["execute_bash"]

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


def test_agent_env_provider_with_callable_secrets():
    """Test that agent env provider works with callable secrets."""
    llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"))

    with tempfile.TemporaryDirectory() as temp_dir:
        tools = [BashTool.create(working_dir=temp_dir)]

        agent = Agent(llm=llm, tools=tools)
        conversation = Conversation(agent)

        # Add callable secrets
        def get_dynamic_token():
            return "dynamic-token-123"

        conversation.update_secrets(
            {
                "STATIC_KEY": "static-value",
                "DYNAMIC_TOKEN": get_dynamic_token,
            }
        )

        # Get bash tool and test env provider
        tools_dict = cast(dict[str, Tool], agent.tools)
        bash_tool = tools_dict["execute_bash"]
        bash_executor = cast(BashExecutor, bash_tool.executor)
        assert bash_executor.env_provider is not None
        env_vars = bash_executor.env_provider("export DYNAMIC_TOKEN=$DYNAMIC_TOKEN")

        assert env_vars == {"DYNAMIC_TOKEN": "dynamic-token-123"}


def test_agent_env_provider_handles_exceptions():
    """Test that agent env provider handles exceptions gracefully."""
    llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"))

    with tempfile.TemporaryDirectory() as temp_dir:
        tools = [BashTool.create(working_dir=temp_dir)]

        agent = Agent(llm=llm, tools=tools)
        conversation = Conversation(agent)

        # Add a failing callable secret
        def failing_secret():
            raise ValueError("Secret retrieval failed")

        conversation.update_secrets(
            {
                "WORKING_KEY": "working-value",
                "FAILING_KEY": failing_secret,
            }
        )

        # Get bash tool and test env provider
        tools_dict = cast(dict[str, Tool], agent.tools)
        bash_tool = tools_dict["execute_bash"]
        bash_executor = cast(BashExecutor, bash_tool.executor)
        assert bash_executor.env_provider is not None

        # Should not raise exception, should return empty dict
        env_vars = bash_executor.env_provider("export FAILING_KEY=$FAILING_KEY")
        assert env_vars == {}

        # Working key should still work
        env_vars = bash_executor.env_provider("export WORKING_KEY=$WORKING_KEY")
        assert env_vars == {"WORKING_KEY": "working-value"}


def test_agent_env_provider_no_matches():
    """Test agent env provider when command has no secret matches."""
    llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"))

    with tempfile.TemporaryDirectory() as temp_dir:
        tools = [BashTool.create(working_dir=temp_dir)]

        agent = Agent(llm=llm, tools=tools)
        conversation = Conversation(agent)

        conversation.update_secrets({"API_KEY": "test-value"})

        # Get bash tool and test env provider with command that doesn't reference
        # secrets
        tools_dict = cast(dict[str, Tool], agent.tools)
        bash_tool = tools_dict["execute_bash"]
        bash_executor = cast(BashExecutor, bash_tool.executor)
        assert bash_executor.env_provider is not None
        env_vars = bash_executor.env_provider("echo hello world")

        assert env_vars == {}


def test_agent_without_bash_tools():
    """Test that agent works correctly when no bash tools are present."""
    llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"))

    # Create agent without bash tools
    agent = Agent(llm=llm, tools=[])
    conversation = Conversation(agent)

    # Add secrets (should not cause any issues)
    conversation.update_secrets({"API_KEY": "test-value"})

    # Should not raise any exceptions
    # Agent always has default tools (finish, think), so check that no bash tool
    # is present
    assert "execute_bash" not in agent.tools


def test_agent_secrets_integration_workflow():
    """Test complete workflow of agent secrets integration."""
    llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"))

    with tempfile.TemporaryDirectory() as temp_dir:
        tools = [BashTool.create(working_dir=temp_dir)]

        # Step 1: Create agent and conversation
        agent = Agent(llm=llm, tools=tools)
        conversation = Conversation(agent)

        # Step 2: Add secrets with mixed types
        def get_auth_token():
            return "bearer-token-456"

        conversation.update_secrets(
            {
                "API_KEY": "static-api-key-123",
                "AUTH_TOKEN": get_auth_token,
                "DATABASE_URL": "postgresql://localhost/test",
            }
        )

        # Step 3: Verify bash tool is configured correctly
        tools_dict = cast(dict[str, Tool], agent.tools)
        bash_tool = tools_dict["execute_bash"]
        bash_executor = cast(BashExecutor, bash_tool.executor)
        assert bash_executor.env_provider is not None

        # Step 4: Test env provider with various commands

        # Single secret
        env_vars = bash_executor.env_provider("curl -H 'X-API-Key: $API_KEY'")
        assert env_vars == {"API_KEY": "static-api-key-123"}

        # Multiple secrets
        command = "export API_KEY=$API_KEY && export AUTH_TOKEN=$AUTH_TOKEN"
        env_vars = bash_executor.env_provider(command)
        assert env_vars == {
            "API_KEY": "static-api-key-123",
            "AUTH_TOKEN": "bearer-token-456",
        }

        # No secrets referenced
        env_vars = bash_executor.env_provider("echo hello world")
        assert env_vars == {}

        # Step 5: Update secrets and verify changes propagate
        conversation.update_secrets({"API_KEY": "updated-api-key-789"})

        env_vars = bash_executor.env_provider("curl -H 'X-API-Key: $API_KEY'")
        assert env_vars == {"API_KEY": "updated-api-key-789"}


def test_warns_when_missing_bash_tool(caplog):
    """
    If no 'execute_bash' tool is registered, Agent.init_state() should log a warning
    when wiring the SecretsManager/env provider.
    """
    llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"))

    with caplog.at_level("WARNING"):
        _ = Conversation(Agent(llm=llm, tools=[]))

    messages = [
        rec.getMessage() for rec in caplog.records if rec.levelno >= 30
    ]  # WARNING+
    # Allow any of the suggested phrasings while ensuring it's the right warning
    assert any(
        "Skipped wiring SecretsManager: missing bash tool" in m for m in messages
    ), f"Expected a warning about missing 'execute_bash' tool; got: {messages}"
