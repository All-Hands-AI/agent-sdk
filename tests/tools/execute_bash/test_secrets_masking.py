"""Tests for automatic secrets masking in BashExecutor."""

import tempfile
from unittest.mock import Mock

from pydantic import SecretStr

from openhands.sdk.agent import Agent
from openhands.sdk.conversation import Conversation
from openhands.sdk.llm import LLM
from openhands.tools.execute_bash import ExecuteBashAction, ExecuteBashObservation
from openhands.tools.execute_bash.impl import BashExecutor


def test_bash_executor_with_env_provider_automatic_masking():
    """Test that BashExecutor automatically masks secrets when env_masker is provided."""  # noqa: E501
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a mock env_provider that returns secrets
        def mock_env_provider(cmd: str) -> dict[str, str]:
            return {
                "SECRET_TOKEN": "secret-value-123",
                "API_KEY": "another-secret-456",
            }

        # Create env_masker that returns the same secrets for masking
        def mock_env_masker(str: str) -> str:
            str = str.replace("secret-value-123", "<secret-hidden>")
            str = str.replace("another-secret-456", "<secret-hidden>")
            return str

        # Create executor with both env_provider and env_masker
        executor = BashExecutor(
            working_dir=temp_dir,
            env_provider=mock_env_provider,
            env_masker=mock_env_masker,
        )

        try:
            # Execute a command that outputs secret values
            action = ExecuteBashAction(
                command="echo 'Token: secret-value-123, Key: another-secret-456'"
            )
            result = executor(action)

            # Check that both secrets were masked in the output
            assert "secret-value-123" not in result.output
            assert "another-secret-456" not in result.output
            assert "<secret-hidden>" in result.output
            assert "Token: <secret-hidden>, Key: <secret-hidden>" in result.output

        finally:
            executor.close()


def test_bash_executor_without_env_provider():
    """Test that BashExecutor works normally without env_provider (no masking)."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create executor without env_provider
        executor = BashExecutor(working_dir=temp_dir)

        try:
            # Execute a command that outputs a secret value
            action = ExecuteBashAction(command="echo 'The secret is: secret-value-123'")
            result = executor(action)

            # Check that the output is not masked
            assert "secret-value-123" in result.output
            assert "<secret-hidden>" not in result.output

        finally:
            executor.close()


def test_bash_executor_with_conversation_secrets():
    """Test that BashExecutor uses secrets from conversation.state.secrets_manager."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a conversation with secrets
        llm = LLM(
            model="gpt-4o-mini", api_key=SecretStr("test-key"), usage_id="test-llm"
        )
        agent = Agent(llm=llm, tools=[])

        test_secrets = {
            "SECRET_TOKEN": "secret-value-123",
            "API_KEY": "another-secret-456",
        }

        conversation = Conversation(
            agent=agent,
            workspace=temp_dir,
            persistence_dir=temp_dir,
            secrets=test_secrets,
        )

        # Create executor without env_provider
        executor = BashExecutor(working_dir=temp_dir)

        try:
            # Mock the session to avoid subprocess issues in tests
            mock_session = Mock()
            # session.execute returns ExecuteBashObservation
            mock_observation = ExecuteBashObservation(
                command="echo 'Token: $SECRET_TOKEN, Key: $API_KEY'",
                exit_code=0,
                output="Token: secret-value-123, Key: another-secret-456",
            )
            mock_session.execute.return_value = mock_observation
            executor.session = mock_session

            # Execute command with conversation - secrets should be exported and masked
            action = ExecuteBashAction(
                command="echo 'Token: $SECRET_TOKEN, Key: $API_KEY'"
            )
            result = executor(action, conversation=conversation)

            # Verify that session.execute was called
            assert mock_session.execute.called

            # Check that both secrets were masked in the output
            assert "secret-value-123" not in result.output
            assert "another-secret-456" not in result.output
            # SecretsManager uses <secret-hidden> as the mask
            assert "<secret-hidden>" in result.output

        finally:
            executor.close()
            conversation.close()


def test_bash_executor_conversation_secrets_prioritized_over_env_provider():
    """Test that conversation secrets are prioritized over env_provider."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a conversation with secrets
        llm = LLM(
            model="gpt-4o-mini", api_key=SecretStr("test-key"), usage_id="test-llm"
        )
        agent = Agent(llm=llm, tools=[])

        conversation_secrets = {
            "SECRET_TOKEN": "conversation-secret-value",
        }

        conversation = Conversation(
            agent=agent,
            workspace=temp_dir,
            persistence_dir=temp_dir,
            secrets=conversation_secrets,
        )

        # Create executor with env_provider that returns different value
        def mock_env_provider(cmd: str) -> dict[str, str]:
            return {"SECRET_TOKEN": "env-provider-value"}

        executor = BashExecutor(working_dir=temp_dir, env_provider=mock_env_provider)

        try:
            # Mock the session
            mock_session = Mock()
            mock_observation = ExecuteBashObservation(
                command="echo 'Token: $SECRET_TOKEN'",
                exit_code=0,
                output="Token: conversation-secret-value",
            )
            mock_session.execute.return_value = mock_observation
            executor.session = mock_session

            # Execute command with conversation
            action = ExecuteBashAction(command="echo 'Token: $SECRET_TOKEN'")
            result = executor(action, conversation=conversation)

            # Verify that session.execute was called
            assert mock_session.execute.called

            # Verify masking used conversation secrets
            assert "conversation-secret-value" not in result.output
            # SecretsManager uses <secret-hidden> as the mask
            assert "<secret-hidden>" in result.output

        finally:
            executor.close()
            conversation.close()
