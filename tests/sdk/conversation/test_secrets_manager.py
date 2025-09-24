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


def test_export_all_secrets_static_values():
    """Test export_all_secrets with static values."""
    manager = SecretsManager()
    manager.update_secrets(
        {
            "API_KEY": "test-api-key",
            "DATABASE_URL": "postgresql://localhost/test",
        }
    )

    export_commands = manager.export_all_secrets()
    assert len(export_commands) == 2
    assert "export API_KEY=test-api-key" in export_commands
    assert "export DATABASE_URL=postgresql://localhost/test" in export_commands


def test_export_all_secrets_callable_values():
    """Test export_all_secrets with callable values."""
    manager = SecretsManager()

    def get_dynamic_token():
        return "dynamic-token-456"

    manager.update_secrets(
        {
            "STATIC_KEY": "static-value",
            "DYNAMIC_TOKEN": get_dynamic_token,
        }
    )

    export_commands = manager.export_all_secrets()
    assert len(export_commands) == 2
    assert "export STATIC_KEY=static-value" in export_commands
    assert "export DYNAMIC_TOKEN=dynamic-token-456" in export_commands


def test_export_all_secrets_handles_callable_exceptions():
    """Test that export_all_secrets handles exceptions from callables."""
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
    export_commands = manager.export_all_secrets()

    # Only working secret should be returned
    assert len(export_commands) == 1
    assert "export WORKING_SECRET=working-value" in export_commands


def test_export_all_secrets_special_characters():
    """Test export_all_secrets properly quotes values with special characters."""
    manager = SecretsManager()
    manager.update_secrets(
        {
            "PASSWORD": "p@ssw0rd!",
            "URL": "https://api.example.com/v1?key=value&other=data",
            "QUOTED": 'value with "quotes" inside',
        }
    )

    export_commands = manager.export_all_secrets()
    assert len(export_commands) == 3

    # Check that special characters are properly quoted
    password_cmd = next(cmd for cmd in export_commands if "PASSWORD" in cmd)
    assert "export PASSWORD='p@ssw0rd!'" == password_cmd

    url_cmd = next(cmd for cmd in export_commands if "URL" in cmd)
    assert "export URL='https://api.example.com/v1?key=value&other=data'" == url_cmd

    quoted_cmd = next(cmd for cmd in export_commands if "QUOTED" in cmd)
    # shlex.quote should handle the quotes properly
    assert "QUOTED=" in quoted_cmd and "export" in quoted_cmd
    # The exact quoting depends on shlex.quote implementation
    assert quoted_cmd.startswith("export QUOTED=")
