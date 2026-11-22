"""Document extractors package."""

from coi_form_digitization.infrastructure.extractors.composite import CompositeDocumentExtractor
from coi_form_digitization.infrastructure.extractors.docx_extractor import DocxExtractor
from coi_form_digitization.infrastructure.extractors.image_ocr_extractor import ImageOcrExtractor
from coi_form_digitization.infrastructure.extractors.legacy_doc_extractor import LegacyDocExtractor
from coi_form_digitization.infrastructure.extractors.pdf_extractor import PdfExtractor
from coi_form_digitization.infrastructure.extractors.spreadsheet_extractor import (
    SpreadsheetExtractor,
)

__all__ = [
    "CompositeDocumentExtractor",
    "DocxExtractor",
    "ImageOcrExtractor",
    "LegacyDocExtractor",
    "PdfExtractor",
    "SpreadsheetExtractor",
]
