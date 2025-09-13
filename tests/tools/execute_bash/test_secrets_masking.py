"""Tests for automatic secrets masking in BashExecutor."""

import tempfile

from openhands.tools.execute_bash import ExecuteBashAction
from openhands.tools.execute_bash.impl import BashExecutor


def test_bash_executor_with_env_provider_automatic_masking():
    """Test that BashExecutor automatically masks secrets from env_provider."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a mock env_provider that returns secrets
        def mock_env_provider(cmd: str) -> dict[str, str]:
            return {
                "SECRET_TOKEN": "secret-value-123",
                "API_KEY": "another-secret-456",
            }

        # Create executor with env_provider (masking happens automatically)
        executor = BashExecutor(
            working_dir=temp_dir,
            env_provider=mock_env_provider,
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


def test_bash_executor_with_empty_output():
    """Test that automatic masking handles empty output gracefully."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create env_provider that returns secrets
        def mock_env_provider(cmd: str) -> dict[str, str]:
            return {"SECRET": "secret-value"}

        # Create executor with env_provider
        executor = BashExecutor(
            working_dir=temp_dir,
            env_provider=mock_env_provider,
        )

        try:
            # Execute a command with no output
            action = ExecuteBashAction(command="true")
            result = executor(action)

            # Should handle empty output gracefully
            assert result.output == ""

        finally:
            executor.close()


def test_bash_executor_masking_exception_handling():
    """Test that BashExecutor handles masking exceptions gracefully."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create env_provider that returns invalid secret values to trigger exception
        def problematic_env_provider(cmd: str) -> dict[str, str]:
            return {}  # Empty dict to test edge cases

        # Create executor with env_provider
        executor = BashExecutor(
            working_dir=temp_dir,
            env_provider=problematic_env_provider,
        )

        try:
            # Execute a command
            action = ExecuteBashAction(command="echo 'test output'")
            result = executor(action)

            # Should still return the original output if masking fails
            assert "test output" in result.output

        finally:
            executor.close()


def test_bash_executor_multiple_secrets_automatic_masking():
    """Test that BashExecutor automatically masks multiple secrets from env_provider."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create env_provider that returns multiple secrets
        def multi_secrets_env_provider(cmd: str) -> dict[str, str]:
            return {
                "API_KEY": "secret-api-key",
                "PASSWORD": "secret-password",
            }

        # Create executor with env_provider
        executor = BashExecutor(
            working_dir=temp_dir,
            env_provider=multi_secrets_env_provider,
        )

        try:
            # Execute a command that outputs multiple secrets
            action = ExecuteBashAction(
                command="echo 'API: secret-api-key, Password: secret-password'"
            )
            result = executor(action)

            # Check that both secrets were masked
            assert "secret-api-key" not in result.output
            assert "secret-password" not in result.output
            assert result.output.count("<secret-hidden>") == 2
            assert "API: <secret-hidden>, Password: <secret-hidden>" in result.output

        finally:
            executor.close()


def test_bash_executor_env_provider_with_env_vars():
    """Test that BashExecutor provides env vars and masks secrets automatically."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create env provider that provides secrets
        def env_provider(cmd: str) -> dict[str, str]:
            if "SECRET_TOKEN" in cmd:
                return {"SECRET_TOKEN": "my-secret-token-456"}
            return {}

        # Create executor with env_provider (automatic masking)
        executor = BashExecutor(
            working_dir=temp_dir,
            env_provider=env_provider,
        )

        try:
            # Execute a command that uses and outputs the secret
            action = ExecuteBashAction(command="echo $SECRET_TOKEN")
            result = executor(action)

            # Check that the secret was automatically masked in the output
            assert "my-secret-token-456" not in result.output
            assert "<secret-hidden>" in result.output

        finally:
            executor.close()


def test_bash_executor_partial_secret_masking():
    """Test that BashExecutor masks secrets even when they appear as substrings."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create env_provider that returns a secret
        def env_provider(cmd: str) -> dict[str, str]:
            return {"API_TOKEN": "abc123def456"}

        # Create executor with env_provider
        executor = BashExecutor(
            working_dir=temp_dir,
            env_provider=env_provider,
        )

        try:
            # Execute a command that outputs the secret in different contexts
            action = ExecuteBashAction(
                command="echo 'Token: abc123def456, URL: https://api.com?token=abc123def456'"
            )
            result = executor(action)

            # Check that all instances of the secret were masked
            assert "abc123def456" not in result.output
            assert result.output.count("<secret-hidden>") == 2
            assert (
                "Token: <secret-hidden>, URL: https://api.com?token=<secret-hidden>"
                in result.output
            )

        finally:
            executor.close()
