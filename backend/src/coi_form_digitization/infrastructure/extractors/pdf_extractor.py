"""Extractor for PDF documents using pypdf and pdfplumber, with OCR fallback."""

import io
import logging

import pdfplumber
from pypdf import PdfReader
from pypdf.errors import EmptyFileError, FileNotDecryptedError, PdfReadError

from coi_form_digitization.domain.exceptions import DocumentProcessingError
from coi_form_digitization.domain.extracted_document import (
    CheckboxItem,
    ExtractedDocument,
    ExtractedPage,
    KeyValuePair,
    TableData,
)
from coi_form_digitization.domain.ports import DocumentExtractorPort
from coi_form_digitization.infrastructure.extractors.base import (
    parse_line_elements,
    parse_table_row_key_value,
)
from coi_form_digitization.infrastructure.extractors.image_ocr_extractor import ImageOcrExtractor

logger = logging.getLogger(__name__)


class PdfExtractor(DocumentExtractorPort):
    """Extracts text, tables, and form elements from PDF files with OCR fallback."""

    def __init__(self, ocr_extractor: ImageOcrExtractor | None = None) -> None:
        self._ocr = ocr_extractor or ImageOcrExtractor()

    def supports(self, extension: str) -> bool:
        return extension.lower() == "pdf"

    def extract(self, filename: str, data: bytes) -> ExtractedDocument:
        # Pre-check integrity and encryption using pypdf
        try:
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted:
                raise DocumentProcessingError("Password-protected or encrypted PDF is not supported.")
            if len(reader.pages) == 0:
                raise DocumentProcessingError("PDF document contains no pages.")
        except (PdfReadError, EmptyFileError, FileNotDecryptedError) as exc:
            raise DocumentProcessingError(f"Corrupted or invalid PDF file: {exc}") from exc
        except DocumentProcessingError:
            raise
        except Exception as exc:
            raise DocumentProcessingError(f"Cannot read PDF structure: {exc}") from exc

        pages: list[ExtractedPage] = []
        try:
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                for idx, page in enumerate(pdf.pages, start=1):
                    extracted_text = page.extract_text() or ""
                    tables: list[TableData] = []
                    table_key_values: list[KeyValuePair] = []
                    raw_tables = page.extract_tables() or []
                    for t in raw_tables:
                        cleaned_rows = [
                            [c.strip().replace("\n", " ") if c else "" for c in row]
                            for row in t
                            if any(row)
                        ]
                        if cleaned_rows:
                            tables.append(TableData(headers=cleaned_rows[0], rows=cleaned_rows[1:]))
                            for row in cleaned_rows:
                                row_kv = parse_table_row_key_value(row)
                                if row_kv and row_kv not in table_key_values:
                                    table_key_values.append(row_kv)

                    headings: list[str] = []
                    paragraphs: list[str] = []
                    key_values: list[KeyValuePair] = table_key_values
                    checkboxes: list[CheckboxItem] = []
                    raw_lines = [line.strip() for line in extracted_text.splitlines() if line.strip()]

                    # Fallback to OCR if page has negligible text (scanned PDF)
                    if len("".join(raw_lines)) < 20:
                        try:
                            # Render page to in-memory PNG for OCR at 200 DPI
                            img = page.to_image(resolution=200).original
                            img_byte_arr = io.BytesIO()
                            img.save(img_byte_arr, format="PNG")
                            ocr_doc = self._ocr.extract(f"{filename}_page_{idx}.png", img_byte_arr.getvalue())
                            if ocr_doc.pages:
                                ocr_page = ocr_doc.pages[0]
                                headings.extend(ocr_page.headings)
                                paragraphs.extend(ocr_page.paragraphs)
                                key_values.extend(ocr_page.key_values)
                                checkboxes.extend(ocr_page.checkboxes)
                                raw_lines = ocr_page.raw_text.splitlines()
                        except DocumentProcessingError:
                            raise
                        except Exception as exc:
                            logger.error("PDF page %d OCR fallback rendering failed: %s", idx, exc)
                            raise DocumentProcessingError(
                                f"Failed during OCR fallback rendering for PDF page {idx}: {exc}"
                            ) from exc
                    else:
                        for line in raw_lines:
                            cbs, kv = parse_line_elements(line)
                            if cbs:
                                checkboxes.extend(cbs)
                            elif kv:
                                key_values.append(kv)
                            else:
                                if len(line) < 60 and (line.isupper() or line.endswith(":") or line[0].isdigit()):
                                    headings.append(line)
                                else:
                                    paragraphs.append(line)

                    pages.append(
                        ExtractedPage(
                            page_number=idx,
                            headings=headings,
                            paragraphs=paragraphs,
                            key_values=key_values,
                            tables=tables,
                            checkboxes=checkboxes,
                            raw_text="\n".join(raw_lines),
                        )
                    )
        except DocumentProcessingError:
            raise
        except Exception as exc:
            raise DocumentProcessingError(f"Failed parsing PDF stream: {exc}") from exc

        return ExtractedDocument(
            filename=filename,
            format="pdf",
            pages=pages,
            metadata={"pages_count": len(pages)},
        )
