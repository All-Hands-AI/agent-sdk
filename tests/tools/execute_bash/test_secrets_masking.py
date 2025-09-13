"""Tests for secrets masking in BashExecutor."""

import tempfile
from unittest.mock import Mock

from openhands.tools.execute_bash import ExecuteBashAction
from openhands.tools.execute_bash.impl import BashExecutor


def test_bash_executor_with_secrets_masker():
    """Test that BashExecutor applies secrets masking to command output."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a mock secrets masker
        def mock_secrets_masker(text: str) -> str:
            return text.replace("secret-value-123", "<secret-hidden>")

        # Create executor with secrets masker
        executor = BashExecutor(
            working_dir=temp_dir,
            secrets_masker=mock_secrets_masker,
        )

        try:
            # Execute a command that outputs a secret value
            action = ExecuteBashAction(
                command="echo 'The secret is: secret-value-123'", security_risk="LOW"
            )
            result = executor(action)

            # Check that the secret was masked in the output
            assert "secret-value-123" not in result.output
            assert "<secret-hidden>" in result.output
            assert "The secret is: <secret-hidden>" in result.output

        finally:
            executor.close()


def test_bash_executor_without_secrets_masker():
    """Test that BashExecutor works normally without secrets masker."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create executor without secrets masker
        executor = BashExecutor(working_dir=temp_dir)

        try:
            # Execute a command that outputs a secret value
            action = ExecuteBashAction(
                command="echo 'The secret is: secret-value-123'", security_risk="LOW"
            )
            result = executor(action)

            # Check that the output is not masked
            assert "secret-value-123" in result.output
            assert "<secret-hidden>" not in result.output

        finally:
            executor.close()


def test_bash_executor_secrets_masker_with_empty_output():
    """Test that secrets masker handles empty output gracefully."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a mock secrets masker
        mock_masker = Mock(return_value="")

        # Create executor with secrets masker
        executor = BashExecutor(
            working_dir=temp_dir,
            secrets_masker=mock_masker,
        )

        try:
            # Execute a command with no output
            action = ExecuteBashAction(command="true", security_risk="LOW")
            executor(action)

            # Masker should not be called for empty output
            mock_masker.assert_not_called()

        finally:
            executor.close()


def test_bash_executor_secrets_masker_exception_handling():
    """Test that BashExecutor handles exceptions from secrets masker gracefully."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a secrets masker that raises an exception
        def failing_masker(text: str) -> str:
            raise ValueError("Masker failed")

        # Create executor with failing secrets masker
        executor = BashExecutor(
            working_dir=temp_dir,
            secrets_masker=failing_masker,
        )

        try:
            # Execute a command
            action = ExecuteBashAction(
                command="echo 'test output'", security_risk="LOW"
            )
            result = executor(action)

            # Should still return the original output if masker fails
            assert "test output" in result.output

        finally:
            executor.close()


def test_bash_executor_multiple_secrets_masking():
    """Test that BashExecutor masks multiple secrets in output."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a secrets masker that masks multiple values
        def multi_secrets_masker(text: str) -> str:
            text = text.replace("secret-api-key", "<secret-hidden>")
            text = text.replace("secret-password", "<secret-hidden>")
            return text

        # Create executor with secrets masker
        executor = BashExecutor(
            working_dir=temp_dir,
            secrets_masker=multi_secrets_masker,
        )

        try:
            # Execute a command that outputs multiple secrets
            action = ExecuteBashAction(
                command="echo 'API: secret-api-key, Password: secret-password'",
                security_risk="LOW",
            )
            result = executor(action)

            # Check that both secrets were masked
            assert "secret-api-key" not in result.output
            assert "secret-password" not in result.output
            assert result.output.count("<secret-hidden>") == 2
            assert "API: <secret-hidden>, Password: <secret-hidden>" in result.output

        finally:
            executor.close()


def test_bash_executor_env_provider_and_secrets_masker():
    """Test that BashExecutor works with both env_provider and secrets_masker."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create env provider that provides secrets
        def env_provider(cmd: str) -> dict[str, str]:
            if "SECRET_TOKEN" in cmd:
                return {"SECRET_TOKEN": "my-secret-token-456"}
            return {}

        # Create secrets masker that masks the secret
        def secrets_masker(text: str) -> str:
            return text.replace("my-secret-token-456", "<secret-hidden>")

        # Create executor with both providers
        executor = BashExecutor(
            working_dir=temp_dir,
            env_provider=env_provider,
            secrets_masker=secrets_masker,
        )

        try:
            # Execute a command that uses and outputs the secret
            action = ExecuteBashAction(
                command="echo $SECRET_TOKEN", security_risk="LOW"
            )
            result = executor(action)

            # Check that the secret was masked in the output
            assert "my-secret-token-456" not in result.output
            assert "<secret-hidden>" in result.output

        finally:
            executor.close()
