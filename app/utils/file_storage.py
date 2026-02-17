"""
File Storage Utility
Handles upload, encrypted storage, and retrieval of claim documents
"""
import hashlib
import logging
import os
import uuid
from pathlib import Path
from typing import Optional, Tuple

from app.config import settings
from app.utils.encryption import EncryptionService
from app.core.exceptions import FileTooLargeException, InvalidFileTypeException

logger = logging.getLogger(__name__)

ALLOWED_MIME_TYPES = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "audio/wav": ".wav",
    "audio/mpeg": ".mp3",
}


class FileStorageService:
    """
    Encrypted file storage for claim documents.

    Flow:
    1. Validate file (size, MIME type)
    2. Generate unique storage path
    3. Encrypt file
    4. Store encrypted bytes
    5. Return storage reference (path)

    Storage is NEVER plaintext on disk.
    """

    def __init__(self):
        self.upload_dir = Path(settings.UPLOAD_DIR)
        self.encrypted_dir = Path(settings.ENCRYPTED_STORAGE_DIR)
        self.max_size = settings.MAX_UPLOAD_SIZE
        self.encryption = EncryptionService()

        # Ensure directories exist
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.encrypted_dir.mkdir(parents=True, exist_ok=True)

    def store_document(
        self,
        file_bytes: bytes,
        content_type: str,
        claim_id: str,
        original_filename: str = "document",
    ) -> str:
        """
        Validate, encrypt, and store a document.

        Args:
            file_bytes: Raw file bytes
            content_type: MIME type from upload
            claim_id: Claim UUID (used for path namespacing)
            original_filename: Original filename (for extension)

        Returns:
            Encrypted storage path reference (stored in DB)

        Raises:
            FileTooLargeException
            InvalidFileTypeException
        """
        # Validate size
        if len(file_bytes) > self.max_size:
            raise FileTooLargeException(self.max_size // (1024 * 1024))

        # Validate content type
        if content_type not in ALLOWED_MIME_TYPES:
            raise InvalidFileTypeException(list(ALLOWED_MIME_TYPES.keys()))

        # Generate unique filename
        extension = ALLOWED_MIME_TYPES[content_type]
        unique_name = f"{uuid.uuid4().hex}{extension}"

        # Namespace by claim ID
        claim_dir = self.encrypted_dir / claim_id
        claim_dir.mkdir(parents=True, exist_ok=True)

        encrypted_path = claim_dir / f"{unique_name}.enc"

        # Encrypt and write
        encrypted_bytes = self.encryption.encrypt_bytes(file_bytes)
        with open(encrypted_path, "wb") as f:
            f.write(encrypted_bytes)

        # Return relative path (stored in DB)
        storage_ref = str(encrypted_path.relative_to(self.encrypted_dir))

        logger.info(
            f"Document stored: claim={claim_id} "
            f"size={len(file_bytes)} bytes "
            f"type={content_type} "
            f"ref={storage_ref}"
        )

        return storage_ref

    def retrieve_document(self, storage_ref: str) -> bytes:
        """
        Retrieve and decrypt a document.

        Args:
            storage_ref: Storage reference from DB

        Returns:
            Decrypted file bytes
        """
        encrypted_path = self.encrypted_dir / storage_ref

        if not encrypted_path.exists():
            raise FileNotFoundError(f"Document not found: {storage_ref}")

        decrypted = self.encryption.decrypt_file(encrypted_path)

        logger.debug(f"Document retrieved: {storage_ref}")
        return decrypted

    def delete_document(self, storage_ref: str) -> bool:
        """
        Securely delete a document (shred then remove).
        Only called after retention period expires.

        Args:
            storage_ref: Storage reference from DB

        Returns:
            True if deleted
        """
        encrypted_path = self.encrypted_dir / storage_ref

        if not encrypted_path.exists():
            logger.warning(f"Attempted to delete non-existent document: {storage_ref}")
            return False

        # Overwrite with zeros before deletion (basic secure erase)
        file_size = os.path.getsize(encrypted_path)
        with open(encrypted_path, "wb") as f:
            f.write(b"\x00" * file_size)

        os.remove(encrypted_path)

        logger.info(f"Document securely deleted: {storage_ref}")
        return True

    def compute_file_hash(self, file_bytes: bytes) -> str:
        """
        Compute SHA-256 hash of file bytes.
        Used for duplicate detection and integrity verification.

        Args:
            file_bytes: Raw file bytes

        Returns:
            Hex SHA-256 digest
        """
        return hashlib.sha256(file_bytes).hexdigest()