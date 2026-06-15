from cryptography.fernet import Fernet

from socialstack.utils.errors import EncryptionError


def get_fernet(key: str) -> Fernet:
    if not key:
        raise EncryptionError("TOKEN_ENCRYPTION_KEY is not set")
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception as e:
        raise EncryptionError(f"Invalid encryption key: {e}") from e


def encrypt_token(token: str, key: str) -> str:
    f = get_fernet(key)
    return f.encrypt(token.encode()).decode()


def decrypt_token(encrypted: str, key: str) -> str:
    f = get_fernet(key)
    try:
        return f.decrypt(encrypted.encode()).decode()
    except Exception as e:
        raise EncryptionError(f"Token decryption failed: {e}") from e


def generate_key() -> str:
    return Fernet.generate_key().decode()
