"""Focused regression coverage for COI form extraction edge cases."""

import io

import openpyxl
from docx import Document
from docx.oxml import parse_xml
from openpyxl.styles import Border, Side

from coi_form_digitization.domain.extracted_document import CheckboxItem, KeyValuePair
from coi_form_digitization.infrastructure.extractors.base import parse_line_elements
from coi_form_digitization.infrastructure.extractors.docx_extractor import DocxExtractor
from coi_form_digitization.infrastructure.extractors.image_ocr_extractor import ImageOcrExtractor
from coi_form_digitization.infrastructure.extractors.pdf_extractor import PdfExtractor
from coi_form_digitization.infrastructure.extractors.spreadsheet_extractor import (
    SpreadsheetExtractor,
)
from tests.fixtures_generator import make_test_image_bytes, make_test_pdf_bytes


def test_jpe_is_supported_and_ocr_extracts_text(monkeypatch) -> None:
    extractor = ImageOcrExtractor()
    monkeypatch.setattr(
        extractor,
        "_get_engine",
        lambda: lambda _image: (
            [([[0, 0], [1, 0], [1, 1], [0, 1]], "PESEL: _______", 0.98)],
            0,
        ),
    )

    assert extractor.supports("jpe")
    result = extractor.extract("scan.jpe", make_test_image_bytes("JPEG"))

    assert result.format == "jpe"
    assert result.pages[0].key_values == [KeyValuePair(key="PESEL", value="")]


def test_docx_textboxes_skip_duplicate_alternate_content_fallback() -> None:
    doc = Document()
    doc._element.body.append(
        parse_xml(
            '<mc:AlternateContent '
            'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
            'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<mc:Choice Requires="wps"><w:txbxContent><w:p><w:r><w:t>Choice text</w:t>'
            '</w:r></w:p></w:txbxContent></mc:Choice>'
            '<mc:Fallback><w:txbxContent><w:p><w:r><w:t>Fallback duplicate</w:t>'
            '</w:r></w:p></w:txbxContent></mc:Fallback>'
            '</mc:AlternateContent>'
        )
    )
    document_bytes = _docx_bytes(doc)

    result = DocxExtractor().extract("textbox.docx", document_bytes)

    assert result.pages[0].paragraphs.count("Choice text") == 1
    assert "Fallback duplicate" not in result.pages[0].raw_text


def test_docx_two_column_blank_entry_becomes_empty_key_value() -> None:
    doc = Document()
    table = doc.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Imię i nazwisko"
    table.cell(0, 1).text = ""

    result = DocxExtractor().extract("blank-field.docx", _docx_bytes(doc))

    assert KeyValuePair(key="Imię i nazwisko", value="") in result.pages[0].key_values


def test_docx_textbox_standalone_field_prompts_become_empty_key_values() -> None:
    doc = Document()
    textbox_paragraphs = [
        "PESEL",
        "NIP",
        "Nazwa /Imię i nazwisko",
        "(adres)",
        "Dane właściciela",
        "4. Uzasadnienie wniosku (opisz w polu poniżej dlaczego opłata jest błędna",
        "2. Dane wnioskodawcy",
        "WYPEŁNIJ WIELKIMI LITERAMI.",
        "Gotówką w kasie organu",
        "Dokument stwierdzający udzielenie pełnomocnictwa",
    ]
    textbox_xml = (
        '<w:txbxContent xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        + "".join(
            f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>" for text in textbox_paragraphs
        )
        + "</w:txbxContent>"
    )
    doc._element.body.append(parse_xml(textbox_xml))

    result = DocxExtractor().extract("textbox-fields.docx", _docx_bytes(doc))
    values = {item.key: item.value for item in result.pages[0].key_values}

    assert values["PESEL"] == ""
    assert values["NIP"] == ""
    assert values["Nazwa /Imię i nazwisko"] == ""
    assert values["adres"] == ""
    assert values["Dane właściciela"] == ""
    assert values["Uzasadnienie wniosku"] == ""
    assert "2. Dane wnioskodawcy" not in values
    assert "WYPEŁNIJ WIELKIMI LITERAMI." not in values
    assert "Gotówką w kasie organu" not in values
    assert "Dokument stwierdzający udzielenie pełnomocnictwa" not in values


def test_coordinate_xlsx_extracts_merged_prompts_and_preserves_sheets() -> None:
    workbook = openpyxl.Workbook()
    form = workbook.active
    assert form is not None
    form.title = "Formularz"
    form.merge_cells("A1:F1")
    form["A1"] = "A. ORGAN, DO KTÓREGO SKŁADANY JEST WNIOSEK"
    form.merge_cells("A2:B2")
    form["A2"] = "(imię i nazwisko)"
    form.merge_cells("C2:F2")
    form.merge_cells("A3:B3")
    form["A3"] = "PESEL:"
    form.merge_cells("C3:F3")
    form.merge_cells("A4:B4")
    form["A4"] = "Prezydent Miasta Gdyni"
    form.merge_cells("C4:F4")
    form["A5"] = "1. właściciel"
    entry_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )
    form["C2"].border = entry_border
    form["C3"].border = entry_border
    form["C4"].border = entry_border
    for row in range(10, 15):
        form.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
    second = workbook.create_sheet("II. Wniosek")
    second["A1"] = "Załączniki"

    buffer = io.BytesIO()
    workbook.save(buffer)
    result = SpreadsheetExtractor().extract("form.xlsx", buffer.getvalue())

    assert len(result.pages) == 2
    assert "A. ORGAN, DO KTÓREGO SKŁADANY JEST WNIOSEK" in result.pages[0].headings
    assert KeyValuePair(key="(imię i nazwisko)", value="") in result.pages[0].key_values
    assert KeyValuePair(key="PESEL", value="") in result.pages[0].key_values
    assert KeyValuePair(key="Prezydent Miasta Gdyni", value="") not in result.pages[0].key_values
    assert CheckboxItem(label="1. właściciel", is_checked=False) in result.pages[0].checkboxes
    assert "C2:" not in result.pages[0].raw_text
    assert result.pages[1].headings == ["II. Wniosek"]


def test_pdf_table_row_with_blank_right_cell_is_extracted(monkeypatch) -> None:
    class FakePage:
        def extract_text(self) -> str:
            return "Selectable text is long enough to avoid the OCR fallback."

        def extract_tables(self) -> list[list[list[str]]]:
            return [[ ["Pole", "Wartość"], ["PESEL", ""] ]]

    class FakePdf:
        pages = [FakePage()]

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

    monkeypatch.setattr("coi_form_digitization.infrastructure.extractors.pdf_extractor.pdfplumber.open", lambda _data: FakePdf())

    result = PdfExtractor().extract("table.pdf", make_test_pdf_bytes())

    assert KeyValuePair(key="PESEL", value="") in result.pages[0].key_values


def test_dotted_and_underscored_blank_lines_become_empty_key_values() -> None:
    dotted = parse_line_elements("Imię i nazwisko: ............")[1]
    underscored = parse_line_elements("PESEL: ___________")[1]

    assert dotted == KeyValuePair(key="Imię i nazwisko", value="")
    assert underscored == KeyValuePair(key="PESEL", value="")


def _docx_bytes(doc: Document) -> bytes:
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()
