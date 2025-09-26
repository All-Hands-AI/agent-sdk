import json
import os
from pathlib import Path
from typing import get_origin

from pydantic import BaseModel, Field


# Environment variable constants
CONFIG_FILE_PATH_ENV = "OPENHANDS_AGENT_SERVER_CONFIG_PATH"
SESSION_API_KEY_ENV = "SESSION_API_KEY"

# Default config file location
DEFAULT_CONFIG_FILE_PATH = "workspace/openhands_agent_server_config.json"


class WebhookSpec(BaseModel):
    """Spec to create a webhook. All webhook requests use POST method."""

    # General parameters
    event_buffer_size: int = Field(
        default=10,
        ge=1,
        description=(
            "The number of events to buffer locally before posting to the webhook"
        ),
    )
    base_url: str = Field(
        description="The base URL of the webhook service. Events will be sent to "
        "{base_url}/events and conversation info to {base_url}/conversations"
    )
    headers: dict[str, str] = Field(default_factory=dict)
    flush_delay: float = Field(
        default=30.0,
        gt=0,
        description=(
            "The delay in seconds after which buffered events will be flushed to "
            "the webhook, even if the buffer is not full. Timer is reset on each "
            "new event."
        ),
    )

    # Retry parameters
    num_retries: int = Field(
        default=3,
        ge=0,
        description="The number of times to retry if the post operation fails",
    )
    retry_delay: int = Field(default=5, ge=0, description="The delay between retries")


class Config(BaseModel):
    """
    Immutable configuration for a server running in local mode.
    (Typically inside a sandbox).
    """

    session_api_keys: list[str] = Field(
        default_factory=list,
        description=(
            "List of valid session API keys used to authenticate incoming requests. "
            "Empty list implies the server will be unsecured. Any key in this list "
            "will be accepted for authentication."
        ),
    )
    allow_cors_origins: list[str] = Field(
        default_factory=list,
        description=(
            "Set of CORS origins permitted by this server (Anything from localhost is "
            "always accepted regardless of what's in here)."
        ),
    )
    conversations_path: Path = Field(
        default=Path("workspace/conversations"),
        description=(
            "The location of the directory where conversations and events are stored."
        ),
    )
    workspace_path: Path = Field(
        default=Path("workspace/project"),
        description=(
            "The location of the project directory where the agent reads/writes. "
            "Defaults to 'workspace/project'."
        ),
    )
    bash_events_dir: Path = Field(
        default=Path("workspace/bash_events"),
        description=(
            "The location of the directory where bash events are stored as files. "
            "Defaults to 'workspace/bash_events'."
        ),
    )
    static_files_path: Path | None = Field(
        default=None,
        description=(
            "The location of the directory containing static files to serve. "
            "If specified and the directory exists, static files will be served "
            "at the /static/ endpoint."
        ),
    )
    webhooks: list[WebhookSpec] = Field(
        default_factory=list,
        description="Webhooks to invoke in response to events",
    )
    enable_vscode: bool = Field(
        default=True,
        description="Whether to enable VSCode server functionality",
    )
    model_config = {"frozen": True}

    def _parse_env_value(self, env_value: str, field_type: type | None):
        """Parse environment variable value based on field type."""
        if field_type is bool:
            return env_value.lower() in ("true", "1", "yes", "on")
        elif field_type is int:
            return int(env_value)
        elif field_type is float:
            return float(env_value)
        elif field_type is Path:
            return Path(env_value)
        elif get_origin(field_type) is list:
            return env_value.split(",") if env_value.strip() else []
        else:
            return env_value

    def update_with_env_var(self) -> "Config":
        """Create a new Config instance with values overridden from env vars.

        Auto-generates UPPER_CASE env var mappings from model fields.
        """
        mappings = {name: name.upper() for name in self.__class__.model_fields}
        values = self.model_dump()

        for field_name, env_var in mappings.items():
            env_value = os.getenv(env_var)
            if not env_value or field_name not in values:
                continue

            try:
                field_type = self.__class__.model_fields[field_name].annotation
                if field_type is None:
                    # Skip fields without type annotations
                    continue
                values[field_name] = self._parse_env_value(env_value, field_type)
            except (ValueError, TypeError):
                # Skip invalid environment variable values
                continue

        return self.__class__(**values)

    @classmethod
    def from_json_file(cls, file_path: Path) -> "Config":
        """Load configuration from a JSON file with environment variable overrides."""
        config_data = {}

        # Load from JSON file if it exists
        if file_path.exists():
            with open(file_path) as f:
                config_data = json.load(f) or {}

        # Handle session API keys with backward compatibility
        session_api_keys = []

        # First, check for new plural format in JSON
        if "session_api_keys" in config_data:
            session_api_keys = config_data["session_api_keys"]
            # Remove the plural key to avoid conflicts
            del config_data["session_api_keys"]

        # Then, check for legacy singular format in JSON
        elif "session_api_key" in config_data and config_data["session_api_key"]:
            session_api_keys = [config_data["session_api_key"]]
            # Remove the singular key to avoid conflicts
            del config_data["session_api_key"]

        # Finally, apply environment variable override for legacy compatibility
        if session_api_key := os.getenv(SESSION_API_KEY_ENV):
            # If env var is set, it takes precedence and becomes the only key
            session_api_keys = [session_api_key]

        # Set the final session_api_keys
        config_data["session_api_keys"] = session_api_keys

        # Convert string paths to Path objects
        if "conversations_path" in config_data:
            config_data["conversations_path"] = Path(config_data["conversations_path"])
        if "workspace_path" in config_data:
            config_data["workspace_path"] = Path(config_data["workspace_path"])
        if "bash_events_dir" in config_data:
            config_data["bash_events_dir"] = Path(config_data["bash_events_dir"])
        if (
            "static_files_path" in config_data
            and config_data["static_files_path"] is not None
        ):
            config_data["static_files_path"] = Path(config_data["static_files_path"])

        # Create initial config and apply environment variable overrides
        config = cls(**config_data)
        return config.update_with_env_var()


_default_config: Config | None = None


def get_default_config():
    """Get the default local server config shared across the server"""
    global _default_config
    if _default_config is None:
        # Get config file path from environment variable or use default
        config_file_path = os.getenv(CONFIG_FILE_PATH_ENV, DEFAULT_CONFIG_FILE_PATH)
        config_path = Path(config_file_path)

        # Load configuration from JSON file with environment variable overrides
        _default_config = Config.from_json_file(config_path)
    return _default_config
