"""Extractor for spreadsheet formats (.xlsx and .ods)."""

import io
import re

import odf.teletype
import openpyxl
from odf.opendocument import load
from odf.table import Table, TableCell, TableRow
from openpyxl.cell.cell import MergedCell

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

_SECTION_PREFIX_PATTERN = re.compile(
    r"^(?:[A-ZĄĆĘŁŃÓŚŹŻ]\.\s+[A-ZĄĆĘŁŃÓŚŹŻ]|\d+\.\s+[A-ZĄĆĘŁŃÓŚŹŻ]|[IVXLCDM]+\.\s+[A-ZĄĆĘŁŃÓŚŹŻ])"
)
_ROMAN_SECTION_PATTERN = re.compile(r"^[IVXLCDM]+\.$")
_NUMBERED_CHOICE_PATTERN = re.compile(r"^\d+[.)]\s+(.+)$")
_PARENTHETICAL_PROMPT_PATTERN = re.compile(r"^\([^()]{2,120}\)\s*\d?\)?$")
_CHECKBOX_MARKERS = {"☐", "□", "☑", "☒", "■", "[ ]", "[x]", "[X]"}
_CHECKED_MARKERS = {"☑", "☒", "■", "[x]", "[X]"}
_FIELD_LABEL_TERMS = (
    "imię",
    "nazwisk",
    "nazwa",
    "wnioskodawc",
    "pełnomocnik",
    "reprezentant",
    "kandydat",
    "podopieczn",
    "adres",
    "ulic",
    "miejscowo",
    "kod pocztow",
    "numer",
    "nr ",
    "pesel",
    "nip",
    "regon",
    "telefon",
    "tel.",
    "e-mail",
    "email",
    "epuap",
    "edoręczeni",
    "data",
    "podpis",
    "dyscyplin",
    "działk",
    "dzialk",
    "lokal",
    "seria",
    "rachunk",
    "konto",
    "cel ",
    "przedmiot",
)


class SpreadsheetExtractor(DocumentExtractorPort):
    """Extracts tables, key-values, and text from .xlsx and .ods spreadsheets."""

    def supports(self, extension: str) -> bool:
        return extension.lower() in ("xlsx", "ods")

    def extract(self, filename: str, data: bytes) -> ExtractedDocument:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "xlsx"
        if ext == "xlsx":
            return self._extract_xlsx(filename, data)
        return self._extract_ods(filename, data)

    def _extract_xlsx(self, filename: str, data: bytes) -> ExtractedDocument:
        try:
            wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True, read_only=False)
        except Exception as exc:
            raise DocumentProcessingError(f"Corrupted or unreadable XLSX file: {exc}") from exc

        pages: list[ExtractedPage] = []
        try:
            for idx, sheet_name in enumerate(wb.sheetnames, start=1):
                sheet = wb[sheet_name]
                if _is_coordinate_canvas(sheet):
                    pages.append(_extract_coordinate_sheet(sheet, idx))
                    continue

                rows: list[list[str]] = []
                headings: list[str] = [sheet_name]
                paragraphs: list[str] = []
                key_values: list[KeyValuePair] = []
                checkboxes: list[CheckboxItem] = []
                raw_lines: list[str] = []

                for row in sheet.iter_rows(values_only=True):
                    row_vals = [str(cell).strip() if cell is not None else "" for cell in row]
                    if not any(row_vals):
                        continue

                    rows.append(row_vals)
                    line_text = " | ".join(v for v in row_vals if v)
                    raw_lines.append(line_text)

                    row_kv = parse_table_row_key_value(row_vals)
                    if row_kv:
                        key_values.append(row_kv)
                    for val in row_vals:
                        if not val:
                            continue
                        cbs, kv = parse_line_elements(val)
                        if cbs:
                            checkboxes.extend(cbs)
                        elif kv and kv not in key_values:
                            key_values.append(kv)

                tables: list[TableData] = []
                if rows:
                    tables.append(TableData(headers=rows[0], rows=rows[1:] if len(rows) > 1 else [], title=sheet_name))

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
        finally:
            wb.close()

        return ExtractedDocument(
            filename=filename,
            format="xlsx",
            pages=pages,
            metadata={"sheets_count": len(pages)},
        )

    def _extract_ods(self, filename: str, data: bytes) -> ExtractedDocument:
        try:
            doc = load(io.BytesIO(data))
        except Exception as exc:
            raise DocumentProcessingError(f"Corrupted or unreadable ODS file: {exc}") from exc

        pages: list[ExtractedPage] = []
        tables_elements = doc.getElementsByType(Table)
        for idx, table_elem in enumerate(tables_elements, start=1):
            sheet_name = table_elem.getAttribute("name") or f"Sheet_{idx}"
            headings: list[str] = [sheet_name]
            paragraphs: list[str] = []
            key_values: list[KeyValuePair] = []
            checkboxes: list[CheckboxItem] = []
            raw_lines: list[str] = []
            rows_data: list[list[str]] = []

            for row_elem in table_elem.getElementsByType(TableRow):
                row_vals: list[str] = []
                for cell in row_elem.getElementsByType(TableCell):
                    cell_text = odf.teletype.extractText(cell).strip()
                    repeated_attr = (
                        cell.getAttrNS("urn:oasis:names:tc:opendocument:xmlns:table:1.0", "number-columns-repeated")
                        or cell.getAttribute("numbercolumnsrepeated")
                    )
                    repeat_count = 1
                    if repeated_attr:
                        try:
                            # Blank repeated cells can otherwise expand into enormous rows.
                            repeat_count = min(int(repeated_attr), 1000) if not cell_text else int(repeated_attr)
                        except (ValueError, TypeError):
                            repeat_count = 1

                    for _ in range(repeat_count):
                        row_vals.append(cell_text)

                if not any(row_vals):
                    continue

                rows_data.append(row_vals)
                line_text = " | ".join(v for v in row_vals if v)
                raw_lines.append(line_text)

                row_kv = parse_table_row_key_value(row_vals)
                if row_kv:
                    key_values.append(row_kv)
                for val in row_vals:
                    if not val:
                        continue
                    cbs, kv = parse_line_elements(val)
                    if cbs:
                        checkboxes.extend(cbs)
                    elif kv and kv not in key_values:
                        key_values.append(kv)

            tables: list[TableData] = []
            if rows_data:
                tables.append(TableData(headers=rows_data[0], rows=rows_data[1:] if len(rows_data) > 1 else [], title=sheet_name))

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

        return ExtractedDocument(
            filename=filename,
            format="ods",
            pages=pages,
            metadata={"sheets_count": len(pages)},
        )


def _is_coordinate_canvas(sheet: openpyxl.worksheet.worksheet.Worksheet) -> bool:
    return len(sheet.merged_cells.ranges) >= 10 or (
        sheet.max_row >= 40 and sheet.max_column >= 20
    )


def _extract_coordinate_sheet(
    sheet: openpyxl.worksheet.worksheet.Worksheet, page_number: int
) -> ExtractedPage:
    headings = [sheet.title]
    paragraphs: list[str] = []
    key_values: list[KeyValuePair] = []
    checkboxes: list[CheckboxItem] = []
    raw_lines: list[str] = []
    merged_end_columns = {
        (merged.min_row, merged.min_col): merged.max_col
        for merged in sheet.merged_cells.ranges
    }

    for row_number in range(1, sheet.max_row + 1):
        populated = [
            cell
            for cell in sheet[row_number]
            if not isinstance(cell, MergedCell) and cell.value is not None and str(cell.value).strip()
        ]
        if not populated:
            continue

        raw_lines.append(" | ".join(f"{cell.coordinate}: {str(cell.value).strip()}" for cell in populated))
        consumed_labels: set[int] = set()
        for index, cell in enumerate(populated):
            if index in consumed_labels:
                continue
            text = str(cell.value).strip()
            if text in _CHECKBOX_MARKERS and index + 1 < len(populated):
                option_label = str(populated[index + 1].value).strip()
                if option_label:
                    checkboxes.append(
                        CheckboxItem(label=option_label, is_checked=text in _CHECKED_MARKERS)
                    )
                    consumed_labels.add(index + 1)
                    continue

            cbs, kv = parse_line_elements(text)
            if cbs:
                checkboxes.extend(cbs)
                continue
            if kv:
                if kv not in key_values:
                    key_values.append(kv)
                continue
            numbered_choice = _NUMBERED_CHOICE_PATTERN.match(text)
            if numbered_choice and numbered_choice.group(1)[:1].islower():
                checkboxes.append(CheckboxItem(label=text, is_checked=False))
                if not _is_field_prompt(text):
                    continue
            if _is_section_heading(text):
                headings.append(text)
                continue

            merge_end = merged_end_columns.get((row_number, cell.column), cell.column)
            has_blank_entry = _has_blank_entry_to_right(sheet, row_number, merge_end)
            is_parenthetical_prompt = _PARENTHETICAL_PROMPT_PATTERN.fullmatch(text) is not None
            if is_parenthetical_prompt or (has_blank_entry and _is_field_prompt(text)):
                label = text.removesuffix(":").strip()
                if label:
                    pair = KeyValuePair(key=label, value="")
                    if pair not in key_values:
                        key_values.append(pair)
                continue

            paragraphs.append(text)

    return ExtractedPage(
        page_number=page_number,
        headings=headings,
        paragraphs=paragraphs,
        key_values=key_values,
        tables=[],
        checkboxes=checkboxes,
        raw_text="\n".join(raw_lines),
    )


def _is_section_heading(text: str) -> bool:
    if _SECTION_PREFIX_PATTERN.match(text) or _ROMAN_SECTION_PATTERN.fullmatch(text):
        return True
    return len(text) >= 20 and any(char.isalpha() for char in text) and text == text.upper()


def _is_field_prompt(text: str) -> bool:
    label = re.sub(r"^\d+[.)]\s*", "", text.casefold()).removesuffix(":").strip()
    if len(label) >= 60 or label.endswith((".", "!", "?")):
        return False
    return any(term in label for term in _FIELD_LABEL_TERMS)


def _has_blank_entry_to_right(
    sheet: openpyxl.worksheet.worksheet.Worksheet, row_number: int, merge_end_column: int
) -> bool:
    last_column = min(sheet.max_column, merge_end_column + 4)
    for column in range(merge_end_column + 1, last_column + 1):
        cell = sheet.cell(row_number, column)
        if cell.value is not None:
            return False
        if _cell_has_border(cell):
            return True
    return False


def _cell_has_border(cell: openpyxl.cell.cell.Cell | MergedCell) -> bool:
    return any(
        getattr(cell.border, side).style is not None
        for side in ("left", "right", "top", "bottom")
    )
