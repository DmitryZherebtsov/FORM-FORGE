"""Router: POST /api/v1/forms/digitize"""

import asyncio

from fastapi import APIRouter, Depends, UploadFile

from coi_form_digitization.application.dtos import (
    CheckboxItemDTO,
    ChoiceGroupDTO,
    ChoiceOptionDTO,
    DigitizeResponseDTO,
    ExtractedDocumentDTO,
    ExtractedPageDTO,
    FormDefinitionDTO,
    FormFieldDTO,
    FormSectionDTO,
    KeyValuePairDTO,
    StructuredFormDTO,
    TableDataDTO,
)
from coi_form_digitization.domain.extracted_document import ExtractedDocument
from coi_form_digitization.domain.ports import FormDefinitionMapperPort, FormStructurerPort
from coi_form_digitization.domain.structured_form import StructuredForm
from coi_form_digitization.infrastructure.config import Settings, get_settings
from coi_form_digitization.infrastructure.extractors.composite import CompositeDocumentExtractor
from coi_form_digitization.infrastructure.upload_validator import UploadSecurityValidator
from coi_form_digitization.presentation.dependencies import (
    get_form_definition_mapper,
    get_form_structurer,
    require_jwt,
)

router = APIRouter(tags=["forms"])


def _get_validator(settings: Settings = Depends(get_settings)) -> UploadSecurityValidator:
    return UploadSecurityValidator(settings)


_extractor_instance: CompositeDocumentExtractor | None = None


def _get_extractor() -> CompositeDocumentExtractor:
    global _extractor_instance
    if _extractor_instance is None:
        _extractor_instance = CompositeDocumentExtractor()
    return _extractor_instance


def _map_extracted_to_dto(extracted: ExtractedDocument) -> ExtractedDocumentDTO:
    pages_dto = [
        ExtractedPageDTO(
            page_number=p.page_number,
            headings=p.headings,
            paragraphs=p.paragraphs,
            key_values=[KeyValuePairDTO(key=kv.key, value=kv.value, confidence=kv.confidence) for kv in p.key_values],
            tables=[TableDataDTO(headers=t.headers, rows=t.rows, title=t.title) for t in p.tables],
            checkboxes=[
                CheckboxItemDTO(label=cb.label, is_checked=cb.is_checked, context=cb.context) for cb in p.checkboxes
            ],
            raw_text=p.raw_text,
        )
        for p in extracted.pages
    ]
    return ExtractedDocumentDTO(
        filename=extracted.filename,
        format=extracted.format,
        total_pages=extracted.total_pages,
        pages=pages_dto,
        metadata=extracted.metadata,
    )


def _map_structured_form_to_dto(form: StructuredForm) -> StructuredFormDTO:
    return StructuredFormDTO(
        filename=form.filename,
        format=form.format,
        form_title=form.form_title,
        sections=[
            FormSectionDTO(
                section_id=section.section_id,
                title=section.title,
                order=section.order,
                fields=[
                    FormFieldDTO(
                        field_id=item.field_id,
                        label=item.label,
                        field_type=item.field_type.value,
                        value=item.value,
                        is_valid=item.is_valid,
                        validation_error=item.validation_error,
                        confidence=item.confidence,
                        needs_review=item.needs_review,
                    )
                    for item in section.fields
                ],
                choice_groups=[
                    ChoiceGroupDTO(
                        group_id=group.group_id,
                        label=group.label,
                        selection_type=group.selection_type,
                        options=[
                            ChoiceOptionDTO(label=option.label, is_selected=option.is_selected)
                            for option in group.options
                        ],
                        needs_review=group.needs_review,
                    )
                    for group in section.choice_groups
                ],
                tables=[
                    TableDataDTO(headers=table.headers, rows=table.rows, title=table.title)
                    for table in section.tables
                ],
            )
            for section in form.sections
        ],
        total_fields=form.total_fields,
        fields_needing_review=form.fields_needing_review,
        overall_confidence=form.overall_confidence,
    )


@router.post("/digitize", response_model=DigitizeResponseDTO, response_model_exclude_none=True)
async def digitize(
    file: UploadFile,
    _claims: dict = Depends(require_jwt),
    validator: UploadSecurityValidator = Depends(_get_validator),
    extractor: CompositeDocumentExtractor = Depends(_get_extractor),
    structurer: FormStructurerPort = Depends(get_form_structurer),
    definition_mapper: FormDefinitionMapperPort = Depends(get_form_definition_mapper),
) -> DigitizeResponseDTO:
    """Validate uploaded document and extract structured elements strictly in-memory."""
    data = await file.read()
    metadata = await asyncio.to_thread(validator.validate, file.filename or "", data)
    extracted = await asyncio.to_thread(extractor.extract, metadata.original_filename, data)
    structured_form = await asyncio.to_thread(structurer.structure, extracted)
    form_definition = await asyncio.to_thread(
        definition_mapper.build_definition, extracted, structured_form
    )

    return DigitizeResponseDTO(
        status="success",
        filename=metadata.original_filename,
        extension=metadata.extension,
        size_bytes=metadata.size_bytes,
        detected_mime=metadata.detected_mime,
        extracted=_map_extracted_to_dto(extracted),
        structured_form=_map_structured_form_to_dto(structured_form),
        form_definition=FormDefinitionDTO.model_validate(form_definition),
        structuring_mode=getattr(structurer, "mode", "heuristic"),
    )
