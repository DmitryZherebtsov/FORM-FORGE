"""Fixtures generating valid in-memory documents for integration tests."""

import io

import openpyxl
from docx import Document
from odf.opendocument import OpenDocumentSpreadsheet
from odf.table import Table, TableCell, TableRow
from odf.text import P
from PIL import Image, ImageDraw
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject, NumberObject


def make_test_pdf_bytes(
    lines: list[str] | None = None,
) -> bytes:
    """Create a PDF with actual text content stream."""
    if lines is None:
        lines = [
            "1. DANE WNIOSKODAWCY:",
            "PESEL: 90010112345",
            "Nazwisko: Kowalski",
            "[x] Tak   [ ] Nie",
        ]

    content_cmds = ["BT /F1 12 Tf"]
    y = 750
    for line in lines:
        safe_line = line.replace("(", "\\(").replace(")", "\\)")
        content_cmds.append(f"50 {y} Td ({safe_line}) Tj")
        y -= 30
    content_cmds.append("ET")
    content = "\n".join(content_cmds).encode("latin-1")

    stream = DecodedStreamObject()
    stream.set_data(content)
    stream[NameObject("/Length")] = NumberObject(len(content))

    font_dict = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    resources = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {
                    NameObject("/F1"): font_dict,
                }
            )
        }
    )

    writer = PdfWriter()
    page = writer.add_blank_page(width=595, height=842)
    page[NameObject("/Contents")] = writer._add_object(stream)
    page[NameObject("/Resources")] = writer._add_object(resources)

    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def make_test_docx_bytes(title: str = "Wniosek", items: list[str] | None = None) -> bytes:
    doc = Document()
    doc.add_heading(title, level=1)
    doc.add_paragraph("Numer PESEL: 90010112345")
    doc.add_paragraph("[x] Obywatel polski   [ ] Cudzoziemiec")
    table = doc.add_table(rows=3, cols=2)
    table.rows[0].cells[0].text = "Pole"
    table.rows[0].cells[1].text = "Wartość"
    table.rows[1].cells[0].text = "Nazwisko"
    table.rows[1].cells[1].text = "Kowalski"
    table.rows[2].cells[0].text = "[x] Tak"
    table.rows[2].cells[1].text = "[ ] Nie"
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def make_test_xlsx_bytes() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "DaneWniosku"
    ws.append(["Pole", "Wartość"])
    ws.append(["PESEL", "90010112345"])
    ws.append(["Województwo", "Mazowieckie"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def make_test_ods_bytes() -> bytes:
    doc = OpenDocumentSpreadsheet()
    table = Table(name="Arkusz1")
    doc.spreadsheet.addElement(table)

    row1 = TableRow()
    table.addElement(row1)
    cell1 = TableCell()
    cell1.addElement(P(text="Nazwa"))
    row1.addElement(cell1)
    cell2 = TableCell()
    cell2.addElement(P(text="Wartosc"))
    row1.addElement(cell2)

    row2 = TableRow()
    table.addElement(row2)
    cell3 = TableCell()
    cell3.addElement(P(text="PESEL"))
    row2.addElement(cell3)
    cell4 = TableCell()
    cell4.addElement(P(text="90010112345"))
    row2.addElement(cell4)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def make_test_image_bytes(format: str = "PNG", text: str = "DOKUMENT") -> bytes:
    img = Image.new("RGB", (300, 100), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((20, 30), text, fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format=format)
    return buf.getvalue()
