"""Tests for automatic secrets masking in BashExecutor."""

import tempfile
from unittest.mock import Mock

from pydantic import SecretStr

from openhands.sdk.agent import Agent
from openhands.sdk.conversation import Conversation
from openhands.sdk.llm import LLM
from openhands.sdk.tool.schema import TextContent
from openhands.tools.execute_bash import ExecuteBashAction, ExecuteBashObservation
from openhands.tools.execute_bash.impl import BashExecutor
from tests.tools.execute_bash.conftest import get_output_text


def test_bash_executor_without_conversation():
    """Test that BashExecutor works normally without conversation (no masking)."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create executor without conversation
        executor = BashExecutor(working_dir=temp_dir)

        try:
            # Execute a command that outputs a secret value
            action = ExecuteBashAction(command="echo 'The secret is: secret-value-123'")
            result = executor(action)

            # Check that the output is not masked (no conversation provided)
            assert "secret-value-123" in get_output_text(result)
            assert "<secret-hidden>" not in get_output_text(result)

        finally:
            executor.close()


def test_bash_executor_with_conversation_secrets():
    """Test that BashExecutor uses secrets from conversation.state.secret_registry."""
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
                output=[
                    TextContent(text="Token: secret-value-123, Key: another-secret-456")
                ],
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
            assert "secret-value-123" not in get_output_text(result)
            assert "another-secret-456" not in get_output_text(result)
            # SecretsManager uses <secret-hidden> as the mask
            assert "<secret-hidden>" in get_output_text(result)

        finally:
            executor.close()
            conversation.close()
