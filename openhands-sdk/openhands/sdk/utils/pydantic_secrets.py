from pydantic import SecretStr

from openhands.sdk.utils.cipher import Cipher


def serialize_secret(v: SecretStr | None, info):
    """
    Serialize secret fields with encryption or redaction.

    - If a cipher is provided in context, encrypts the secret value
    - If expose_secrets flag is True in context, exposes the actual value
    - Otherwise, lets Pydantic handle default masking (redaction)
    - This prevents accidental secret disclosure when sharing conversations
    """  # noqa: E501
    if v is None:
        return None

    # check if a cipher is supplied
    if info.context and info.context.get("cipher"):
        cipher: Cipher = info.context.get("cipher")
        return cipher.encrypt(v)

    # Check if the 'expose_secrets' flag is in the serialization context
    if info.context and info.context.get("expose_secrets"):
        return v.get_secret_value()

    # Let Pydantic handle the default masking
    return v


def validate_secret(v: SecretStr | None, info):
    """
    Deserialize secret fields, handling encryption and empty values.

    - Empty API keys are converted to None to allow boto3 to use alternative auth methods
    - If a cipher is provided in context, attempts to decrypt the value
    - If decryption fails, the cipher returns None and a warning is logged
    - This gracefully handles conversations encrypted with different keys
    """  # noqa: E501
    if v is None:
        return None

    # Handle both SecretStr and string inputs
    if isinstance(v, SecretStr):
        secret_value = v.get_secret_value()
    else:
        secret_value = v

    # If the secret is empty or whitespace-only, return None
    if not secret_value or not secret_value.strip():
        return None

    # check if a cipher is supplied
    if info.context and info.context.get("cipher"):
        cipher: Cipher = info.context.get("cipher")
        return cipher.decrypt(secret_value)

    return v
