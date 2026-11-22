"""Domain exceptions — pure Python, no framework imports."""


class DomainError(Exception):
    """Base class for all domain errors."""


class SecurityValidationError(DomainError):
    """Raised when a security constraint on the uploaded file is violated."""

    def __init__(self, message: str, detail: str | None = None) -> None:
        super().__init__(message)
        self.detail = detail or message


class UnsupportedFormatError(DomainError):
    """Raised when the file extension or detected MIME type is not supported."""

    def __init__(self, message: str, detail: str | None = None) -> None:
        super().__init__(message)
        self.detail = detail or message


class PayloadTooLargeError(DomainError):
    """Raised when the uploaded file exceeds the configured size limit."""

    def __init__(self, limit_bytes: int) -> None:
        super().__init__(f"File exceeds maximum allowed size of {limit_bytes} bytes.")
        self.limit_bytes = limit_bytes


class AuthenticationError(DomainError):
    """Raised when JWT authentication fails."""


class DocumentProcessingError(DomainError):
    """Raised when a document cannot be parsed or is corrupt."""
