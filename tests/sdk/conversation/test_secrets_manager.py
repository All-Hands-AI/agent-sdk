"""Tests for the secrets manager functionality."""

from openhands.sdk.conversation.secrets_manager import SecretsManager


def test_secrets_manager_initialization():
    """Test that SecretsManager initializes correctly."""
    manager = SecretsManager()
    assert not manager.has_secrets()
    assert len(manager.get_secret_keys()) == 0


def test_add_secrets():
    """Test adding secrets to the manager."""
    manager = SecretsManager()

    def get_api_key(key: str) -> str:
        return f"secret-value-for-{key}"

    def get_password(key: str) -> str:
        return "super-secret-password"

    secrets = {
        "API_KEY": get_api_key,
        "PASSWORD": get_password,
    }

    manager.add_secrets(secrets)

    assert manager.has_secrets()
    assert manager.get_secret_keys() == {"API_KEY", "PASSWORD"}


def test_find_secrets_in_text():
    """Test finding secret keys in text."""
    manager = SecretsManager()

    def get_secret(key: str) -> str:
        return f"value-{key}"

    secrets = {
        "API_KEY": get_secret,
        "DATABASE_URL": get_secret,
        "SECRET_TOKEN": get_secret,
    }

    manager.add_secrets(secrets)

    # Test exact matches
    assert manager.find_secrets_in_text("echo $API_KEY") == {"API_KEY"}
    assert manager.find_secrets_in_text("curl -H 'Authorization: $API_KEY'") == {
        "API_KEY"
    }

    # Test multiple secrets
    text = "export API_KEY=test && echo $DATABASE_URL"
    assert manager.find_secrets_in_text(text) == {"API_KEY", "DATABASE_URL"}

    # Test case insensitive
    assert manager.find_secrets_in_text("echo $api_key") == {"API_KEY"}

    # Test no matches
    assert manager.find_secrets_in_text("echo hello world") == set()

    # Test partial matches should not be found (word boundaries)
    assert manager.find_secrets_in_text("MY_API_KEY_SUFFIX") == set()


def test_inject_secrets_into_bash_command():
    """Test injecting secrets into bash commands."""
    manager = SecretsManager()

    def get_api_key(key: str) -> str:
        return "sk-1234567890abcdef"

    def get_password(key: str) -> str:
        return "my-secret-password"

    secrets = {
        "API_KEY": get_api_key,
        "PASSWORD": get_password,
    }

    manager.add_secrets(secrets)

    # Test single secret injection
    command = "curl -H 'Authorization: Bearer $API_KEY' https://api.example.com"
    result = manager.inject_secrets_into_bash_command(command)
    expected = (
        "export API_KEY='sk-1234567890abcdef' && "
        "curl -H 'Authorization: Bearer $API_KEY' https://api.example.com"
    )
    assert result == expected

    # Test multiple secrets injection
    command = "echo $API_KEY && echo $PASSWORD"
    result = manager.inject_secrets_into_bash_command(command)
    # The order might vary, so check both secrets are exported
    assert "export API_KEY='sk-1234567890abcdef'" in result
    assert "export PASSWORD='my-secret-password'" in result
    assert command in result

    # Test no secrets in command
    command = "echo hello world"
    result = manager.inject_secrets_into_bash_command(command)
    assert result == command


def test_inject_secrets_with_quotes_escaping():
    """Test that secrets with quotes are properly escaped."""
    manager = SecretsManager()

    def get_secret_with_quotes(key: str) -> str:
        return "secret'with'quotes"

    secrets = {"SECRET": get_secret_with_quotes}
    manager.add_secrets(secrets)

    command = "echo $SECRET"
    result = manager.inject_secrets_into_bash_command(command)
    expected = "export SECRET='secret'\"'\"'with'\"'\"'quotes' && echo $SECRET"
    assert result == expected


def test_clear_secrets():
    """Test clearing all secrets."""
    manager = SecretsManager()

    def get_secret(key: str) -> str:
        return "value"

    secrets = {"API_KEY": get_secret, "PASSWORD": get_secret}
    manager.add_secrets(secrets)

    assert manager.has_secrets()
    assert len(manager.get_secret_keys()) == 2

    manager.clear_secrets()

    assert not manager.has_secrets()
    assert len(manager.get_secret_keys()) == 0


def test_secret_retrieval_error():
    """Test handling of errors during secret retrieval."""
    manager = SecretsManager()

    def failing_secret(key: str) -> str:
        raise ValueError("Secret retrieval failed")

    def working_secret(key: str) -> str:
        return "working-value"

    secrets = {
        "FAILING_SECRET": failing_secret,
        "WORKING_SECRET": working_secret,
    }

    manager.add_secrets(secrets)

    command = "echo $FAILING_SECRET && echo $WORKING_SECRET"
    result = manager.inject_secrets_into_bash_command(command)

    # Should only inject the working secret
    assert "export WORKING_SECRET='working-value'" in result
    assert "export FAILING_SECRET" not in result
    assert command in result


def test_empty_secrets_dict():
    """Test adding an empty secrets dictionary."""
    manager = SecretsManager()
    manager.add_secrets({})

    assert not manager.has_secrets()
    assert len(manager.get_secret_keys()) == 0

    command = "echo hello"
    result = manager.inject_secrets_into_bash_command(command)
    assert result == command


def test_update_existing_secrets():
    """Test updating existing secrets."""
    manager = SecretsManager()

    def get_old_secret(key: str) -> str:
        return "old-value"

    def get_new_secret(key: str) -> str:
        return "new-value"

    # Add initial secret
    manager.add_secrets({"API_KEY": get_old_secret})

    # Update with new secret
    manager.add_secrets({"API_KEY": get_new_secret})

    command = "echo $API_KEY"
    result = manager.inject_secrets_into_bash_command(command)
    expected = "export API_KEY='new-value' && echo $API_KEY"
    assert result == expected
