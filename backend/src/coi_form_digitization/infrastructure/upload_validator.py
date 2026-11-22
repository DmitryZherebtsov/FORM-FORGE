"""Infrastructure: in-memory file security validation."""


import filetype

from coi_form_digitization.domain.exceptions import (
    PayloadTooLargeError,
    SecurityValidationError,
    UnsupportedFormatError,
)
from coi_form_digitization.domain.value_objects import (
    ALLOWED_EXTENSIONS,
    FORBIDDEN_FILENAME_CHARS,
    MAX_FILENAME_LENGTH,
    FileMetadata,
)
from coi_form_digitization.infrastructure.config import Settings

# Map allowed extensions to their accepted real MIME types.
# ZIP-based Office formats (docx, xlsx, ods) all share application/zip magic bytes;
# filetype returns "application/zip" for them, which we accept alongside the
# canonical MIME.  OLE2 compound documents (.doc) carry a distinct magic signature.
_EXTENSION_TO_ACCEPTED_MIMES: dict[str, frozenset[str]] = {
    "pdf": frozenset({"application/pdf"}),
    "doc": frozenset({"application/msword", "application/x-ole-storage", "application/x-cfb"}),
    "docx": frozenset(
        {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/zip",
        }
    ),
    "ods": frozenset(
        {
            "application/vnd.oasis.opendocument.spreadsheet",
            "application/zip",
        }
    ),
    "xlsx": frozenset(
        {
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/zip",
        }
    ),
    "jpg": frozenset({"image/jpeg"}),
    "jpeg": frozenset({"image/jpeg"}),
    "jpe": frozenset({"image/jpeg"}),
    "png": frozenset({"image/png"}),
    "tiff": frozenset({"image/tiff"}),
}

# OLE2 magic signature used by legacy .doc files.
_OLE2_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def _detect_mime(data: bytes) -> str:
    """Return the MIME type detected from magic bytes, or empty string if unknown."""
    # Prioritise OLE2 check before filetype to avoid "application/zip" false-positives
    # for .doc files stored in modern container environments.
    if data[:8] == _OLE2_MAGIC:
        return "application/msword"

    kind = filetype.guess(data)
    return kind.mime if kind else ""


class UploadSecurityValidator:
    """Validates uploaded file bytes entirely in RAM without touching disk."""

    def __init__(self, settings: Settings) -> None:
        self._max_size = settings.max_file_size_bytes

    def validate(self, filename: str, data: bytes) -> FileMetadata:
        """Run all security checks and return validated FileMetadata.

        Raises:
            SecurityValidationError: Filename rule violations.
            PayloadTooLargeError: File exceeds MAX_FILE_SIZE_BYTES.
            UnsupportedFormatError: Unsupported extension or MIME mismatch.
        """
        self._check_filename(filename)
        self._check_size(data)
        return self._check_mime(filename, data)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _check_filename(self, filename: str) -> None:
        if len(filename) > MAX_FILENAME_LENGTH:
            raise SecurityValidationError(
                f"Filename exceeds {MAX_FILENAME_LENGTH} characters.",
                detail=f"Filename length {len(filename)} exceeds the maximum of {MAX_FILENAME_LENGTH}.",
            )
        forbidden_found = FORBIDDEN_FILENAME_CHARS.intersection(filename)
        if forbidden_found:
            raise SecurityValidationError(
                "Filename contains forbidden characters.",
                detail=f"Forbidden characters found: {', '.join(sorted(forbidden_found))}",
            )

    def _check_size(self, data: bytes) -> None:
        if len(data) > self._max_size:
            raise PayloadTooLargeError(self._max_size)

    def _check_mime(self, filename: str, data: bytes) -> FileMetadata:
        # Extract and normalise extension (lowercase, no leading dot).
        raw_ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if raw_ext not in ALLOWED_EXTENSIONS:
            raise UnsupportedFormatError(
                f"Extension '.{raw_ext}' is not supported.",
                detail=f"Allowed extensions: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
            )

        detected_mime = _detect_mime(data)
        accepted_mimes = _EXTENSION_TO_ACCEPTED_MIMES[raw_ext]

        if detected_mime not in accepted_mimes:
            raise UnsupportedFormatError(
                "Detected MIME type does not match the declared file extension.",
                detail=(
                    f"Extension '.{raw_ext}' expects one of {sorted(accepted_mimes)}, "
                    f"but detected '{detected_mime}'."
                ),
            )

        # Derive a stable declared MIME from the extension for the metadata record.
        declared_mime = next(iter(accepted_mimes))

        return FileMetadata(
            original_filename=filename,
            extension=raw_ext,
            declared_mime=declared_mime,
            detected_mime=detected_mime,
            size_bytes=len(data),
        )
