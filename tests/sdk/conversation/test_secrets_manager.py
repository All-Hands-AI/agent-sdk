"""Tests for SecretsManager class."""

from openhands.sdk.conversation.secrets_manager import SecretsManager


def test_update_secrets_with_static_values():
    """Test updating secrets with static string values."""
    manager = SecretsManager()
    secrets = {
        "API_KEY": "test-api-key",
        "DATABASE_URL": "postgresql://localhost/test",
    }

    manager.update_secrets(secrets)
    assert manager._secrets == secrets


def test_update_secrets_overwrites_existing():
    """Test that update_secrets overwrites existing keys."""
    manager = SecretsManager()

    # Add initial secrets
    manager.update_secrets({"API_KEY": "old-value"})
    assert manager._secrets["API_KEY"] == "old-value"

    # Update with new value
    manager.update_secrets({"API_KEY": "new-value", "NEW_KEY": "key-value"})
    assert manager._secrets["API_KEY"] == "new-value"

    manager.update_secrets({"API_KEY": "new-value-2"})
    assert manager._secrets["API_KEY"] == "new-value-2"


def test_find_secrets_in_text_case_insensitive():
    """Test that find_secrets_in_text is case insensitive."""
    manager = SecretsManager()
    manager.update_secrets(
        {
            "API_KEY": "test-key",
            "DATABASE_PASSWORD": "test-password",
        }
    )

    # Test various case combinations
    found = manager.find_secrets_in_text("echo api_key=$API_KEY")
    assert found == {"API_KEY"}

    found = manager.find_secrets_in_text("echo $database_password")
    assert found == {"DATABASE_PASSWORD"}

    found = manager.find_secrets_in_text("API_KEY and DATABASE_PASSWORD")
    assert found == {"API_KEY", "DATABASE_PASSWORD"}

    found = manager.find_secrets_in_text("echo hello world")
    assert found == set()


def test_find_secrets_in_text_partial_matches():
    """Test that find_secrets_in_text handles partial matches correctly."""
    manager = SecretsManager()
    manager.update_secrets(
        {
            "API_KEY": "test-key",
            "API": "test-api",  # Shorter key that's contained in API_KEY
        }
    )

    # Both should be found since "API" is contained in "API_KEY"
    found = manager.find_secrets_in_text("export API_KEY=$API_KEY")
    assert "API_KEY" in found
    assert "API" in found


def test_get_secrets_as_env_vars_static_values():
    """Test get_secrets_as_env_vars with static values."""
    manager = SecretsManager()
    manager.update_secrets(
        {
            "API_KEY": "test-api-key",
            "DATABASE_URL": "postgresql://localhost/test",
        }
    )

    env_vars = manager.get_secrets_as_env_vars("curl -H 'X-API-Key: $API_KEY'")
    assert env_vars == {"API_KEY": "test-api-key"}

    env_vars = manager.get_secrets_as_env_vars(
        "export API_KEY=$API_KEY && export DATABASE_URL=$DATABASE_URL"
    )
    assert env_vars == {
        "API_KEY": "test-api-key",
        "DATABASE_URL": "postgresql://localhost/test",
    }


def test_get_secrets_as_env_vars_callable_values():
    """Test get_secrets_as_env_vars with callable values."""
    manager = SecretsManager()

    def get_dynamic_token():
        return "dynamic-token-456"

    manager.update_secrets(
        {
            "STATIC_KEY": "static-value",
            "DYNAMIC_TOKEN": get_dynamic_token,
        }
    )

    env_vars = manager.get_secrets_as_env_vars("export DYNAMIC_TOKEN=$DYNAMIC_TOKEN")
    assert env_vars == {"DYNAMIC_TOKEN": "dynamic-token-456"}


def test_get_secrets_as_env_vars_handles_callable_exceptions():
    """Test that get_secrets_as_env_vars handles exceptions from callables."""
    manager = SecretsManager()

    def failing_callable():
        raise ValueError("Secret retrieval failed")

    def working_callable():
        return "working-value"

    manager.update_secrets(
        {
            "FAILING_SECRET": failing_callable,
            "WORKING_SECRET": working_callable,
        }
    )

    # Should not raise exception, should skip failing secret
    env_vars = manager.get_secrets_as_env_vars(
        "export FAILING_SECRET=$FAILING_SECRET && export WORKING_SECRET=$WORKING_SECRET"
    )

    # Only working secret should be returned
    assert env_vars == {"WORKING_SECRET": "working-value"}


def test_mask_secrets_once_retrieved():
    """Test mask_secrets_in_output with static secret values."""
    manager = SecretsManager()
    manager.update_secrets(
        {
            "API_KEY": "secret-api-key-123",
            "PASSWORD": "my-secret-password",
        }
    )

    manager.get_secrets_as_env_vars("$API_KEY")

    # Test masking single secret
    text = "API key is: secret-api-key-123"
    masked = manager.mask_secrets_in_output(text)
    assert masked == "API key is: <secret-hidden>"

    # # Test masking multiple secrets
    # text = "API: secret-api-key-123, Password: my-secret-password"
    # masked = manager.mask_secrets_in_output(text)
    # assert masked == "API: <secret-hidden>, Password: <secret-hidden>"

    # # Test text without secrets
    # text = "This text has no secrets"
    # masked = manager.mask_secrets_in_output(text)
    # assert masked == "This text has no secrets"


def test_mask_secrets_in_output_callable_values():
    """Test mask_secrets_in_output with callable secret values."""
    manager = SecretsManager()

    def get_dynamic_token():
        return "dynamic-token-456"

    manager.update_secrets(
        {
            "STATIC_KEY": "static-value-789",
            "DYNAMIC_TOKEN": get_dynamic_token,
        }
    )

    manager.get_secrets_as_env_vars("echo $STATIC_KEY; echo $DYNAMIC_TOKEN")

    text = "Token: dynamic-token-456, Key: static-value-789"
    masked = manager.mask_secrets_in_output(text)
    assert masked == "Token: <secret-hidden>, Key: <secret-hidden>"


def test_mask_secrets_in_output_multiple_occurrences():
    """Test mask_secrets_in_output with multiple occurrences of same secret."""
    manager = SecretsManager()
    manager.update_secrets({"SECRET": "my-secret"})

    manager.get_secrets_as_env_vars()

    text = "First: my-secret, Second: my-secret, Third: my-secret"
    masked = manager.mask_secrets_in_output(text)
    assert (
        masked
        == "First: <secret-hidden>, Second: <secret-hidden>, Third: <secret-hidden>"
    )


def test_mask_secrets_in_output_empty_input():
    """Test mask_secrets_in_output with empty or None input."""
    manager = SecretsManager()
    manager.update_secrets({"SECRET": "my-secret"})
    manager.get_secrets_as_env_vars()

    # Test empty string
    assert manager.mask_secrets_in_output("") == ""


def test_mask_secrets_in_output_no_secrets():
    """Test mask_secrets_in_output when no secrets are configured."""
    manager = SecretsManager()

    text = "This text has some content"
    masked = manager.mask_secrets_in_output(text)
    assert masked == text


def test_mask_secrets_in_output_handles_callable_exceptions():
    """Test that mask_secrets_in_output handles exceptions from callables gracefully."""
    manager = SecretsManager()

    def failing_callable():
        raise ValueError("Secret retrieval failed")

    def working_callable():
        return "working-secret"

    manager.update_secrets(
        {
            "FAILING_SECRET": failing_callable,
            "WORKING_SECRET": working_callable,
        }
    )
    manager.get_secrets_as_env_vars()

    text = "Text with working-secret but no failing secret"
    masked = manager.mask_secrets_in_output(text)
    # Should mask the working secret and ignore the failing one
    assert masked == "Text with <secret-hidden> but no failing secret"


def test_mask_secrets_in_output_empty_secret_values():
    """Test mask_secrets_in_output ignores empty secret values."""
    manager = SecretsManager()
    manager.update_secrets(
        {
            "EMPTY_SECRET": "",
            "VALID_SECRET": "valid-value",
        }
    )
    manager.get_secrets_as_env_vars()

    text = "Text with valid-value and empty values"
    masked = manager.mask_secrets_in_output(text)
    # Should only mask the valid secret
    assert masked == "Text with <secret-hidden> and empty values"
