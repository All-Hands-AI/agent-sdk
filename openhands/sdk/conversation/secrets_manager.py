"""Secrets manager for handling sensitive data in conversations."""

import re
from typing import Callable, Dict

from openhands.sdk.logger import get_logger


logger = get_logger(__name__)


class SecretsManager:
    """Manages secrets and injects them into bash commands when needed.

    The secrets manager stores a mapping of secret keys to callable functions
    that retrieve the actual secret values. When a bash command is about to be
    executed, it scans the command for any secret keys and injects the corresponding
    environment variables.
    """

    def __init__(self) -> None:
        """Initialize an empty secrets manager."""
        self._secrets: Dict[str, Callable[[str], str]] = {}

    def add_secrets(self, secrets: Dict[str, Callable[[str], str]]) -> None:
        """Add secrets to the manager.

        Args:
            secrets: Dictionary mapping secret keys to callable functions.
                    Each callable takes a string (the key) and returns the secret value.
        """
        self._secrets.update(secrets)
        logger.debug(
            f"Added {len(secrets)} secrets. Total secrets: {len(self._secrets)}"
        )

    def get_secret_keys(self) -> set[str]:
        """Get all registered secret keys."""
        return set(self._secrets.keys())

    def find_secrets_in_text(self, text: str) -> set[str]:
        """Find all secret keys mentioned in the given text.

        Args:
            text: The text to search for secret keys

        Returns:
            Set of secret keys found in the text
        """
        found_keys = set()
        for key in self._secrets.keys():
            # Use word boundaries to match whole words only
            pattern = r"\b" + re.escape(key) + r"\b"
            if re.search(pattern, text, re.IGNORECASE):
                found_keys.add(key)
        return found_keys

    def inject_secrets_into_bash_command(self, command: str) -> str:
        """Inject secrets as environment variables into a bash command.

        Args:
            command: The original bash command

        Returns:
            Modified bash command with secret environment variables exported
        """
        found_secrets = self.find_secrets_in_text(command)

        if not found_secrets:
            return command

        logger.debug(f"Found secrets in command: {found_secrets}")

        # Build export statements for each found secret
        export_statements = []
        for key in found_secrets:
            try:
                secret_value = self._secrets[key](key)
                # Escape the secret value for bash
                escaped_value = secret_value.replace("'", "'\"'\"'")
                export_statements.append(f"export {key}='{escaped_value}'")
            except Exception as e:
                logger.error(f"Failed to retrieve secret for key '{key}': {e}")
                continue

        if not export_statements:
            return command

        # Combine export statements with the original command
        exports = " && ".join(export_statements)
        modified_command = f"{exports} && {command}"

        logger.debug(f"Injected {len(export_statements)} secrets into bash command")
        return modified_command

    def clear_secrets(self) -> None:
        """Clear all stored secrets."""
        count = len(self._secrets)
        self._secrets.clear()
        logger.debug(f"Cleared {count} secrets")

    def has_secrets(self) -> bool:
        """Check if any secrets are registered."""
        return len(self._secrets) > 0
