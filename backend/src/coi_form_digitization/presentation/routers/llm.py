"""Router for explicit LLM readiness checks."""

from fastapi import APIRouter, Depends

from coi_form_digitization.application.dtos import LlmWarmupResponseDTO
from coi_form_digitization.infrastructure.structurers.openai_compat_form_structurer import (
    OpenAICompatFormStructurer,
)
from coi_form_digitization.presentation.dependencies import get_form_structurer, require_jwt

router = APIRouter(tags=["llm"])


@router.post("/llm/warmup", response_model=LlmWarmupResponseDTO)
async def warmup_llm(
    _claims: dict = Depends(require_jwt),
    structurer: OpenAICompatFormStructurer = Depends(get_form_structurer),
) -> LlmWarmupResponseDTO:
    result = await structurer.warmup()
    return LlmWarmupResponseDTO(**result)
