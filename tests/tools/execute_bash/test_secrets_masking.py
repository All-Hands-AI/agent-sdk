"""Tests for automatic secrets masking in BashExecutor."""

import tempfile

from openhands.tools.execute_bash import ExecuteBashAction
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
