"""Tests for automatic secrets masking in BashExecutor."""

import tempfile

from openhands.tools.execute_bash import ExecuteBashAction
from openhands.tools.execute_bash.impl import BashExecutor
from openhands.tools.execute_bash.secrets_manager import SecretsManager


def test_bash_executor_with_env_provider_automatic_masking():
    """Test BashExecutor automatically masks secrets with secrets_manager."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a secrets manager with secrets
        secrets_manager = SecretsManager()
        secrets_manager.update_secrets(
            {
                "SECRET_TOKEN": "secret-value-123",
                "API_KEY": "another-secret-456",
            }
        )

        # Create executor with secrets_manager
        executor = BashExecutor(working_dir=temp_dir, secrets_manager=secrets_manager)

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
    """Test that BashExecutor works normally without secrets_manager (no masking)."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create executor without secrets_manager
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
