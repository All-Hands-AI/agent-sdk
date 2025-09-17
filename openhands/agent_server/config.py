import json
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


# Environment variable constants
CONFIG_FILE_PATH_ENV = "OPENHANDS_AGENT_SERVER_CONFIG_PATH"
SESSION_API_KEY_ENV = "SESSION_API_KEY"

# Default config file location
DEFAULT_CONFIG_FILE_PATH = "workspace/openhands_agent_server_config.json"


class WebhookSpec(BaseModel):
    """Spec to create a webhook"""

    # General parameters
    event_buffer_size: int = Field(
        default=10,
        description=(
            "The number of events to buffer locally before posting to the webhook"
        ),
    )
    method: Literal["POST", "PUT", "PATCH"] = "POST"
    webhook_url: str = Field(
        description="The URL of the webhook to which to post lists of events"
    )
    headers: dict[str, str] = Field(default_factory=dict)

    # Retry parameters
    num_retries: int = Field(
        default=3,
        description="The number of times to retry if the post operation fails",
    )
    retry_delay: int = Field(default=5, description="The delay between retries")


class Config(BaseModel):
    """
    Immutable configuration for a server running in local mode.
    (Typically inside a sandbox).
    """

    session_api_key: str | None = Field(
        default=None,
        description=(
            "The session api key used to authenticate all incoming requests. "
            "None implies the server will be unsecured"
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
            "The location of the workspace directory where the agent reads/writes."
        ),
    )
    webhooks: list[WebhookSpec] = Field(
        default_factory=list,
        description="Webhooks to invoke in response to events",
    )
    model_config = {"frozen": True}

    @classmethod
    def from_json_file(cls, file_path: Path) -> "Config":
        """Load configuration from a JSON file with environment variable overrides."""
        config_data = {}

        # Load from JSON file if it exists
        if file_path.exists():
            with open(file_path, "r") as f:
                config_data = json.load(f) or {}
        # Apply environment variable overrides for legacy compatibility
        if session_api_key := os.getenv(SESSION_API_KEY_ENV):
            config_data["session_api_key"] = session_api_key

        # Convert string paths to Path objects
        if "conversations_path" in config_data:
            config_data["conversations_path"] = Path(config_data["conversations_path"])
        if "workspace_path" in config_data:
            config_data["workspace_path"] = Path(config_data["workspace_path"])

        return cls(**config_data)


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
