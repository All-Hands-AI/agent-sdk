"""Secrets manager for handling sensitive data in conversations."""

from typing import Callable, Mapping

from openhands.sdk.logger import get_logger


logger = get_logger(__name__)

SecretProvider = Callable[[], str]
SecretValue = str | SecretProvider


class SecretsManager:
    """Manages secrets and injects them into bash commands when needed.

    The secrets manager stores a mapping of secret keys to callable functions
    that retrieve the actual secret values. When a bash command is about to be
    executed, it scans the command for any secret keys and injects the corresponding
    environment variables.
    """

    def __init__(self) -> None:
        """Initialize an empty secrets manager."""
        self._secrets: dict[str, SecretValue] = {}

    def update_secrets(
        self,
        secrets: Mapping[str, SecretValue],
    ) -> None:
        """Add or update secrets in the manager.

        Args:
            secrets: Dictionary mapping secret keys to either string values
                    or callable functions that return string values
        """
        self._secrets.update(secrets)

    def find_secrets_in_text(self, text: str) -> set[str]:
        """Find all secret keys mentioned in the given text.

        Args:
            text: The text to search for secret keys

        Returns:
            Set of secret keys found in the text
        """
        found_keys = set()
        for key in self._secrets.keys():
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
                provider_or_value = self._secrets[key]
                value = (
                    provider_or_value()
                    if callable(provider_or_value)
                    else provider_or_value
                )
                env_vars[key] = value
            except Exception as e:
                logger.error(f"Failed to retrieve secret for key '{key}': {e}")
                continue

        logger.debug(f"Prepared {len(env_vars)} secrets as environment variables")
        return env_vars
