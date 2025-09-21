"""Test agent secrets integration with bash tools from openhands.tools package."""

import os
import tempfile
from pathlib import Path

import pytest
from pydantic import SecretStr

from openhands.sdk import Agent
from openhands.sdk.llm import LLM
from openhands.sdk.tool import ToolSpec
from openhands.tools.execute_bash import (
    BashTool,
    ExecuteBashAction,
    ExecuteBashObservation,
)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def bash_tool(temp_dir):
    """Create a BashTool instance for testing."""
    return BashTool.create(working_dir=temp_dir)


@pytest.fixture
def agent_with_bash(temp_dir):
    """Create an agent with bash tool for testing."""
    llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"))
    tools = [ToolSpec(name="BashTool", params={"working_dir": temp_dir})]
    return Agent(llm=llm, tools=tools)


def test_agent_without_bash_can_be_created(caplog):
    """Test that creating an agent without bash tool works fine."""
    llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"))
    agent = Agent(llm=llm, tools=[])

    # Verify agent was created successfully
    assert agent.llm.model == "gpt-4o-mini"
    assert len(agent.tools) == 0


def test_agent_with_bash_no_warning(caplog, temp_dir):
    """Test that creating an agent with bash tool doesn't log a warning."""
    llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"))
    tools = [ToolSpec(name="BashTool", params={"working_dir": temp_dir})]
    Agent(llm=llm, tools=tools)

    # Check that no warning was logged
    assert not any(
        "Agent created without BashTool" in record.message for record in caplog.records
    )


def test_agent_secrets_env_var_access(agent_with_bash, temp_dir):
    """Test that agent can access environment variables through bash tool."""
    # Set a test environment variable
    test_var = "TEST_SECRET_VAR"
    test_value = "secret_value_123"
    os.environ[test_var] = test_value

    try:
        # Get the bash tool from the agent
        bash_tool_spec = next(
            tool for tool in agent_with_bash.tools if tool.name == "BashTool"
        )
        bash_tool = BashTool.create(**bash_tool_spec.params)

        # Execute a command to read the environment variable
        action = ExecuteBashAction(command=f"echo ${test_var}")
        result = bash_tool(action)
        assert isinstance(result, ExecuteBashObservation)

        # Verify the result contains our secret value
        assert test_value in result.output
        assert result.metadata.exit_code == 0

    finally:
        # Clean up the environment variable
        if test_var in os.environ:
            del os.environ[test_var]


def test_agent_secrets_file_access(agent_with_bash, temp_dir):
    """Test that agent can access files with secrets through bash tool."""
    # Create a test file with secret content
    secret_file = Path(temp_dir) / "secret.txt"
    secret_content = "This is a secret message"
    secret_file.write_text(secret_content)

    # Get the bash tool from the agent
    bash_tool_spec = next(
        tool for tool in agent_with_bash.tools if tool.name == "BashTool"
    )
    bash_tool = BashTool.create(**bash_tool_spec.params)

    # Execute a command to read the secret file
    action = ExecuteBashAction(command=f"cat {secret_file}")
    result = bash_tool(action)
    assert isinstance(result, ExecuteBashObservation)

    # Verify the result contains our secret content
    assert secret_content in result.output
    assert result.metadata.exit_code == 0


def test_agent_secrets_working_directory(agent_with_bash, temp_dir):
    """Test that agent's bash tool respects the working directory."""
    # Get the bash tool from the agent
    bash_tool_spec = next(
        tool for tool in agent_with_bash.tools if tool.name == "BashTool"
    )
    bash_tool = BashTool.create(**bash_tool_spec.params)

    # Execute pwd command to get current working directory
    action = ExecuteBashAction(command="pwd")
    result = bash_tool(action)
    assert isinstance(result, ExecuteBashObservation)

    # Verify the working directory is correct
    assert temp_dir in result.output
    assert result.metadata.exit_code == 0


def test_agent_secrets_command_execution(agent_with_bash):
    """Test that agent can execute commands that might involve secrets."""
    # Get the bash tool from the agent
    bash_tool_spec = next(
        tool for tool in agent_with_bash.tools if tool.name == "BashTool"
    )
    bash_tool = BashTool.create(**bash_tool_spec.params)

    # Execute a simple command
    action = ExecuteBashAction(command="echo 'Hello World'")
    result = bash_tool(action)
    assert isinstance(result, ExecuteBashObservation)

    # Verify the command executed successfully
    assert "Hello World" in result.output
    assert result.metadata.exit_code == 0


def test_agent_secrets_multiple_commands(agent_with_bash, temp_dir):
    """Test that agent can execute multiple commands in sequence."""
    # Get the bash tool from the agent
    bash_tool_spec = next(
        tool for tool in agent_with_bash.tools if tool.name == "BashTool"
    )
    bash_tool = BashTool.create(**bash_tool_spec.params)

    # Create a test file
    action1 = ExecuteBashAction(command="echo 'test content' > test.txt")
    result1 = bash_tool(action1)
    assert isinstance(result1, ExecuteBashObservation)
    assert result1.metadata.exit_code == 0

    # Read the test file
    action2 = ExecuteBashAction(command="cat test.txt")
    result2 = bash_tool(action2)
    assert isinstance(result2, ExecuteBashObservation)
    assert result2.metadata.exit_code == 0
    assert "test content" in result2.output

    # Remove the test file
    action3 = ExecuteBashAction(command="rm test.txt")
    result3 = bash_tool(action3)
    assert isinstance(result3, ExecuteBashObservation)
    assert result3.metadata.exit_code == 0


def test_agent_secrets_error_handling(agent_with_bash):
    """Test that agent properly handles command errors."""
    # Get the bash tool from the agent
    bash_tool_spec = next(
        tool for tool in agent_with_bash.tools if tool.name == "BashTool"
    )
    bash_tool = BashTool.create(**bash_tool_spec.params)

    # Execute a command that should fail
    action = ExecuteBashAction(command="ls /nonexistent/directory")
    result = bash_tool(action)
    assert isinstance(result, ExecuteBashObservation)

    # Verify the command failed appropriately
    assert result.exit_code != 0
    assert (
        "No such file or directory" in result.output or "cannot access" in result.output
    )


def test_agent_secrets_bash_tool_isolation(temp_dir):
    """Test that different bash tools are properly isolated."""
    llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"))

    # Create two agents with different working directories
    temp_dir1 = Path(temp_dir) / "dir1"
    temp_dir2 = Path(temp_dir) / "dir2"
    temp_dir1.mkdir()
    temp_dir2.mkdir()

    tools1 = [ToolSpec(name="BashTool", params={"working_dir": str(temp_dir1)})]
    tools2 = [ToolSpec(name="BashTool", params={"working_dir": str(temp_dir2)})]

    agent1 = Agent(llm=llm, tools=tools1)
    agent2 = Agent(llm=llm, tools=tools2)

    # Get bash tools from both agents
    bash_tool1_spec = next(tool for tool in agent1.tools if tool.name == "BashTool")
    bash_tool2_spec = next(tool for tool in agent2.tools if tool.name == "BashTool")

    bash_tool1 = BashTool.create(**bash_tool1_spec.params)
    bash_tool2 = BashTool.create(**bash_tool2_spec.params)

    # Execute pwd in both tools
    action1 = ExecuteBashAction(command="pwd")
    action2 = ExecuteBashAction(command="pwd")
    result1 = bash_tool1(action1)
    result2 = bash_tool2(action2)
    assert isinstance(result1, ExecuteBashObservation)
    assert isinstance(result2, ExecuteBashObservation)

    # Verify they have different working directories
    assert str(temp_dir1) in result1.output
    assert str(temp_dir2) in result2.output
    assert result1.output != result2.output
