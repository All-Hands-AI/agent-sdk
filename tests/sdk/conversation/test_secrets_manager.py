"""Tests for secrets singleton facade and workspace behavior."""

import pytest

from openhands.sdk import secrets as global_secrets
from openhands.sdk.conversation.secret_source import LookupSecret, SecretSource


@pytest.fixture(autouse=True)
def _reset_secrets():
    global_secrets.clear()
    yield
    global_secrets.clear()


def test_update_secrets_with_static_values():
    """Test updating secrets with static string values."""
    secrets = {
        "API_KEY": "test-api-key",
        "DATABASE_URL": "postgresql://localhost/test",
    }

    global_secrets.update(secrets)
    # Verify names are registered
    assert "API_KEY" in global_secrets.list_names()
    assert "DATABASE_URL" in global_secrets.list_names()

    # Verify StaticSecret wrapping by checking get_value
    assert global_secrets.get_value("API_KEY") == "test-api-key"
    assert global_secrets.get_value("DATABASE_URL") == "postgresql://localhost/test"


def test_update_secrets_overwrites_existing():
    """Test that update_secrets overwrites existing keys."""
    # Add initial secrets
    global_secrets.update({"API_KEY": "old-value"})
    assert global_secrets.get_value("API_KEY") == "old-value"

    # Update with new value and add NEW_KEY
    global_secrets.update({"API_KEY": "new-value", "NEW_KEY": "key-value"})
    assert global_secrets.get_value("API_KEY") == "new-value"
    assert global_secrets.get_value("NEW_KEY") == "key-value"

    # Update again
    global_secrets.update({"API_KEY": "new-value-2"})
    assert global_secrets.get_value("API_KEY") == "new-value-2"


def test_env_for_command_detects_var_forms_and_lowercase():
    """env_for_command should detect $VAR and ${VAR}, including lowercase names."""
    global_secrets.clear()
    global_secrets.update(
        {
            "API_KEY": "test-key",
            "database_password": "test-password",
        }
    )

    # $VAR and ${VAR}
    assert global_secrets.env_for_command("echo $API_KEY") == {"API_KEY": "test-key"}
    assert global_secrets.env_for_command("echo ${API_KEY}") == {"API_KEY": "test-key"}

    # lowercase supported
    assert global_secrets.env_for_command("echo $database_password") == {
        "database_password": "test-password"
    }

    # Non-referenced names should not be included
    assert global_secrets.env_for_command("echo hello world") == {}


def test_env_for_command_uses_exact_var_names_not_substrings():
    """Scanner should not include keys unless referenced as $NAME or ${NAME}."""
    global_secrets.clear()
    global_secrets.update({"API_KEY": "test-key", "API": "test-api"})

    # Only API_KEY is referenced
    env = global_secrets.env_for_command("export API_KEY=$API_KEY")
    assert env == {"API_KEY": "test-key"}


def test_env_for_command_static_values_and_multiple():
    """env_for_command with static values and multiple references."""
    global_secrets.clear()
    global_secrets.update(
        {
            "API_KEY": "test-api-key",
            "DATABASE_URL": "postgresql://localhost/test",
        }
    )

    env_vars = global_secrets.env_for_command("curl -H 'X-API-Key: $API_KEY'")
    assert env_vars == {"API_KEY": "test-api-key"}

    env_vars = global_secrets.env_for_command(
        "export API_KEY=$API_KEY && export DATABASE_URL=$DATABASE_URL"
    )
    assert env_vars == {
        "API_KEY": "test-api-key",
        "DATABASE_URL": "postgresql://localhost/test",
    }


def test_env_for_command_callable_values():
    """env_for_command with callable SecretSource values."""

    class MyTokenSource(SecretSource):
        def get_value(self):
            return "dynamic-token-456"

    global_secrets.clear()
    global_secrets.update(
        {
            "STATIC_KEY": "static-value",
            "DYNAMIC_TOKEN": MyTokenSource(),
        }
    )

    env_vars = global_secrets.env_for_command("export DYNAMIC_TOKEN=$DYNAMIC_TOKEN")
    assert env_vars == {"DYNAMIC_TOKEN": "dynamic-token-456"}


def test_env_for_command_handles_callable_exceptions_and_masking():
    """env_for_command skips failing sources; mask_output hides resolved values."""

    class MyFailingTokenSource(SecretSource):
        def get_value(self):
            raise ValueError("Secret retrieval failed")

    class MyWorkingTokenSource(SecretSource):
        def get_value(self):
            return "working-value"

    global_secrets.clear()
    global_secrets.update(
        {
            "FAILING_SECRET": MyFailingTokenSource(),
            "WORKING_SECRET": MyWorkingTokenSource(),
        }
    )

    # Should not raise exception, should skip failing secret
    env_vars = global_secrets.env_for_command(
        "export FAILING_SECRET=$FAILING_SECRET && export WORKING_SECRET=$WORKING_SECRET"
    )

    # Only working secret should be returned
    assert env_vars == {"WORKING_SECRET": "working-value"}

    # mask_output replaces the resolved value
    masked = global_secrets.mask_output("token=working-value; other=unchanged")
    assert masked == "token=<secret-hidden>; other=unchanged"


def test_lookup_secret_fetch_and_masking(monkeypatch):
    """LookupSecret should fetch via httpx.get and mask resolved value."""
    calls = {}

    class DummyResponse:
        text: str

        def __init__(self, text: str):
            self.text = text

        def raise_for_status(self) -> None:
            return None

    def fake_get(url, headers=None):
        calls["url"] = url
        calls["headers"] = headers
        return DummyResponse("fetched-token")

    # Patch httpx.get used by LookupSecret
    import openhands.sdk.conversation.secret_source as ss

    monkeypatch.setattr(ss.httpx, "get", fake_get)

    global_secrets.clear()
    global_secrets.update(
        {
            "gh_token": LookupSecret(
                url="https://example.com/token", headers={"X-Auth": "abc"}
            )
        }
    )

    # JIT resolution when referenced
    env = global_secrets.env_for_command("echo $gh_token")
    assert env == {"gh_token": "fetched-token"}
    assert calls["url"] == "https://example.com/token"
    assert calls["headers"] == {"X-Auth": "abc"}

    # Masking should hide the fetched value
    masked = global_secrets.mask_output("Bearer fetched-token")
    assert masked == "Bearer <secret-hidden>"
