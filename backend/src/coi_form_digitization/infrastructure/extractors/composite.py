"""Composite registry delegating to the appropriate extractor by file extension."""

from coi_form_digitization.domain.exceptions import UnsupportedFormatError
from coi_form_digitization.domain.extracted_document import ExtractedDocument
from coi_form_digitization.domain.ports import DocumentExtractorPort
from coi_form_digitization.infrastructure.extractors.docx_extractor import DocxExtractor
from coi_form_digitization.infrastructure.extractors.image_ocr_extractor import ImageOcrExtractor
from coi_form_digitization.infrastructure.extractors.legacy_doc_extractor import LegacyDocExtractor
from coi_form_digitization.infrastructure.extractors.pdf_extractor import PdfExtractor
from coi_form_digitization.infrastructure.extractors.spreadsheet_extractor import (
    SpreadsheetExtractor,
)


class CompositeDocumentExtractor(DocumentExtractorPort):
    """Orchestrates format-specific extractors."""

    def __init__(self, extractors: list[DocumentExtractorPort] | None = None) -> None:
        if extractors is not None:
            self._extractors = extractors
        else:
            ocr = ImageOcrExtractor()
            docx = DocxExtractor()
            self._extractors = [
                PdfExtractor(ocr_extractor=ocr),
                docx,
                LegacyDocExtractor(docx_extractor=docx),
                SpreadsheetExtractor(),
                ocr,
            ]

    def supports(self, extension: str) -> bool:
        ext = extension.lower().lstrip(".")
        return any(e.supports(ext) for e in self._extractors)

    def extract(self, filename: str, data: bytes) -> ExtractedDocument:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        for extractor in self._extractors:
            if extractor.supports(ext):
                return extractor.extract(filename, data)

        raise UnsupportedFormatError(f"No extractor registered for extension '.{ext}'.")
