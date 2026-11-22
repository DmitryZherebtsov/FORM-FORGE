"""Application-layer DTOs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class TokenRequestDTO(BaseModel):
    access_key: str


class TokenResponseDTO(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CheckboxItemDTO(BaseModel):
    label: str
    is_checked: bool
    context: str | None = None


class KeyValuePairDTO(BaseModel):
    key: str
    value: str
    confidence: float = 1.0


class TableDataDTO(BaseModel):
    headers: list[str]
    rows: list[list[str]]
    title: str | None = None


class ExtractedPageDTO(BaseModel):
    page_number: int
    headings: list[str]
    paragraphs: list[str]
    key_values: list[KeyValuePairDTO]
    tables: list[TableDataDTO]
    checkboxes: list[CheckboxItemDTO]
    raw_text: str


class ExtractedDocumentDTO(BaseModel):
    filename: str
    format: str
    total_pages: int
    pages: list[ExtractedPageDTO]
    metadata: dict[str, Any]


class FormFieldDTO(BaseModel):
    field_id: str
    label: str
    field_type: str
    value: str
    is_valid: bool
    validation_error: str | None
    confidence: float
    needs_review: bool


class ChoiceOptionDTO(BaseModel):
    label: str
    is_selected: bool


class ChoiceGroupDTO(BaseModel):
    group_id: str
    label: str | None
    selection_type: str
    options: list[ChoiceOptionDTO]
    needs_review: bool


class FormSectionDTO(BaseModel):
    section_id: str
    title: str
    order: int
    fields: list[FormFieldDTO]
    choice_groups: list[ChoiceGroupDTO]
    tables: list[TableDataDTO]


class StructuredFormDTO(BaseModel):
    filename: str
    format: str
    form_title: str | None
    sections: list[FormSectionDTO]
    total_fields: int
    fields_needing_review: int
    overall_confidence: float


class _FormDefinitionModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class FormOptionDTO(_FormDefinitionModel):
    id: str
    name: str
    tech_name: str = Field(serialization_alias="techName")


class FieldStateDTO(_FormDefinitionModel):
    type: str
    query: str


class ConsentItemDTO(_FormDefinitionModel):
    description: str
    required: bool


class ConsentSectionConfigDTO(_FormDefinitionModel):
    consents: list[ConsentItemDTO]
    files: list[str]


class FormQuestionFieldDTO(_FormDefinitionModel):
    id: str
    type: str
    tech_name: str = Field(serialization_alias="techName")
    title: str
    description: str
    options: list[FormOptionDTO]
    validation: list[str]
    dictionary_name: str | None = Field(default=None, serialization_alias="dictionaryName")
    read_only: bool = Field(serialization_alias="readOnly")
    repeating_section_grid: list[FormQuestionDTO] = Field(
        serialization_alias="repeatingSectionGrid"
    )
    default_value: str | list[str] | None = Field(default=None, serialization_alias="defaultValue")
    default_value_type: str | None = Field(default=None, serialization_alias="defaultValueType")
    consent_section_config: ConsentSectionConfigDTO | None = Field(
        default=None, serialization_alias="consentSectionConfig"
    )
    states: list[FieldStateDTO]
    question_order: int = Field(serialization_alias="questionOrder")
    tooltip_message: str = Field(serialization_alias="tooltipMessage")
    multi_level_tree: bool | None = Field(default=None, serialization_alias="multiLevelTree")
    search_enabled: bool | None = Field(default=None, serialization_alias="searchEnabled")


class FormQuestionDTO(_FormDefinitionModel):
    x: int
    y: int
    rows: int
    cols: int
    field: FormQuestionFieldDTO


class FormTabDTO(_FormDefinitionModel):
    id: str
    title: str
    type: str
    questions: list[FormQuestionDTO]


class FlowLinkDTO(_FormDefinitionModel):
    id: str
    source: str
    target: str


class FormFlowDTO(_FormDefinitionModel):
    links: list[FlowLinkDTO]


class FormDefinitionDTO(_FormDefinitionModel):
    title: str
    tabs: list[FormTabDTO]
    flow: FormFlowDTO


class DigitizeResponseDTO(BaseModel):
    status: str
    filename: str
    extension: str
    size_bytes: int
    detected_mime: str
    extracted: ExtractedDocumentDTO | None = None
    structured_form: StructuredFormDTO | None = None
    form_definition: FormDefinitionDTO | None = None
    structuring_mode: Literal["heuristic", "llm", "heuristic_fallback"] = "heuristic"


class HealthResponseDTO(BaseModel):
    status: str
    ai_provider: str
    service: str
    version: str
    llm_enabled: bool
    ai_model: str
    llm_status: Literal["disabled", "configured", "unreachable"]


class LlmWarmupResponseDTO(BaseModel):
    status: Literal["ready", "disabled", "unreachable"]
    model: str
    latency_ms: float
    detail: str | None = None
