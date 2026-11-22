"""Domain value objects — pure Python, immutable, no framework or I/O imports."""

from dataclasses import dataclass

ALLOWED_EXTENSIONS: frozenset[str] = frozenset(
    {"pdf", "doc", "docx", "ods", "xlsx", "jpg", "jpeg", "jpe", "png", "tiff"}
)

# Forbidden characters per COI security specification.
FORBIDDEN_FILENAME_CHARS: frozenset[str] = frozenset([";", ":", ">", "<", "/", "\\", "|", "'", "*", "%", "$"])

MAX_FILENAME_LENGTH: int = 250


@dataclass(frozen=True)
class FileMetadata:
    """Validated, immutable representation of an uploaded file's identity."""

    original_filename: str
    extension: str
    declared_mime: str
    detected_mime: str
    size_bytes: int
