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

        assert config.session_api_key is None
        assert config.allow_cors_origins == []
        assert config.conversations_path == Path("workspace/conversations")
        assert config.workspace_path == Path("workspace/project")

    def test_config_with_custom_values(self):
        """Test Config creation with custom values."""
        config = Config(
            session_api_key="test-key",
            allow_cors_origins=["https://example.com"],
            conversations_path=Path("custom/conversations"),
            workspace_path=Path("custom/workspace"),
        )

        assert config.session_api_key == "test-key"
        assert config.allow_cors_origins == ["https://example.com"]
        assert config.conversations_path == Path("custom/conversations")
        assert config.workspace_path == Path("custom/workspace")

    def test_config_immutable(self):
        """Test that Config is immutable (frozen)."""
        config = Config()

        with pytest.raises(Exception):  # pydantic ValidationError or similar
            config.session_api_key = "new-key"

    def test_from_json_file_nonexistent_file(self):
        """Test loading from a non-existent JSON file returns defaults."""
        non_existent_path = Path("/tmp/nonexistent_config.json")
        config = Config.from_json_file(non_existent_path)

        assert config.session_api_key is None
        assert config.allow_cors_origins == []
        assert config.conversations_path == Path("workspace/conversations")
        assert config.workspace_path == Path("workspace/project")

    def test_from_json_file_empty_file(self):
        """Test loading from an empty JSON file returns defaults."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{}")
            temp_path = Path(f.name)

        try:
            config = Config.from_json_file(temp_path)

            assert config.session_api_key is None
            assert config.allow_cors_origins == []
            assert config.conversations_path == Path("workspace/conversations")
            assert config.workspace_path == Path("workspace/project")
        finally:
            temp_path.unlink()

    def test_from_json_file_with_values(self):
        """Test loading from a JSON file with custom values."""
        json_content = {
            "session_api_key": "json-key",
            "allow_cors_origins": ["https://json.com", "https://test.com"],
            "conversations_path": "json/conversations",
            "workspace_path": "json/workspace",
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(json_content, f)
            temp_path = Path(f.name)

        try:
            config = Config.from_json_file(temp_path)

            assert config.session_api_key == "json-key"
            assert config.allow_cors_origins == ["https://json.com", "https://test.com"]
            assert config.conversations_path == Path("json/conversations")
            assert config.workspace_path == Path("json/workspace")
        finally:
            temp_path.unlink()

    def test_from_json_file_with_env_override(self):
        """Test that environment variables override JSON file values."""
        json_content = {
            "session_api_key": "json-key",
            "allow_cors_origins": ["https://json.com"],
            "conversations_path": "json/conversations",
            "workspace_path": "json/workspace",
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(json_content, f)
            temp_path = Path(f.name)

        try:
            with patch.dict(os.environ, {SESSION_API_KEY_ENV: "env-override-key"}):
                config = Config.from_json_file(temp_path)

                # Environment variable should override JSON value
                assert config.session_api_key == "env-override-key"
                # Other values should come from JSON
                assert config.allow_cors_origins == ["https://json.com"]
                assert config.conversations_path == Path("json/conversations")
                assert config.workspace_path == Path("json/workspace")
        finally:
            temp_path.unlink()

    def test_from_json_file_env_override_only(self):
        """Test environment variable override with no JSON file."""
        non_existent_path = Path("/tmp/nonexistent_config.json")

        with patch.dict(os.environ, {SESSION_API_KEY_ENV: "env-only-key"}):
            config = Config.from_json_file(non_existent_path)

            assert config.session_api_key == "env-only-key"
            assert config.allow_cors_origins == []
            assert config.conversations_path == Path("workspace/conversations")
            assert config.workspace_path == Path("workspace/project")

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
            config = Config.from_json_file(temp_path)

            assert config.session_api_key == "partial-key"
            assert config.allow_cors_origins == ["https://partial.com"]
            # Should use defaults for unspecified values
            assert config.conversations_path == Path("workspace/conversations")
            assert config.workspace_path == Path("workspace/project")
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

                assert config.session_api_key is None
                assert config.allow_cors_origins == []
                assert config.conversations_path == Path("workspace/conversations")
                assert config.workspace_path == Path("workspace/project")

    def test_get_default_config_with_default_file(self):
        """Test get_default_config using the default config file."""
        json_content = {
            "session_api_key": "default-file-key",
            "allow_cors_origins": ["https://default.com"],
            "conversations_path": "default/conversations",
            "workspace_path": "default/workspace",
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

                    assert config.session_api_key == "default-file-key"
                    assert config.allow_cors_origins == ["https://default.com"]
                    assert config.conversations_path == Path("default/conversations")
                    assert config.workspace_path == Path("default/workspace")
        finally:
            temp_path.unlink()

    def test_get_default_config_with_custom_file_path(self):
        """Test get_default_config with custom config file path from environment."""
        json_content = {
            "session_api_key": "custom-file-key",
            "allow_cors_origins": ["https://custom.com"],
            "conversations_path": "custom/conversations",
            "workspace_path": "custom/workspace",
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(json_content, f)
            temp_path = Path(f.name)

        try:
            with patch.dict(os.environ, {CONFIG_FILE_PATH_ENV: str(temp_path)}):
                config = get_default_config()

                assert config.session_api_key == "custom-file-key"
                assert config.allow_cors_origins == ["https://custom.com"]
                assert config.conversations_path == Path("custom/conversations")
                assert config.workspace_path == Path("custom/workspace")
        finally:
            temp_path.unlink()

    def test_get_default_config_with_env_override(self):
        """Test get_default_config with environment variable override."""
        json_content = {
            "session_api_key": "file-key",
            "allow_cors_origins": ["https://file.com"],
            "conversations_path": "file/conversations",
            "workspace_path": "file/workspace",
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
                assert config.session_api_key == "env-override-key"
                # Other values should come from file
                assert config.allow_cors_origins == ["https://file.com"]
                assert config.conversations_path == Path("file/conversations")
                assert config.workspace_path == Path("file/workspace")
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
            with patch.dict(os.environ, {CONFIG_FILE_PATH_ENV: str(temp_path)}):
                # First call
                config1 = get_default_config()
                # Second call
                config2 = get_default_config()

                # Should be the same object (cached)
                assert config1 is config2
                assert config1.session_api_key == "cached-key"
                assert config1.allow_cors_origins == ["https://cached.com"]
        finally:
            temp_path.unlink()

    def test_get_default_config_nonexistent_custom_file(self):
        """Test get_default_config with non-existent custom config file."""
        with patch.dict(
            os.environ, {CONFIG_FILE_PATH_ENV: "/tmp/nonexistent_config.json"}
        ):
            config = get_default_config()

            # Should fall back to defaults
            assert config.session_api_key is None
            assert config.allow_cors_origins == []
            assert config.conversations_path == Path("workspace/conversations")
            assert config.workspace_path == Path("workspace/project")

    def test_get_default_config_env_override_only(self):
        """Test get_default_config with only environment variable override."""
        with patch.dict(os.environ, {SESSION_API_KEY_ENV: "env-only-key"}):
            with patch("pathlib.Path.exists", return_value=False):
                config = get_default_config()

                assert config.session_api_key == "env-only-key"
                assert config.allow_cors_origins == []
                assert config.conversations_path == Path("workspace/conversations")
                assert config.workspace_path == Path("workspace/project")

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
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(json_content, f)
            temp_path = Path(f.name)

        try:
            with patch.dict(os.environ, {CONFIG_FILE_PATH_ENV: str(temp_path)}):
                config = get_default_config()

                assert config.session_api_key == "complex-key"
                assert len(config.allow_cors_origins) == 3
                assert "https://app.example.com" in config.allow_cors_origins
                assert "https://admin.example.com" in config.allow_cors_origins
                assert "https://*.staging.example.com" in config.allow_cors_origins
                assert config.conversations_path == Path("data/conversations")
                assert config.workspace_path == Path("data/workspace")
        finally:
            temp_path.unlink()


class TestConfigConstants:
    """Test cases for configuration constants."""

    def test_config_constants_defined(self):
        """Test that all required constants are defined."""
        assert CONFIG_FILE_PATH_ENV == "openhands_CONFIG_PATH"
        assert SESSION_API_KEY_ENV == "SESSION_API_KEY"
        assert DEFAULT_CONFIG_FILE_PATH == "workspace/openhands_sdk_config.json"

    def test_constants_are_strings(self):
        """Test that constants are strings."""
        assert isinstance(CONFIG_FILE_PATH_ENV, str)
        assert isinstance(SESSION_API_KEY_ENV, str)
        assert isinstance(DEFAULT_CONFIG_FILE_PATH, str)
