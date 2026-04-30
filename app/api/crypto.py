import base64
import hashlib

from cryptography.fernet import Fernet

from app.api.config import ENCRYPTION_KEY


def _get_fernet() -> Fernet:
    if not ENCRYPTION_KEY:
        raise ValueError("ENCRYPTION_KEY no está configurada. Defínela como variable de entorno.")
    key = hashlib.sha256(ENCRYPTION_KEY.encode("utf-8")).digest()
    fernet_key = base64.urlsafe_b64encode(key)
    return Fernet(fernet_key)


def encrypt(plain_text: str) -> str:
    f = _get_fernet()
    return f.encrypt(plain_text.encode("utf-8")).decode("utf-8")


def decrypt(cipher_text: str) -> str:
    f = _get_fernet()
    return f.decrypt(cipher_text.encode("utf-8")).decode("utf-8")
