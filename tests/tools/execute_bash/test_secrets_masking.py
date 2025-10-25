"""Tests for automatic secrets masking in BashExecutor."""

import tempfile

from openhands.tools.execute_bash import ExecuteBashAction
from openhands.tools.execute_bash.impl import BashExecutor


def test_bash_executor_with_env_masker_automatic_masking():
    """Test that BashExecutor automatically masks secrets when env_masker is provided."""  # noqa: E501
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create env_masker that masks known secret values
        def mock_env_masker(output: str) -> str:
            output = output.replace("secret-value-123", "<secret-hidden>")
            output = output.replace("another-secret-456", "<secret-hidden>")
            return output

        # Create executor with env_masker
        executor = BashExecutor(
            working_dir=temp_dir,
            env_masker=mock_env_masker,
        )

        try:
            # First, manually export secrets (simulating the new direct export approach)
            export_action = ExecuteBashAction(
                command=(
                    "export SECRET_TOKEN='secret-value-123' && "
                    "export API_KEY='another-secret-456'"
                )
            )
            executor(export_action)

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


def test_bash_executor_without_env_masker():
    """Test that BashExecutor works normally without env_masker (no masking)."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create executor without env_masker
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
