"""Extractor for Microsoft Word .docx documents using python-docx."""

import io

from docx import Document
from docx.opc.exceptions import PackageNotFoundError
from docx.oxml.ns import qn
from docx.oxml.xmlchemy import BaseOxmlElement

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
    parse_standalone_field_prompt,
    parse_table_row_key_value,
)

_MC_FALLBACK_TAG = "{http://schemas.openxmlformats.org/markup-compatibility/2006}Fallback"
_MC_CHOICE_TAG = "{http://schemas.openxmlformats.org/markup-compatibility/2006}Choice"


class DocxExtractor(DocumentExtractorPort):
    """Extracts paragraphs, tables, headings, and checkboxes from .docx files."""

    def supports(self, extension: str) -> bool:
        return extension.lower() == "docx"

    def extract(self, filename: str, data: bytes) -> ExtractedDocument:
        try:
            doc = Document(io.BytesIO(data))
        except (PackageNotFoundError, Exception) as exc:
            raise DocumentProcessingError(f"Failed to parse DOCX file: {exc}") from exc

        headings: list[str] = []
        paragraphs: list[str] = []
        key_values: list[KeyValuePair] = []
        checkboxes: list[CheckboxItem] = []
        raw_lines: list[str] = []

        for p in doc.paragraphs:
            text = p.text.strip()
            if not text:
                continue

            raw_lines.append(text)
            if p.style and p.style.name.lower().startswith("heading"):
                headings.append(text)
            else:
                paragraphs.append(text)

            cbs, kv = parse_line_elements(text)
            if cbs:
                checkboxes.extend(cbs)
            elif kv:
                key_values.append(kv)

        for text in _textbox_paragraph_texts(doc):
            if not text:
                continue
            raw_lines.append(text)
            paragraphs.append(text)
            cbs, kv = parse_line_elements(text)
            if cbs:
                checkboxes.extend(cbs)
            elif kv and kv not in key_values:
                key_values.append(kv)
            else:
                prompt = parse_standalone_field_prompt(text)
                if prompt and prompt not in key_values:
                    key_values.append(prompt)

        tables: list[TableData] = []
        for table in doc.tables:
            rows_data: list[list[str]] = []
            for row in table.rows:
                # Deduplicate horizontally merged cells by tracking seen XML element (_tc)
                seen_tc = set()
                row_cells: list[str] = []
                for cell in row.cells:
                    if cell._tc in seen_tc:
                        continue
                    seen_tc.add(cell._tc)
                    cell_text = cell.text.strip().replace("\n", " ")
                    row_cells.append(cell_text)

                    # Extract checkboxes and key-values from cell text
                    if cell_text:
                        cbs, kv = parse_line_elements(cell_text)
                        if cbs:
                            checkboxes.extend(cbs)
                        elif kv and kv not in key_values:
                            key_values.append(kv)

                if any(row_cells):
                    rows_data.append(row_cells)
                    # Extract 2-column key-values from table rows
                    row_kv = parse_table_row_key_value(row_cells)
                    if row_kv and row_kv not in key_values:
                        key_values.append(row_kv)

            if rows_data:
                headers = rows_data[0]
                rows = rows_data[1:] if len(rows_data) > 1 else []
                tables.append(TableData(headers=headers, rows=rows))

        page = ExtractedPage(
            page_number=1,
            headings=headings,
            paragraphs=paragraphs,
            key_values=key_values,
            tables=tables,
            checkboxes=checkboxes,
            raw_text="\n".join(raw_lines),
        )

        return ExtractedDocument(
            filename=filename,
            format="docx",
            pages=[page],
            metadata={"paragraphs_count": len(doc.paragraphs), "tables_count": len(tables)},
        )


def _textbox_paragraph_texts(doc: Document) -> list[str]:
    """Read text-box paragraphs while ignoring duplicated markup fallbacks."""
    textboxes = doc.element.iter(qn("w:txbxContent"))
    paragraphs: list[str] = []
    for textbox in textboxes:
        for paragraph in textbox.iter(qn("w:p")):
            if _is_duplicate_fallback_paragraph(paragraph):
                continue
            text = "".join(node.text or "" for node in paragraph.iter(qn("w:t"))).strip()
            if text:
                paragraphs.append(text)
    return paragraphs


def _is_duplicate_fallback_paragraph(paragraph: BaseOxmlElement) -> bool:
    ancestor = paragraph.getparent()
    while ancestor is not None:
        if ancestor.tag == _MC_FALLBACK_TAG:
            alternate_content = ancestor.getparent()
            return alternate_content is not None and any(
                child.tag == _MC_CHOICE_TAG for child in alternate_content
            )
        ancestor = ancestor.getparent()
    return False
