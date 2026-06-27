import hashlib
import os

from cryptography.fernet import Fernet

from backend.config import settings

_fernet: Fernet | None = None
_master_key: str = ""


def _get_fernet() -> Fernet:
    global _fernet, _master_key
    if _fernet:
        return _fernet

    key = settings.OPENFEL_MASTER_KEY
    if not key:
        from backend.config import DATA_DIR
        key_file = DATA_DIR / ".openfel_master_key"
        if key_file.exists():
            key = key_file.read_text().strip()
        else:
            key = Fernet.generate_key().decode()
            key_file.write_text(key)
            print(f"\n  [OpenFEL] Generated master encryption key (saved to {key_file})")
            print(f"  Set OPENFEL_MASTER_KEY={key} in .env for production\n")

    _master_key = key
    _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet


def get_master_key() -> str:
    _get_fernet()
    return _master_key


def encrypt_credential(plaintext: str) -> str:
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_credential(ciphertext: str) -> str:
    return _get_fernet().decrypt(ciphertext.encode()).decode()


def generate_api_key() -> tuple[str, str, str]:
    """Returns (full_key, key_hash, key_prefix)."""
    from backend.config import settings
    raw = os.urandom(32).hex()
    full_key = f"{settings.API_KEY_PREFIX}{raw}"
    key_hash = hash_api_key(full_key)
    key_prefix = full_key[:20]
    return full_key, key_hash, key_prefix


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()
