from cryptography.fernet import Fernet
from .config import settings
import base64
import hashlib

def _get_cipher():
    key = hashlib.sha256(settings.ENCRYPTION_KEY.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(key)
    return Fernet(fernet_key)

def encrypt_api_key(plain_text: str) -> str:
    if not plain_text:
        return ""
    cipher = _get_cipher()
    return cipher.encrypt(plain_text.encode()).decode()

def decrypt_api_key(encrypted_text: str) -> str:
    if not encrypted_text:
        return ""
    try:
        cipher = _get_cipher()
        return cipher.decrypt(encrypted_text.encode()).decode()
    except Exception:
        return ""
