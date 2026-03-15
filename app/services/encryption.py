"""Encryption utilities using Fernet symmetric encryption."""

import base64

from cryptography.fernet import Fernet

from app.config import get_settings


def _get_fernet() -> Fernet:
    """Build a Fernet instance from the configured ENCRYPTION_KEY.

    The key may be stored as a URL-safe base64-encoded string (the native
    Fernet format) or as a raw string.  This helper normalises either form.
    """
    settings = get_settings()
    raw_key = settings.ENCRYPTION_KEY

    # If the key is already a valid Fernet key (URL-safe base64, 44 chars),
    # use it directly.
    try:
        return Fernet(raw_key.encode("utf-8") if isinstance(raw_key, str) else raw_key)
    except Exception:
        pass

    # Otherwise treat it as raw bytes and encode to URL-safe base64.
    key_bytes = raw_key.encode("utf-8") if isinstance(raw_key, str) else raw_key
    # Fernet requires exactly 32 bytes of key material, base64-encoded.
    if len(key_bytes) < 32:
        key_bytes = key_bytes.ljust(32, b"\0")
    elif len(key_bytes) > 32:
        key_bytes = key_bytes[:32]
    encoded = base64.urlsafe_b64encode(key_bytes)
    return Fernet(encoded)


def encrypt_value(value: str) -> str:
    """Encrypt a plaintext string and return the Fernet token as a string."""
    f = _get_fernet()
    return f.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_value(token: str) -> str:
    """Decrypt a Fernet token string and return the original plaintext."""
    f = _get_fernet()
    return f.decrypt(token.encode("utf-8")).decode("utf-8")
