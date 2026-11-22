"""Immutable domain models for semantically structured forms."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from coi_form_digitization.domain.extracted_document import TableData


class FieldType(StrEnum):
    TEXT = "text"
    DATE = "date"
    PESEL = "pesel"
    NIP = "nip"
    REGON = "regon"
    POSTAL_CODE = "postal_code"
    EMAIL = "email"
    PHONE = "phone"
    CHECKBOX = "checkbox"
    CHOICE_GROUP = "choice_group"
    TABLE = "table"


@dataclass(frozen=True)
class FormField:
    field_id: str
    label: str
    field_type: FieldType
    value: str
    is_valid: bool
    validation_error: str | None
    confidence: float
    needs_review: bool


@dataclass(frozen=True)
class ChoiceOption:
    label: str
    is_selected: bool


@dataclass(frozen=True)
class ChoiceGroup:
    group_id: str
    label: str | None
    selection_type: Literal["single", "multiple"]
    options: list[ChoiceOption]
    needs_review: bool


@dataclass(frozen=True)
class FormSection:
    section_id: str
    title: str
    order: int
    fields: list[FormField]
    choice_groups: list[ChoiceGroup]
    tables: list[TableData]


@dataclass(frozen=True)
class StructuredForm:
    filename: str
    format: str
    form_title: str | None
    sections: list[FormSection]
    total_fields: int
    fields_needing_review: int
    overall_confidence: float
