"""
Cipher utility for preventing accidental secret disclosure in conversation trajectories.

OBJECTIVE: Prevent accidental leakage of keys in the common case where serialized
conversations are downloaded and shared. Keys written to logs are redacted rather
than encrypted (when no cipher is passed to the dump operation).

SECURITY WARNINGS:
- This is NOT designed to thwart attackers with full filesystem access
- The encryption key is stored in plaintext at ~/.openhands/secret_key
- Values written to logs are redacted, not encrypted, for better security
- This provides protection against accidental leakage but will NOT protect
  against attackers with read access to the filesystem
- Existing conversations may fail to deserialize due to encryption changes,
  but this is acceptable as secrets were being redacted anyway

For maximum security against determined attackers, use the OH_SECRET_KEY
environment variable with a securely managed key.
"""

import hashlib
from base64 import b64encode
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
        decryption fails. The inability to deserialize existing conversations is
        acceptable since the objective is to prevent accidental key leakage in
        shared conversations, not to maintain backwards compatibility.
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
                "This may occur when loading conversations encrypted with a different "
                "key or when upgrading from older versions. This is acceptable "
                "behavior since the objective is to prevent accidental key leakage, "
                "not to preserve backwards compatibility with improperly stored "
                "secrets."
            )
            return None

    def _get_fernet(self):
        fernet = self._fernet
        if fernet is None:
            secret_key = self.secret_key.encode()
            # Has the key to make sure we have a 256 bit value
            fernet_key = b64encode(hashlib.sha256(secret_key).digest())
            fernet = Fernet(fernet_key)
            self._fernet = fernet
        return fernet
