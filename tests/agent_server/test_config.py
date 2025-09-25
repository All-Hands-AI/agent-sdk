"""
Unit tests for the configuration system, focusing on get_default_config function
and JSON configuration loading with environment variable overrides.
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from openhands.agent_server.config import (
    CONFIG_FILE_PATH_ENV,
    DEFAULT_CONFIG_FILE_PATH,
    SESSION_API_KEY_ENV,
    Config,
    get_default_config,
)


class TestConfig:
    """Test cases for the Config class and its methods."""

    def test_config_default_values(self):
        """Test that Config has correct default values."""
        config = Config()

        assert config.session_api_keys == []
        assert config.allow_cors_origins == []
        assert config.conversations_path == Path("workspace/conversations")
        assert config.workspace_path == Path("workspace/project")
        assert config.static_files_path is None

    def test_config_with_custom_values(self):
        """Test Config creation with custom values."""
        config = Config(
            session_api_keys=["test-key", "another-key"],
            allow_cors_origins=["https://example.com"],
            conversations_path=Path("custom/conversations"),
            workspace_path=Path("custom/workspace"),
            static_files_path=Path("custom/static"),
        )

        assert config.session_api_keys == ["test-key", "another-key"]
        assert config.allow_cors_origins == ["https://example.com"]
        assert config.conversations_path == Path("custom/conversations")
        assert config.workspace_path == Path("custom/workspace")
        assert config.static_files_path == Path("custom/static")

    def test_config_immutable(self):
        """Test that Config is immutable (frozen)."""
        config = Config()

        with pytest.raises(Exception):  # pydantic ValidationError or similar
            config.session_api_keys = ["new-key"]

    def test_update_with_env_var(self):
        """Test the update_with_env_var method."""
        config = Config()

        # Set environment variables using auto-generated names (UPPER_CASE)
        with patch.dict(
            os.environ,
            {
                "ENABLE_VSCODE": "false",
                "WORKSPACE_PATH": "/tmp/test_workspace",
                "SESSION_API_KEYS": "key1,key2,key3",
            },
        ):
            updated_config = config.update_with_env_var()

            # Verify original config is unchanged (immutable)
            assert config.enable_vscode
            assert config.workspace_path == Path("workspace/project")
            assert config.session_api_keys == []

            # Verify updated config has new values
            assert not updated_config.enable_vscode
            assert updated_config.workspace_path == Path("/tmp/test_workspace")
            assert updated_config.session_api_keys == ["key1", "key2", "key3"]

    def test_update_with_env_var_missing_env_vars(self):
        """Test update_with_env_var with missing environment variables."""
        config = Config()

        # Clear any existing env vars that might match our field names
        with patch.dict(os.environ, {}, clear=False):
            for field_name in config.__class__.model_fields:
                env_var = field_name.upper()
                if env_var in os.environ:
                    del os.environ[env_var]

            updated_config = config.update_with_env_var()

            # Should be unchanged since env vars don't exist
            assert updated_config.enable_vscode == config.enable_vscode
            assert updated_config.workspace_path == config.workspace_path

    def test_update_with_env_var_auto_mapping(self):
        """Test update_with_env_var with automatic environment variable mapping."""
        config = Config()

        # Set environment variables using the auto-generated names (UPPER_CASE)
        with patch.dict(
            os.environ,
            {
                "ENABLE_VSCODE": "false",
                "WORKSPACE_PATH": "/tmp/auto_workspace",
                "SESSION_API_KEYS": "auto1,auto2,auto3",
            },
        ):
            # Call the method to use auto-generation
            updated_config = config.update_with_env_var()

            # Verify original config is unchanged (immutable)
            assert config.enable_vscode
            assert config.workspace_path == Path("workspace/project")
            assert config.session_api_keys == []

            # Verify updated config has new values from auto-mapped env vars
            assert not updated_config.enable_vscode
            assert updated_config.workspace_path == Path("/tmp/auto_workspace")
            assert updated_config.session_api_keys == ["auto1", "auto2", "auto3"]

    def test_from_json_file_nonexistent_file(self):
        """Test loading from a non-existent JSON file returns defaults."""
        non_existent_path = Path("/tmp/nonexistent_config.json")

        # Patch environment to ensure no SESSION_API_KEY is set
        with patch.dict(os.environ, {}, clear=False):
            if SESSION_API_KEY_ENV in os.environ:
                del os.environ[SESSION_API_KEY_ENV]
            config = Config.from_json_file(non_existent_path)

            assert config.session_api_keys == []
            assert config.allow_cors_origins == []
            assert config.conversations_path == Path("workspace/conversations")
            assert config.workspace_path == Path("workspace/project")
            assert config.static_files_path is None

    def test_from_json_file_empty_file(self):
        """Test loading from an empty JSON file returns defaults."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{}")
            temp_path = Path(f.name)

        try:
            # Patch environment to ensure no SESSION_API_KEY is set
            with patch.dict(os.environ, {}, clear=False):
                if SESSION_API_KEY_ENV in os.environ:
                    del os.environ[SESSION_API_KEY_ENV]
                config = Config.from_json_file(temp_path)

                assert config.session_api_keys == []
                assert config.allow_cors_origins == []
                assert config.conversations_path == Path("workspace/conversations")
                assert config.workspace_path == Path("workspace/project")
                assert config.static_files_path is None
        finally:
            temp_path.unlink()

    def test_from_json_file_with_values_legacy_format(self):
        """Test loading from a JSON file with legacy singular session_api_key."""
        json_content = {
            "session_api_key": "json-key",
            "allow_cors_origins": ["https://json.com", "https://test.com"],
            "conversations_path": "json/conversations",
            "workspace_path": "json/workspace",
            "static_files_path": "json/static",
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(json_content, f)
            temp_path = Path(f.name)

        try:
            # Patch environment to ensure no SESSION_API_KEY is set
            with patch.dict(os.environ, {}, clear=False):
                if SESSION_API_KEY_ENV in os.environ:
                    del os.environ[SESSION_API_KEY_ENV]
                config = Config.from_json_file(temp_path)

                # Legacy singular key should be converted to list
                assert config.session_api_keys == ["json-key"]
                assert config.allow_cors_origins == [
                    "https://json.com",
                    "https://test.com",
                ]
                assert config.conversations_path == Path("json/conversations")
                assert config.workspace_path == Path("json/workspace")
                assert config.static_files_path == Path("json/static")
        finally:
            temp_path.unlink()

    def test_from_json_file_with_values_new_format(self):
        """Test loading from a JSON file with new plural session_api_keys."""
        json_content = {
            "session_api_keys": ["json-key-1", "json-key-2"],
            "allow_cors_origins": ["https://json.com", "https://test.com"],
            "conversations_path": "json/conversations",
            "workspace_path": "json/workspace",
            "static_files_path": "json/static",
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(json_content, f)
            temp_path = Path(f.name)

        try:
            # Patch environment to ensure no SESSION_API_KEY is set
            with patch.dict(os.environ, {}, clear=False):
                if SESSION_API_KEY_ENV in os.environ:
                    del os.environ[SESSION_API_KEY_ENV]
                config = Config.from_json_file(temp_path)

                assert config.session_api_keys == ["json-key-1", "json-key-2"]
                assert config.allow_cors_origins == [
                    "https://json.com",
                    "https://test.com",
                ]
                assert config.conversations_path == Path("json/conversations")
                assert config.workspace_path == Path("json/workspace")
                assert config.static_files_path == Path("json/static")
        finally:
            temp_path.unlink()

    def test_from_json_file_with_env_override(self):
        """Test that environment variables override JSON file values."""
        json_content = {
            "session_api_keys": ["json-key-1", "json-key-2"],
            "allow_cors_origins": ["https://json.com"],
            "conversations_path": "json/conversations",
            "workspace_path": "json/workspace",
            "static_files_path": "json/static",
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(json_content, f)
            temp_path = Path(f.name)

        try:
            with patch.dict(os.environ, {SESSION_API_KEY_ENV: "env-override-key"}):
                config = Config.from_json_file(temp_path)

                # Environment variable should override JSON value and become only key
                assert config.session_api_keys == ["env-override-key"]
                # Other values should come from JSON
                assert config.allow_cors_origins == ["https://json.com"]
                assert config.conversations_path == Path("json/conversations")
                assert config.workspace_path == Path("json/workspace")
                assert config.static_files_path == Path("json/static")
        finally:
            temp_path.unlink()

    def test_from_json_file_env_override_only(self):
        """Test environment variable override with no JSON file."""
        non_existent_path = Path("/tmp/nonexistent_config.json")

        with patch.dict(os.environ, {SESSION_API_KEY_ENV: "env-only-key"}):
            config = Config.from_json_file(non_existent_path)

            assert config.session_api_keys == ["env-only-key"]
            assert config.allow_cors_origins == []
            assert config.conversations_path == Path("workspace/conversations")
            assert config.workspace_path == Path("workspace/project")
            assert config.static_files_path is None

    def test_from_json_file_partial_json(self):
        """Test loading from JSON file with only some values specified."""
        json_content = {
            "session_api_key": "partial-key",
            "allow_cors_origins": ["https://partial.com"],
            # conversations_path and workspace_path not specified
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(json_content, f)
            temp_path = Path(f.name)

        try:
            # Patch environment to ensure no SESSION_API_KEY is set
            with patch.dict(os.environ, {}, clear=False):
                if SESSION_API_KEY_ENV in os.environ:
                    del os.environ[SESSION_API_KEY_ENV]
                config = Config.from_json_file(temp_path)

                assert config.session_api_keys == ["partial-key"]
                assert config.allow_cors_origins == ["https://partial.com"]
                # Should use defaults for unspecified values
                assert config.conversations_path == Path("workspace/conversations")
                assert config.workspace_path == Path("workspace/project")
                assert config.static_files_path is None
        finally:
            temp_path.unlink()


class TestGetDefaultConfig:
    """Test cases for the get_default_config function."""

    def setup_method(self):
        """Reset the global config before each test."""
        # Reset the global _default_config variable
        import openhands.agent_server.config as config_module

        config_module._default_config = None

    def test_get_default_config_no_env_no_file(self):
        """Test get_default_config with no environment variable and no default file."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("pathlib.Path.exists", return_value=False):
                config = get_default_config()

                assert config.session_api_keys == []
                assert config.allow_cors_origins == []
                assert config.conversations_path == Path("workspace/conversations")
                assert config.workspace_path == Path("workspace/project")
                assert config.static_files_path is None

    def test_get_default_config_with_default_file(self):
        """Test get_default_config using the default config file."""
        json_content = {
            "session_api_key": "default-file-key",
            "allow_cors_origins": ["https://default.com"],
            "conversations_path": "default/conversations",
            "workspace_path": "default/workspace",
            "static_files_path": "default/static",
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(json_content, f)
            temp_path = Path(f.name)

        try:
            with patch.dict(os.environ, {}, clear=True):
                with patch(
                    "openhands.agent_server.config.DEFAULT_CONFIG_FILE_PATH",
                    str(temp_path),
                ):
                    config = get_default_config()

                    assert config.session_api_keys == ["default-file-key"]
                    assert config.allow_cors_origins == ["https://default.com"]
                    assert config.conversations_path == Path("default/conversations")
                    assert config.workspace_path == Path("default/workspace")
                    assert config.static_files_path == Path("default/static")
        finally:
            temp_path.unlink()

    def test_get_default_config_with_custom_file_path(self):
        """Test get_default_config with custom config file path from environment."""
        json_content = {
            "session_api_key": "custom-file-key",
            "allow_cors_origins": ["https://custom.com"],
            "conversations_path": "custom/conversations",
            "workspace_path": "custom/workspace",
            "static_files_path": "custom/static",
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(json_content, f)
            temp_path = Path(f.name)

        try:
            with patch.dict(
                os.environ, {CONFIG_FILE_PATH_ENV: str(temp_path)}, clear=False
            ):
                if SESSION_API_KEY_ENV in os.environ:
                    del os.environ[SESSION_API_KEY_ENV]
                config = get_default_config()

                assert config.session_api_keys == ["custom-file-key"]
                assert config.allow_cors_origins == ["https://custom.com"]
                assert config.conversations_path == Path("custom/conversations")
                assert config.workspace_path == Path("custom/workspace")
                assert config.static_files_path == Path("custom/static")
        finally:
            temp_path.unlink()

    def test_get_default_config_with_env_override(self):
        """Test get_default_config with environment variable override."""
        json_content = {
            "session_api_key": "file-key",
            "allow_cors_origins": ["https://file.com"],
            "conversations_path": "file/conversations",
            "workspace_path": "file/workspace",
            "static_files_path": "file/static",
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(json_content, f)
            temp_path = Path(f.name)

        try:
            with patch.dict(
                os.environ,
                {
                    CONFIG_FILE_PATH_ENV: str(temp_path),
                    SESSION_API_KEY_ENV: "env-override-key",
                },
            ):
                config = get_default_config()

                # Environment variable should override file value
                assert config.session_api_keys == ["env-override-key"]
                # Other values should come from file
                assert config.allow_cors_origins == ["https://file.com"]
                assert config.conversations_path == Path("file/conversations")
                assert config.workspace_path == Path("file/workspace")
                assert config.static_files_path == Path("file/static")
        finally:
            temp_path.unlink()

    def test_get_default_config_caching(self):
        """Test that get_default_config caches the result."""
        json_content = {
            "session_api_key": "cached-key",
            "allow_cors_origins": ["https://cached.com"],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(json_content, f)
            temp_path = Path(f.name)

        try:
            with patch.dict(
                os.environ, {CONFIG_FILE_PATH_ENV: str(temp_path)}, clear=False
            ):
                if SESSION_API_KEY_ENV in os.environ:
                    del os.environ[SESSION_API_KEY_ENV]
                # Clear the cache first
                import openhands.agent_server.config

                openhands.agent_server.config._default_config = None

                # First call
                config1 = get_default_config()
                # Second call
                config2 = get_default_config()

                # Should be the same object (cached)
                assert config1 is config2
                assert config1.session_api_keys == ["cached-key"]
                assert config1.allow_cors_origins == ["https://cached.com"]
        finally:
            temp_path.unlink()

    def test_get_default_config_nonexistent_custom_file(self):
        """Test get_default_config with non-existent custom config file."""
        with patch.dict(
            os.environ,
            {CONFIG_FILE_PATH_ENV: "/tmp/nonexistent_config.json"},
            clear=False,
        ):
            if SESSION_API_KEY_ENV in os.environ:
                del os.environ[SESSION_API_KEY_ENV]
            # Clear the cache first
            import openhands.agent_server.config

            openhands.agent_server.config._default_config = None

            config = get_default_config()

            # Should fall back to defaults
            assert config.session_api_keys == []
            assert config.allow_cors_origins == []
            assert config.conversations_path == Path("workspace/conversations")
            assert config.workspace_path == Path("workspace/project")
            assert config.static_files_path is None

    def test_get_default_config_env_override_only(self):
        """Test get_default_config with only environment variable override."""
        with patch.dict(os.environ, {SESSION_API_KEY_ENV: "env-only-key"}):
            with patch("pathlib.Path.exists", return_value=False):
                config = get_default_config()

                assert config.session_api_keys == ["env-only-key"]
                assert config.allow_cors_origins == []
                assert config.conversations_path == Path("workspace/conversations")
                assert config.workspace_path == Path("workspace/project")
                assert config.static_files_path is None

    def test_get_default_config_complex_json(self):
        """Test get_default_config with complex JSON structure."""
        json_content = {
            "session_api_key": "complex-key",
            "allow_cors_origins": [
                "https://app.example.com",
                "https://admin.example.com",
                "https://*.staging.example.com",
            ],
            "conversations_path": "data/conversations",
            "workspace_path": "data/workspace",
            "static_files_path": "data/static",
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(json_content, f)
            temp_path = Path(f.name)

        try:
            with patch.dict(
                os.environ, {CONFIG_FILE_PATH_ENV: str(temp_path)}, clear=False
            ):
                if SESSION_API_KEY_ENV in os.environ:
                    del os.environ[SESSION_API_KEY_ENV]
                # Clear the cache first
                import openhands.agent_server.config

                openhands.agent_server.config._default_config = None

                config = get_default_config()

                assert config.session_api_keys == ["complex-key"]
                assert len(config.allow_cors_origins) == 3
                assert "https://app.example.com" in config.allow_cors_origins
                assert "https://admin.example.com" in config.allow_cors_origins
                assert "https://*.staging.example.com" in config.allow_cors_origins
                assert config.conversations_path == Path("data/conversations")
                assert config.workspace_path == Path("data/workspace")
                assert config.static_files_path == Path("data/static")
        finally:
            temp_path.unlink()


class TestMultipleSessionAPIKeys:
    """Test multiple session API keys functionality."""

    def test_config_with_multiple_keys_from_json(self):
        """Test Config.from_json_file with multiple session API keys."""
        json_content = {
            "session_api_keys": ["key1", "key2", "key3"],
            "allow_cors_origins": ["https://example.com"],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(json_content, f)
            temp_path = Path(f.name)

        try:
            with patch.dict(os.environ, {}, clear=True):
                config = Config.from_json_file(temp_path)

                assert config.session_api_keys == ["key1", "key2", "key3"]
                assert config.allow_cors_origins == ["https://example.com"]
        finally:
            temp_path.unlink()

    def test_config_env_override_with_multiple_keys_in_json(self):
        """Test that env var overrides multiple keys in JSON."""
        json_content = {
            "session_api_keys": ["json-key1", "json-key2"],
            "allow_cors_origins": ["https://json.com"],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(json_content, f)
            temp_path = Path(f.name)

        try:
            with patch.dict(os.environ, {"SESSION_API_KEY": "env-override-key"}):
                config = Config.from_json_file(temp_path)

                # Environment variable should override JSON keys
                assert config.session_api_keys == ["env-override-key"]
                assert config.allow_cors_origins == ["https://json.com"]
        finally:
            temp_path.unlink()

    def test_config_mixed_format_compatibility(self):
        """Test that both old and new JSON formats work correctly."""
        # Test old format (singular key)
        old_json = {"session_api_key": "old-key"}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(old_json, f)
            old_path = Path(f.name)

        # Test new format (multiple keys)
        new_json = {"session_api_keys": ["new-key1", "new-key2"]}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(new_json, f)
            new_path = Path(f.name)

        try:
            with patch.dict(os.environ, {}, clear=True):
                old_config = Config.from_json_file(old_path)
                new_config = Config.from_json_file(new_path)

                assert old_config.session_api_keys == ["old-key"]
                assert new_config.session_api_keys == ["new-key1", "new-key2"]
        finally:
            old_path.unlink()
            new_path.unlink()


class TestConfigConstants:
    """Test cases for configuration constants."""

    def test_config_constants_defined(self):
        """Test that all required constants are defined."""
        assert CONFIG_FILE_PATH_ENV == "OPENHANDS_AGENT_SERVER_CONFIG_PATH"
        assert SESSION_API_KEY_ENV == "SESSION_API_KEY"
        assert (
            DEFAULT_CONFIG_FILE_PATH == "workspace/openhands_agent_server_config.json"
        )

    def test_constants_are_strings(self):
        """Test that constants are strings."""
        assert isinstance(CONFIG_FILE_PATH_ENV, str)
        assert isinstance(SESSION_API_KEY_ENV, str)
        assert isinstance(DEFAULT_CONFIG_FILE_PATH, str)
