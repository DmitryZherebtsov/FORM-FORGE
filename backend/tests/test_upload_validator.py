"""Security unit tests: UploadSecurityValidator — critical paths only."""

import pytest

from coi_form_digitization.domain.exceptions import (
    PayloadTooLargeError,
    SecurityValidationError,
    UnsupportedFormatError,
)
from coi_form_digitization.infrastructure.upload_validator import UploadSecurityValidator
from tests.conftest import (
    JPEG_MAGIC,
    OLE2_MAGIC,
    PDF_MAGIC,
    PNG_MAGIC,
    ZIP_MAGIC,
    _build_test_settings,
)


@pytest.fixture()
def validator() -> UploadSecurityValidator:
    return UploadSecurityValidator(_build_test_settings())


class TestFilenameRules:
    def test_filename_exceeds_250_chars_raises(self, validator: UploadSecurityValidator) -> None:
        # 251 chars must be rejected — security boundary.
        with pytest.raises(SecurityValidationError, match="250"):
            validator.validate("a" * 247 + ".pdf", PDF_MAGIC)

    @pytest.mark.parametrize("char", [";", "/"])
    def test_forbidden_char_raises(self, validator: UploadSecurityValidator, char: str) -> None:
        # Representative sample: all forbidden chars share the same code path.
        with pytest.raises(SecurityValidationError, match="forbidden"):
            validator.validate(f"bad{char}name.pdf", PDF_MAGIC)


class TestMimeSpoofing:
    def test_unsupported_extension_raises(self, validator: UploadSecurityValidator) -> None:
        with pytest.raises(UnsupportedFormatError, match="not supported"):
            validator.validate("malware.exe", PDF_MAGIC)

    def test_spoofed_exe_in_pdf_raises(self, validator: UploadSecurityValidator) -> None:
        # EXE magic bytes must be rejected regardless of extension claim.
        with pytest.raises(UnsupportedFormatError, match="MIME"):
            validator.validate("evil.pdf", b"MZ" + b"\x00" * 100)

    def test_cross_format_spoof_raises(self, validator: UploadSecurityValidator) -> None:
        # PNG bytes in a .pdf file — the most common client-side spoof vector.
        with pytest.raises(UnsupportedFormatError, match="MIME"):
            validator.validate("spoofed.pdf", PNG_MAGIC)

    def test_ole2_doc_accepted(self, validator: UploadSecurityValidator) -> None:
        # OLE2 magic must be accepted for legacy .doc — priority detection logic.
        meta = validator.validate("legacy.doc", OLE2_MAGIC)
        assert meta.detected_mime == "application/msword"

    def test_zip_magic_accepted_for_docx(self, validator: UploadSecurityValidator) -> None:
        # ZIP container magic is the real on-disk signature for docx/xlsx/ods.
        meta = validator.validate("form.docx", ZIP_MAGIC)
        assert meta.extension == "docx"

    def test_jpe_extension_accepts_jpeg_magic(self, validator: UploadSecurityValidator) -> None:
        meta = validator.validate("scan.jpe", JPEG_MAGIC)
        assert meta.extension == "jpe"
        assert meta.detected_mime == "image/jpeg"


class TestSizeLimit:
    def test_oversized_file_raises(self) -> None:
        validator = UploadSecurityValidator(_build_test_settings(max_file_size_bytes=50))
        with pytest.raises(PayloadTooLargeError):
            validator.validate("form.pdf", b"\x00" * 51)
