"""Secrets manager for handling sensitive data in conversations."""

from collections.abc import Mapping

from pydantic import SecretStr

from openhands.sdk.conversation.secret_source import (
    SecretSource,
    StaticSecret,
)
from openhands.sdk.logger import get_logger


logger = get_logger(__name__)

SecretValue = str | SecretSource


class SecretsManager:
    """Manages secrets and injects them into bash commands when needed.

    The secrets manager stores a mapping of secret keys to callable functions
    that retrieve the actual secret values. When a bash command is about to be
    executed, it scans the command for any secret keys and injects the corresponding
    environment variables.

    Additionally, it tracks the latest exported values to enable consistent masking
    even when callable secrets fail on subsequent calls.
    """

    def __init__(self) -> None:
        """Initialize an empty secrets manager."""
        self._secret_sources: dict[str, SecretSource] = {}
        # Track the latest successfully exported values for masking
        self._exported_values: dict[str, str] = {}

    def update_secrets(
        self,
        secrets: Mapping[str, SecretValue],
    ) -> None:
        """Add or update secrets in the manager.

        Args:
            secrets: Dictionary mapping secret keys to either string values
                    or callable functions that return string values
        """
        secret_sources = {name: _wrap_secret(value) for name, value in secrets.items()}
        self._secret_sources.update(secret_sources)

    def find_secrets_in_text(self, text: str) -> set[str]:
        """Find all secret keys mentioned in the given text.

        Args:
            text: The text to search for secret keys

        Returns:
            Set of secret keys found in the text
        """
        found_keys = set()
        for key in self._secret_sources.keys():
            if key.lower() in text.lower():
                found_keys.add(key)
        return found_keys

    def get_secrets_as_env_vars(self, command: str) -> dict[str, str]:
        """Get secrets that should be exported as environment variables for a command.

        Args:
            command: The bash command to check for secret references

        Returns:
            Dictionary of environment variables to export (key -> value)
        """
        found_secrets = self.find_secrets_in_text(command)

        if not found_secrets:
            return {}

        logger.debug(f"Found secrets in command: {found_secrets}")

        env_vars = {}
        for key in found_secrets:
            try:
                source = self._secret_sources[key]
                value = source.get_value()
                if value:
                    env_vars[key] = value
                    # Track successfully exported values for masking
                    self._exported_values[key] = value
            except Exception as e:
                logger.error(f"Failed to retrieve secret for key '{key}': {e}")
                continue

        logger.debug(f"Prepared {len(env_vars)} secrets as environment variables")
        return env_vars

    def mask_secrets_in_output(self, text: str) -> str:
        """Mask secret values in the given text.

        This method uses both the current exported values and attempts to get
        fresh values from callables to ensure comprehensive masking.

        Args:
            text: The text to mask secrets in

        Returns:
            Text with secret values replaced by <secret-hidden>
        """
        if not text:
            return text

        masked_text = text

        # First, mask using currently exported values (always available)
        for value in self._exported_values.values():
            masked_text = masked_text.replace(value, "<secret-hidden>")

        return masked_text


def _wrap_secret(value: SecretValue) -> SecretSource:
    """Convert the value given to a secret source"""
    if isinstance(value, SecretSource):
        return value
    if isinstance(value, str):
        return StaticSecret(value=SecretStr(value))
    raise ValueError("Invalid SecretValue")
