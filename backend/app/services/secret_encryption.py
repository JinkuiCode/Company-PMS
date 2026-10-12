"""Versioned authenticated parameter encryption; never include secrets in errors."""
import base64
import binascii
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.core.config import settings

DOMAIN = b"pms.parameter-secret.v1"


class SecretEncryptionError(ValueError):
    pass


def _key(mode):
    source = settings.PARAMETER_ENCRYPTION_KEY if mode == "dedicated" else settings.SECRET_KEY
    if mode not in ("dedicated", "shared") or len(source.strip()) < 32:
        raise SecretEncryptionError("Parameter encryption key unavailable")
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=DOMAIN).derive(source.encode("utf-8"))


def encrypt_secret(value, parameter_code):
    mode = "dedicated" if settings.PARAMETER_ENCRYPTION_KEY else "shared"
    nonce = os.urandom(12)
    aad = DOMAIN + b":" + mode.encode("ascii") + b":" + parameter_code.encode("utf-8")
    encrypted = AESGCM(_key(mode)).encrypt(nonce, value.encode("utf-8"), aad)
    return "v1:" + mode + ":" + base64.urlsafe_b64encode(nonce + encrypted).decode("ascii")


def decrypt_secret(envelope, parameter_code):
    try:
        version, mode, payload = envelope.split(":", 2)
        if version != "v1" or mode not in ("dedicated", "shared"):
            raise SecretEncryptionError("Unsupported parameter encryption envelope")
        encrypted = base64.b64decode(payload, altchars=b"-_", validate=True)
        aad = DOMAIN + b":" + mode.encode("ascii") + b":" + parameter_code.encode("utf-8")
        return AESGCM(_key(mode)).decrypt(encrypted[:12], encrypted[12:], aad).decode("utf-8")
    except (ValueError, TypeError, AttributeError, UnicodeError, binascii.Error, InvalidTag):
        raise SecretEncryptionError("Parameter decryption unavailable") from None
