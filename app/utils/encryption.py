"""
Encryption Utility
Fernet symmetric encryption for file storage
"""
import base64
import logging
from pathlib import Path
from typing import Union

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings

logger = logging.getLogger(__name__)


class EncryptionService:
    """
    Fernet symmetric encryption for document storage.

    Fernet guarantees:
    - AES-128-CBC encryption
    - HMAC-SHA256 authentication
    - Timestamp for token expiry
    """

    def __init__(self):
        key = settings.ENCRYPTION_KEY
        if isinstance(key, str):
            key = key.encode()
        self._fernet = Fernet(key)

    def encrypt_bytes(self, data: bytes) -> bytes:
        """Encrypt raw bytes"""
        return self._fernet.encrypt(data)

    def decrypt_bytes(self, encrypted_data: bytes) -> bytes:
        """Decrypt encrypted bytes. Raises InvalidToken if tampered."""
        try:
            return self._fernet.decrypt(encrypted_data)
        except InvalidToken:
            logger.error("Decryption failed — data may be tampered or key mismatch")
            raise ValueError("Decryption failed: invalid or corrupted data")

    def encrypt_file(self, source_path: Union[str, Path], dest_path: Union[str, Path]) -> None:
        """Encrypt file from source_path and write to dest_path"""
        source_path = Path(source_path)
        dest_path = Path(dest_path)
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        with open(source_path, "rb") as f:
            plaintext = f.read()

        encrypted = self.encrypt_bytes(plaintext)

        with open(dest_path, "wb") as f:
            f.write(encrypted)

        logger.debug(f"File encrypted: {source_path} → {dest_path}")

    def decrypt_file(self, encrypted_path: Union[str, Path]) -> bytes:
        """Read and decrypt an encrypted file, return plaintext bytes"""
        encrypted_path = Path(encrypted_path)

        with open(encrypted_path, "rb") as f:
            encrypted_data = f.read()

        return self.decrypt_bytes(encrypted_data)

    @staticmethod
    def generate_key() -> str:
        """Generate a new Fernet key (run once at setup)"""
        return Fernet.generate_key().decode()