"""Immutable domain model for importable COI e-Service form definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal


class ComponentType(StrEnum):
    SECTION = "SECTION"
    REPEATING_SECTION = "REPEATING_SECTION"
    TEXT_FIELD = "TEXT_FIELD"
    NUMBER = "NUMBER"
    DATEPICKER = "DATEPICKER"
    RADIO = "RADIO"
    CHECKBOX = "CHECKBOX"
    SELECT = "SELECT"
    TEXTAREA = "TEXTAREA"
    FILE_UPLOADER = "FILE_UPLOADER"
    TEXT_BLOCK = "TEXT_BLOCK"
    CONSENT_SECTION = "CONSENT_SECTION"
    INFO_SECTION = "INFO_SECTION"


class TabType(StrEnum):
    MAIN = "MAIN"
    FINISH = "FINISH"


@dataclass(frozen=True)
class FormOption:
    id: str
    name: str
    tech_name: str


@dataclass(frozen=True)
class FieldState:
    type: Literal["SHOW", "READ_ONLY"]
    query: str


@dataclass(frozen=True)
class ConsentItem:
    description: str
    required: bool


@dataclass(frozen=True)
class ConsentSectionConfig:
    consents: list[ConsentItem] = field(default_factory=list)
    files: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FormQuestionField:
    id: str
    type: ComponentType
    tech_name: str
    title: str
    description: str = ""
    options: list[FormOption] = field(default_factory=list)
    validation: list[str] = field(default_factory=list)
    dictionary_name: str | None = None
    read_only: bool = False
    repeating_section_grid: list[FormQuestion] = field(default_factory=list)
    default_value: str | list[str] | None = None
    default_value_type: str | None = None
    consent_section_config: ConsentSectionConfig | None = None
    states: list[FieldState] = field(default_factory=list)
    question_order: int = 0
    tooltip_message: str = ""
    multi_level_tree: bool | None = None
    search_enabled: bool | None = None


@dataclass(frozen=True)
class FormQuestion:
    x: int
    y: int
    rows: int
    cols: int
    field: FormQuestionField


@dataclass(frozen=True)
class FormTab:
    id: str
    title: str
    type: TabType
    questions: list[FormQuestion] = field(default_factory=list)


@dataclass(frozen=True)
class FlowLink:
    id: str
    source: str
    target: str


@dataclass(frozen=True)
class FormFlow:
    links: list[FlowLink] = field(default_factory=list)


@dataclass(frozen=True)
class FormDefinition:
    title: str
    tabs: list[FormTab]
    flow: FormFlow

    def __post_init__(self) -> None:
        if len(self.title) > 255:
            raise ValueError("FormDefinition title cannot exceed 255 characters.")
