"""Critical validation and grouping behavior for deterministic form structuring."""

import pytest

from coi_form_digitization.domain.extracted_document import (
    CheckboxItem,
    ExtractedDocument,
    ExtractedPage,
    KeyValuePair,
)
from coi_form_digitization.domain.structured_form import FieldType
from coi_form_digitization.infrastructure.structurers.deterministic_form_structurer import (
    DeterministicFormStructurer,
    slugify,
)


@pytest.mark.parametrize(
    ("key", "value", "field_type", "valid"),
    [
        ("PESEL", "90010112349", FieldType.PESEL, True),
        ("PESEL", "90010112345", FieldType.PESEL, False),
        ("PESEL", "00223100002", FieldType.PESEL, False),
        ("NIP", "526-025-02-74", FieldType.NIP, True),
        ("NIP", "5260250275", FieldType.NIP, False),
        ("REGON", "123456785", FieldType.REGON, True),
        ("REGON", "123456784", FieldType.REGON, False),
        ("REGON", "12345678500002", FieldType.REGON, True),
        ("REGON", "12345678500003", FieldType.REGON, False),
        ("Kod pocztowy", "00-001", FieldType.POSTAL_CODE, True),
        ("Kod pocztowy", "00001", FieldType.POSTAL_CODE, False),
        ("Data wniosku", "29.02.2024", FieldType.DATE, True),
        ("Data wniosku", "29.02.2023", FieldType.DATE, False),
    ],
)
def test_polish_administrative_validation(
    key: str, value: str, field_type: FieldType, valid: bool
) -> None:
    result = DeterministicFormStructurer().structure(
        ExtractedDocument(
            filename="form.pdf",
            format="pdf",
            pages=[ExtractedPage(page_number=1, key_values=[KeyValuePair(key, value)])],
        )
    )

    field = result.sections[0].fields[0]
    assert field.field_type is field_type
    assert field.is_valid is valid
    assert (field.validation_error is None) is valid


def test_slugifies_polish_diacritics_and_deduplicates_field_ids() -> None:
    assert slugify("Łódź — żółć") == "lodz_zolc"
    form = DeterministicFormStructurer().structure(
        ExtractedDocument(
            filename="form.pdf",
            format="pdf",
            pages=[
                ExtractedPage(
                    page_number=1,
                    key_values=[KeyValuePair("Łódź", "A"), KeyValuePair("Lodz", "B")],
                )
            ],
        )
    )

    assert [field.field_id for field in form.sections[0].fields] == ["lodz", "lodz_2"]


def test_sections_group_content_by_headings_and_keep_preamble_general() -> None:
    form = DeterministicFormStructurer().structure(
        ExtractedDocument(
            filename="form.pdf",
            format="pdf",
            pages=[
                ExtractedPage(page_number=1, key_values=[KeyValuePair("Wstęp", "A")]),
                ExtractedPage(
                    page_number=2,
                    headings=["Dane osobowe"],
                    key_values=[KeyValuePair("Imię", "Jan")],
                ),
                ExtractedPage(
                    page_number=3,
                    headings=["Adres"],
                    key_values=[KeyValuePair("Miasto", "Łódź")],
                ),
            ],
        )
    )

    assert [section.title for section in form.sections] == ["General", "Dane osobowe", "Adres"]
    assert [section.order for section in form.sections] == [1, 2, 3]
    assert form.total_fields == 3
    assert form.fields_needing_review == 0
    assert form.form_title == "Dane osobowe"


def test_checkbox_pairs_and_multiple_choices_are_grouped() -> None:
    form = DeterministicFormStructurer().structure(
        ExtractedDocument(
            filename="form.pdf",
            format="pdf",
            pages=[
                ExtractedPage(
                    page_number=1,
                    headings=["Zgody"],
                    checkboxes=[
                        CheckboxItem("Tak", is_checked=True),
                        CheckboxItem("Nie", is_checked=False),
                        CheckboxItem("SMS", is_checked=True),
                        CheckboxItem("E-mail", is_checked=False),
                        CheckboxItem("Telefon", is_checked=True),
                    ],
                )
            ],
        )
    )

    groups = form.sections[0].choice_groups
    assert [group.selection_type for group in groups] == ["single", "multiple"]
    assert groups[0].needs_review is False
    assert [option.label for option in groups[1].options] == ["SMS", "E-mail", "Telefon"]
    assert groups[1].needs_review is False


def test_review_counts_cover_empty_low_confidence_and_unselected_binary_pair() -> None:
    form = DeterministicFormStructurer().structure(
        ExtractedDocument(
            filename="form.pdf",
            format="pdf",
            pages=[
                ExtractedPage(
                    page_number=1,
                    headings=["Dane"],
                    key_values=[
                        KeyValuePair("Nazwa", "", confidence=0.95),
                        KeyValuePair("Miasto", "Łódź", confidence=0.79),
                    ],
                    checkboxes=[CheckboxItem("Tak"), CheckboxItem("Nie")],
                )
            ],
        )
    )

    assert form.total_fields == 2
    assert form.fields_needing_review == 2
    assert [field.needs_review for field in form.sections[0].fields] == [True, True]
    assert form.sections[0].choice_groups[0].needs_review is True
