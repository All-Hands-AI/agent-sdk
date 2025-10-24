import hashlib
from base64 import b64encode
from dataclasses import dataclass

from cryptography.fernet import Fernet
from pydantic import SecretStr


@dataclass
class Cipher:
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
        if secret is None:
            return None
        fernet = self._get_fernet()
        decrypted = fernet.decrypt(secret.encode()).decode()
        return SecretStr(decrypted)

    def _get_fernet(self):
        fernet = self._fernet
        if fernet is None:
            secret_key = self.secret_key.encode()
            fernet_key = b64encode(hashlib.sha256(secret_key).digest())
            fernet = Fernet(fernet_key)
            self._fernet = fernet
        return fernet
