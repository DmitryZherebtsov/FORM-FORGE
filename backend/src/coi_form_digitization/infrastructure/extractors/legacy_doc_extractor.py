"""Extractor for legacy Microsoft Word .doc documents using headless LibreOffice."""

import shutil
import subprocess
import tempfile
from pathlib import Path

from coi_form_digitization.domain.exceptions import DocumentProcessingError
from coi_form_digitization.domain.extracted_document import ExtractedDocument
from coi_form_digitization.domain.ports import DocumentExtractorPort
from coi_form_digitization.infrastructure.extractors.docx_extractor import DocxExtractor


class LegacyDocExtractor(DocumentExtractorPort):
    """Converts .doc to .docx using headless LibreOffice in an isolated ephemeral directory,

    then delegates extraction to DocxExtractor.
    """

    def __init__(self, docx_extractor: DocxExtractor | None = None) -> None:
        self._docx_extractor = docx_extractor or DocxExtractor()
        self._soffice_cmd = self._find_soffice()

    def _find_soffice(self) -> str | None:
        for cmd in ("soffice", "libreoffice"):
            if shutil.which(cmd):
                return cmd
        # Common macOS app paths
        mac_paths = [
            "/Applications/LibreOffice.app/Contents/MacOS/soffice",
            "/Applications/OpenOffice.app/Contents/MacOS/soffice",
        ]
        for p in mac_paths:
            if Path(p).exists():
                return p
        return None

    def supports(self, extension: str) -> bool:
        return extension.lower() == "doc"

    def extract(self, filename: str, data: bytes) -> ExtractedDocument:
        if not self._soffice_cmd:
            raise DocumentProcessingError(
                "Legacy .doc extraction requires LibreOffice/soffice, which is not installed in the environment."
            )

        # Ephemeral temp directory guaranteed to be wiped on exit
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            in_file = tmp_path / "input.doc"
            try:
                in_file.write_bytes(data)
            except Exception as exc:
                raise DocumentProcessingError(f"Failed to prepare ephemeral doc buffer: {exc}") from exc

            profile_uri = (tmp_path / "profile").as_uri()
            cmd = [
                self._soffice_cmd,
                f"-env:UserInstallation={profile_uri}",
                "--headless",
                "--invisible",
                "--nodefault",
                "--nofirststartwizard",
                "--convert-to",
                "docx",
                "--outdir",
                str(tmp_path),
                str(in_file),
            ]

            try:
                res = subprocess.run(cmd, capture_output=True, timeout=30)
                if res.returncode != 0:
                    raise DocumentProcessingError(f"LibreOffice conversion failed: {res.stderr.decode('utf-8', errors='ignore')}")
            except DocumentProcessingError:
                raise
            except subprocess.TimeoutExpired as exc:
                raise DocumentProcessingError("LibreOffice conversion timed out.") from exc
            except Exception as exc:
                raise DocumentProcessingError(f"LibreOffice execution error: {exc}") from exc

            converted_file = tmp_path / "input.docx"
            if not converted_file.exists():
                raise DocumentProcessingError("LibreOffice conversion produced no output file.")

            converted_bytes = converted_file.read_bytes()
            try:
                extracted = self._docx_extractor.extract(filename, converted_bytes)
            except DocumentProcessingError:
                raise
            except Exception as exc:
                raise DocumentProcessingError(f"Failed extracting converted DOCX from DOC: {exc}") from exc

            # Normalize format to doc
            return ExtractedDocument(
                filename=filename,
                format="doc",
                pages=extracted.pages,
                metadata={**extracted.metadata, "conversion": "libreoffice-headless"},
            )
