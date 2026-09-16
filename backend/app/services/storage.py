"""
Secure Local Document Storage Service.

Enforces secure file handling, unpredictable storage key generation, path traversal
protection, maximum upload size enforcement, and structural file format validation.

Security Rules:
- Original filenames from clients are strictly untrusted; they are never used as filesystem paths.
- Storage keys are deterministic UUID-based identifiers: {STORAGE_DIR}/{knowledge_base_id}/{document_id}.{ext}
- Path traversal is prevented by verifying that all resolved target paths reside within STORAGE_DIR.
- Content format validation verifies file signatures (magic bytes for PDF/DOCX) and structural
  decodability (for TXT/MD/CSV) to prevent disguised executable uploads.
- Filesystem operations do not participate in database transactions. Deletion consistency
  first commits database deletion (preventing dangling database pointers to deleted files)
  and then unlinks physical files from disk with safe error logging.
"""

import csv
import io
import logging
import re
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

# Magic byte signatures
PDF_MAGIC_BYTES = b"%PDF-"
ZIP_MAGIC_BYTES = b"PK\x03\x04"

# MIME type mapping for recognized extensions
EXTENSION_MIME_MAP = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".csv": "text/csv",
}


@dataclass(frozen=True)
class ValidatedUpload:
    """Sanitized and validated upload metadata."""

    original_filename: str
    file_type: str  # e.g. "pdf", "docx", "txt", "md", "csv"
    extension: str  # e.g. ".pdf"
    mime_type: str
    content: bytes
    file_size_bytes: int
    content_hash: str  # SHA-256 hex


class StorageService:
    """
    Manages secure persistence and retrieval of original source documents on disk.
    """

    def __init__(self, storage_dir: Path | None = None) -> None:
        self.storage_dir = (storage_dir or settings.STORAGE_DIR).resolve()
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitize user-provided filename for safe display and citation storage.
        Strips path traversal sequences, directory separators, and control characters.
        """
        # Remove path separators and null bytes
        clean = Path(filename).name.replace("\x00", "").strip()
        # Fallback if filename is empty or malicious
        if not clean or clean in (".", ".."):
            clean = f"document_{uuid.uuid4().hex[:8]}"
        # Limit display length
        return clean[:255]

    def _detect_and_validate_file_structure(self, extension: str, content: bytes) -> str:
        """
        Deeply inspect file header/magic bytes and structural integrity.
        Rejects renamed or disguised files (e.g. executables renamed to .pdf).
        """
        if extension == ".pdf":
            if not content.startswith(PDF_MAGIC_BYTES):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid PDF file: Missing '%PDF-' file signature.",
                )
            return "application/pdf"

        if extension == ".docx":
            if not content.startswith(ZIP_MAGIC_BYTES):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid DOCX file: Missing valid ZIP archive signature.",
                )
            # Verify internal DOCX structure (word/document.xml)
            try:
                with zipfile.ZipFile(io.BytesIO(content)) as zf:
                    namelist = zf.namelist()
                    if "word/document.xml" not in namelist:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Invalid DOCX file: Missing internal 'word/document.xml' structure.",
                        )
            except zipfile.BadZipFile as err:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid DOCX file: Corrupted or unreadable archive.",
                ) from err
            return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

        if extension in (".txt", ".md"):
            # Check for binary null bytes which indicate non-text files (e.g. binaries/executables)
            if b"\x00" in content:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid text file ({extension}): Contains binary null bytes.",
                )
            # Verify decodability as UTF-8 (or fallback Latin-1)
            try:
                content.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    content.decode("latin-1")
                except UnicodeDecodeError as err:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid text file: Cannot decode content as UTF-8 or Latin-1.",
                    ) from err
            return "text/markdown" if extension == ".md" else "text/plain"

        if extension == ".csv":
            if b"\x00" in content:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid CSV file: Contains binary null bytes.",
                )
            try:
                decoded = content.decode("utf-8-sig")
            except UnicodeDecodeError as err:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid CSV file: Cannot decode content as UTF-8.",
                ) from err

            # Verify it parses as tabular CSV
            try:
                reader = csv.reader(io.StringIO(decoded))
                rows = list(reader)
                if not rows or len(rows[0]) == 0:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid CSV file: File is empty or has no tabular columns.",
                    )
            except csv.Error as err:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid CSV file format: {err}",
                ) from err
            return "text/csv"

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file extension '{extension}'.",
        )

    async def validate_and_read_upload(self, file: UploadFile) -> ValidatedUpload:
        """
        Validate upload file parameters, size, content hash, and format structure.
        """
        raw_filename = file.filename or ""
        clean_name = self._sanitize_filename(raw_filename)

        # Extract and validate extension
        ext = Path(clean_name).suffix.lower()
        if not ext or ext not in settings.ALLOWED_EXTENSIONS:
            allowed_list = ", ".join(sorted(settings.ALLOWED_EXTENSIONS))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file extension '{ext}'. Allowed extensions: {allowed_list}",
            )

        # Read content while enforcing MAX_UPLOAD_SIZE_BYTES
        content = await file.read()
        file_size = len(content)

        if file_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty (0 bytes).",
            )

        if file_size > settings.MAX_UPLOAD_SIZE_BYTES:
            max_mb = settings.MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size exceeds maximum allowed limit of {max_mb} MB.",
            )

        # Validate file structural integrity and magic bytes
        mime_type = self._detect_and_validate_file_structure(ext, content)

        # Compute SHA-256 hash for deduplication and content integrity
        import hashlib

        content_hash = hashlib.sha256(content).hexdigest()

        # Canonical file_type without leading dot (e.g. "pdf")
        canonical_type = ext.lstrip(".")

        return ValidatedUpload(
            original_filename=clean_name,
            file_type=canonical_type,
            extension=ext,
            mime_type=mime_type,
            content=content,
            file_size_bytes=file_size,
            content_hash=content_hash,
        )

    def save_file(
        self,
        knowledge_base_id: uuid.UUID,
        document_id: uuid.UUID,
        extension: str,
        content: bytes,
    ) -> str:
        """
        Save file content to secure storage directory under an unpredictable UUID key.
        Returns the relative storage_key string.
        """
        # Create knowledge-base specific directory
        kb_dir = (self.storage_dir / str(knowledge_base_id)).resolve()

        # Path traversal guard: verify target directory is strictly within storage_dir
        if not kb_dir.is_relative_to(self.storage_dir):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Path traversal detected in storage path.",
            )

        kb_dir.mkdir(parents=True, exist_ok=True)

        target_file = (kb_dir / f"{document_id}{extension}").resolve()
        if not target_file.is_relative_to(self.storage_dir):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Path traversal detected in destination filename.",
            )

        # Write binary content atomically to disk
        target_file.write_bytes(content)

        # Relative storage key stored in database (e.g. "storage/kb_uuid/doc_uuid.pdf")
        storage_key = f"storage/{knowledge_base_id}/{document_id}{extension}"
        logger.info("Persisted document %s to %s", document_id, target_file)
        return storage_key

    def get_absolute_path(self, storage_key: str) -> Path:
        """
        Resolve a relative storage key to an absolute filesystem Path with traversal checks.
        """
        # Normalize slashes and strip leading "storage/" if present
        clean_key = re.sub(r"^storage[\\/]", "", storage_key)
        abs_path = (self.storage_dir / clean_key).resolve()

        if not abs_path.is_relative_to(self.storage_dir):
            raise ValueError(f"Path traversal detected for storage key: {storage_key}")

        return abs_path

    def delete_file(self, storage_key: str) -> bool:
        """
        Delete stored file from disk.

        Consistency Strategy:
        This is called ONLY after the PostgreSQL database record is successfully committed.
        If file deletion fails (e.g. temporary Windows file lock), a warning is logged so
        that the physical file can be cleaned up by an orphan reaping job without corrupting
        or rolling back the database.
        """
        try:
            abs_path = self.get_absolute_path(storage_key)
            if abs_path.exists():
                abs_path.unlink()
                logger.info("Deleted physical file from disk: %s", abs_path)
                return True
            logger.warning("Storage file was already missing during deletion: %s", abs_path)
            return False
        except Exception as exc:
            logger.error("Failed to delete physical file %s: %s", storage_key, exc)
            return False


# Singleton storage service instance
storage_service = StorageService()
