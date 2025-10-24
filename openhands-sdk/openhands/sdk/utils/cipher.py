"""
Cipher utility for preventing accidental secret disclosure in conversation trajectories.

This module provides encryption/decryption functionality designed to prevent accidental
leakage of sensitive information when serialized conversations are downloaded and
shared. If it is used in conjunction with the AgentServer when not using environment
variables, keys are stored on on the filesystem at ~/.openhands/secret_key and it
will NOT protect against attackers with read access!
"""

from dataclasses import dataclass

from cryptography.fernet import Fernet
from pydantic import SecretStr


@dataclass
class Cipher:
    """
    Simple encryption utility for preventing accidental secret disclosure.

    WARNING: This is designed to prevent accidental leakage of keys when sharing
    conversation trajectories, NOT to protect against attackers with full access
    to the file system. The encryption key is stored in plaintext on disk.

    When serializing without a cipher context, secret values are redacted rather
    than encrypted.
    """

    secret_key: str
    _fernet: Fernet | None = None

    def encrypt(self, secret: SecretStr | None) -> str | None:
        if secret is None:
            return None
        secret_value = secret.get_secret_value().encode()
        fernet = self._get_fernet()
        result = fernet.encrypt(secret_value).decode()
        return result

    def decrypt(self, secret: str | None) -> SecretStr | None:
        """
        Decrypt a secret value, returning None if decryption fails.

        This handles cases where existing conversations were serialized with different
        encryption keys or contain invalid encrypted data. A warning is logged when
        decryption fails.
        """
        if secret is None:
            return None
        try:
            fernet = self._get_fernet()
            decrypted = fernet.decrypt(secret.encode()).decode()
            return SecretStr(decrypted)
        except Exception as e:
            # Import here to avoid circular imports
            from openhands.sdk.logger import get_logger

            logger = get_logger(__name__)
            logger.warning(
                f"Failed to decrypt secret value (setting to None): {e}. "
                "This may occur when loading conversations encrypted with a "
                "different key."
            )
            return None

    def _get_fernet(self):
        fernet = self._fernet
        if fernet is None:
            # The secret_key is now directly a Fernet-compatible base64 key
            # No need for hashing - just use it directly
            fernet = Fernet(self.secret_key.encode("ascii"))
            self._fernet = fernet
        return fernet
