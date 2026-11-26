import re
from typing import Set, Tuple, Optional, Dict
from fastapi import HTTPException, UploadFile, status

# Allowed file extensions and corresponding MIME types for KYC & platform uploads
ALLOWED_EXTENSIONS: Set[str] = {".pdf", ".jpg", ".jpeg", ".png"}
ALLOWED_MIME_TYPES: Set[str] = {
    "application/pdf",
    "image/jpeg",
    "image/png"
}

# Magic numbers (file signatures)
FILE_SIGNATURES: Dict[str, bytes] = {
    "pdf": b"%PDF-",
    "jpeg": b"\xff\xd8\xff",
    "png": b"\x89PNG\r\n\x1a\n"
}

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 Megabytes


def validate_file_upload(
    file: UploadFile,
    max_size: int = MAX_FILE_SIZE_BYTES,
    allowed_exts: Optional[Set[str]] = None,
    allowed_mimes: Optional[Set[str]] = None
) -> Tuple[bool, str]:
    """
    Validates uploaded file against size limits, file extension whitelist,
    MIME type whitelist, and binary magic bytes inspection.
    """
    allowed_exts = allowed_exts or ALLOWED_EXTENSIONS
    allowed_mimes = allowed_mimes or ALLOWED_MIME_TYPES

    filename = file.filename or ""
    dot_idx = filename.rfind(".")
    if dot_idx == -1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File has no extension. Upload rejected."
        )

    ext = filename[dot_idx:].lower()
    if ext not in allowed_exts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file extension '{ext}'. Allowed extensions: {list(allowed_exts)}"
        )

    content_type = (file.content_type or "").lower()
    if content_type not in allowed_mimes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported MIME type '{content_type}'. Allowed types: {list(allowed_mimes)}"
        )

    # Read header bytes to verify magic number signature
    header = file.file.read(16)
    file.file.seek(0)  # Reset pointer back to beginning

    if len(header) < 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty or corrupted file content."
        )

    is_valid_signature = False
    if ext == ".pdf" and header.startswith(b"%PDF-"):
        is_valid_signature = True
    elif ext in [".jpg", ".jpeg"] and header.startswith(b"\xff\xd8\xff"):
        is_valid_signature = True
    elif ext == ".png" and header.startswith(b"\x89PNG\r\n\x1a\n"):
        is_valid_signature = True

    if not is_valid_signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File content signature does not match claimed file type. Upload rejected."
        )

    # Verify file size
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Reset back to start

    if file_size > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of {max_size // (1024 * 1024)}MB."
        )

    return True, ext


XSS_PATTERNS = [
    re.compile(r'<script.*?>.*?</script>', re.IGNORECASE | re.DOTALL),
    re.compile(r'javascript:', re.IGNORECASE),
    re.compile(r'onload\s*=', re.IGNORECASE),
    re.compile(r'onerror\s*=', re.IGNORECASE),
    re.compile(r'eval\(', re.IGNORECASE),
    re.compile(r'<iframe.*?>', re.IGNORECASE),
]


def sanitize_text(value: str) -> str:
    """Sanitizes text strings against XSS attacks and script injection."""
    if not isinstance(value, str):
        return value
    sanitized = value
    for pattern in XSS_PATTERNS:
        sanitized = pattern.sub('', sanitized)
    return sanitized.strip()


def validate_safe_input(value: str, field_name: str = "Input") -> str:
    """Rejects strings containing malicious script tags or dangerous javascript protocols."""
    if not isinstance(value, str):
        return value
    for pattern in XSS_PATTERNS:
        if pattern.search(value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Malicious or illegal script pattern detected in {field_name}."
            )
    return value.strip()

