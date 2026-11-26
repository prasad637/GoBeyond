import json
import logging
import re
import sys
from typing import Any, Dict, Optional

# Regular expressions to detect and mask sensitive credentials, tokens, OTPs
SENSITIVE_PATTERNS = [
    (re.compile(r'(password["\':\s=]+)([\w!@#$%^&*()-+=]{1,64})', re.IGNORECASE), r'\1******'),
    (re.compile(r'(token["\':\s=]+)([\w\.-]{10,})', re.IGNORECASE), r'\1******'),
    (re.compile(r'(secret["\':\s=]+)([\w\.-]{10,})', re.IGNORECASE), r'\1******'),
    (re.compile(r'(key["\':\s=]+)([\w\.-]{16,})', re.IGNORECASE), r'\1******'),
    (re.compile(r'(otp["\':\s=]+)(\d{4,8})', re.IGNORECASE), r'\1******'),
    (re.compile(r'(code["\':\s=]+)(\d{6})', re.IGNORECASE), r'\1******'),
    (re.compile(r'\b(\d{6})\b'), r'******'),  # Standalone 6-digit OTPs
]


def mask_sensitive_data(text: str) -> str:
    """Masks credentials, passwords, OTPs, and auth secrets from log strings."""
    if not isinstance(text, str):
        text = str(text)
    for pattern, replacement in SENSITIVE_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class StructuredJsonFormatter(logging.Formatter):
    """
    Formats log records as production-ready structured JSON.
    Automatically scrubs sensitive data and includes correlation IDs.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": mask_sensitive_data(record.getMessage()),
            "module": record.module,
            "line": record.lineno,
        }

        # Include request context if present
        if hasattr(record, "correlation_id") and record.correlation_id:
            log_entry["correlation_id"] = record.correlation_id
        if hasattr(record, "method") and record.method:
            log_entry["method"] = record.method
        if hasattr(record, "path") and record.path:
            log_entry["path"] = record.path
        if hasattr(record, "status_code") and record.status_code is not None:
            log_entry["status_code"] = record.status_code
        if hasattr(record, "duration_ms") and record.duration_ms is not None:
            log_entry["duration_ms"] = record.duration_ms

        if record.exc_info:
            # Mask exception traceback if needed
            exc_text = self.formatException(record.exc_info)
            log_entry["exception"] = mask_sensitive_data(exc_text)

        return json.dumps(log_entry)


def setup_structured_logging(log_level: str = "INFO", json_format: bool = False) -> logging.Logger:
    """Configures structured application logging."""
    logger = logging.getLogger("gobeyond")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Remove existing handlers to avoid duplicates
    for handler in list(logger.handlers):
        logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    if json_format:
        handler.setFormatter(StructuredJsonFormatter())
    else:
        # Standard human-readable format with masking filter
        class MaskingFormatter(logging.Formatter):
            def format(self, rec):
                rec.msg = mask_sensitive_data(str(rec.msg))
                return super().format(rec)

        handler.setFormatter(MaskingFormatter("%(asctime)s [%(levelname)s] [%(name)s] %(message)s"))

    logger.addHandler(handler)
    logger.propagate = False
    return logger

