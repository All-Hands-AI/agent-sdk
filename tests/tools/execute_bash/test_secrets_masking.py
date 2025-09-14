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
        def mock_env_masker() -> dict[str, str]:
            return {
                "SECRET_TOKEN": "secret-value-123",
                "API_KEY": "another-secret-456",
            }

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


def test_bash_executor_with_empty_output():
    """Test that automatic masking handles empty output gracefully."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create env_provider that returns secrets
        def mock_env_provider(cmd: str) -> dict[str, str]:
            return {"SECRET": "secret-value"}

        # Create env_masker that returns secrets for masking
        def mock_env_masker() -> dict[str, str]:
            return {"SECRET": "secret-value"}

        # Create executor with both env_provider and env_masker
        executor = BashExecutor(
            working_dir=temp_dir,
            env_provider=mock_env_provider,
            env_masker=mock_env_masker,
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
    """Test that BashExecutor automatically masks multiple secrets when env_masker is provided."""  # noqa: E501
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create env_provider that returns multiple secrets
        def multi_secrets_env_provider(cmd: str) -> dict[str, str]:
            return {
                "API_KEY": "secret-api-key",
                "PASSWORD": "secret-password",
            }

        # Create env_masker that returns the same secrets for masking
        def multi_secrets_env_masker() -> dict[str, str]:
            return {
                "API_KEY": "secret-api-key",
                "PASSWORD": "secret-password",
            }

        # Create executor with both env_provider and env_masker
        executor = BashExecutor(
            working_dir=temp_dir,
            env_provider=multi_secrets_env_provider,
            env_masker=multi_secrets_env_masker,
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
    """Test that BashExecutor provides env vars and masks secrets when env_masker is provided."""  # noqa: E501
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create env provider that provides secrets
        def env_provider(cmd: str) -> dict[str, str]:
            if "SECRET_TOKEN" in cmd:
                return {"SECRET_TOKEN": "my-secret-token-456"}
            return {}

        # Create env_masker that returns the secret for masking
        def env_masker() -> dict[str, str]:
            return {"SECRET_TOKEN": "my-secret-token-456"}

        # Create executor with both env_provider and env_masker
        executor = BashExecutor(
            working_dir=temp_dir,
            env_provider=env_provider,
            env_masker=env_masker,
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

        # Create env_masker that returns the secret for masking
        def env_masker() -> dict[str, str]:
            return {"API_TOKEN": "abc123def456"}

        # Create executor with both env_provider and env_masker
        executor = BashExecutor(
            working_dir=temp_dir,
            env_provider=env_provider,
            env_masker=env_masker,
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


def test_bash_executor_callable_secret_failure_bug():
    """Test the specific bug where callable secrets fail on second call but bash still has the value."""  # noqa: E501
    with tempfile.TemporaryDirectory() as temp_dir:
        call_count = 0

        # Create env_provider that succeeds first time, fails second time
        def failing_env_provider(cmd: str) -> dict[str, str]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call succeeds
                return {"SECRET_TOKEN": "my-secret-value-123"}
            else:
                # Second call fails (simulating HTTP request failure)
                raise Exception("HTTP request failed")

        # Create env_masker that always returns current values
        def env_masker() -> dict[str, str]:
            return {"SECRET_TOKEN": "my-secret-value-123"}

        # Create executor with both env_provider and env_masker
        executor = BashExecutor(
            working_dir=temp_dir,
            env_provider=failing_env_provider,
            env_masker=env_masker,
        )

        try:
            # First call: env_provider succeeds, secret is exported to bash
            action1 = ExecuteBashAction(command="echo $SECRET_TOKEN")
            result1 = executor(action1)

            # Should be masked because env_masker provides the value
            assert "my-secret-value-123" not in result1.output
            assert "<secret-hidden>" in result1.output

            # Second call: env_provider fails, but bash still has the value
            action2 = ExecuteBashAction(command="echo $SECRET_TOKEN")
            result2 = executor(action2)

            # This is the bug fix: should still be masked because env_masker works
            assert "my-secret-value-123" not in result2.output
            assert "<secret-hidden>" in result2.output

        finally:
            executor.close()


def test_bash_executor_with_secrets_manager_integration():
    """Test BashExecutor with SecretsManager to verify the full integration."""
    with tempfile.TemporaryDirectory() as temp_dir:
        from openhands.sdk.conversation.secrets_manager import SecretsManager

        # Create secrets manager with callable secret
        secrets_manager = SecretsManager()
        call_count = 0

        def get_secret() -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "secret-from-callable-123"
            else:
                raise Exception("Callable failed")

        secrets_manager.update_secrets({"API_KEY": get_secret})

        # Create env_provider and env_masker using secrets manager
        def env_provider(cmd: str) -> dict[str, str]:
            return secrets_manager.get_secrets_as_env_vars(cmd)

        def env_masker() -> dict[str, str]:
            return secrets_manager.get_current_secret_values()

        # Create executor
        executor = BashExecutor(
            working_dir=temp_dir,
            env_provider=env_provider,
            env_masker=env_masker,
        )

        try:
            # First call: callable succeeds, value is exported and tracked
            action1 = ExecuteBashAction(command="echo $API_KEY")
            result1 = executor(action1)

            # Should be masked
            assert "secret-from-callable-123" not in result1.output
            assert "<secret-hidden>" in result1.output

            # Second call: callable fails, but masking should still work
            action2 = ExecuteBashAction(command="echo $API_KEY")
            result2 = executor(action2)

            # Should still be masked using cached value from secrets manager
            assert "secret-from-callable-123" not in result2.output
            assert "<secret-hidden>" in result2.output

        finally:
            executor.close()
