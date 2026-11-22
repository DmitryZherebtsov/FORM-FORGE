"""Router: GET /api/v1/health"""

from fastapi import APIRouter, Depends

from coi_form_digitization.application.dtos import HealthResponseDTO
from coi_form_digitization.infrastructure.config import Settings, get_settings
from coi_form_digitization.infrastructure.structurers.openai_compat_form_structurer import (
    OpenAICompatFormStructurer,
)
from coi_form_digitization.presentation.dependencies import get_form_structurer

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponseDTO)
async def health(
    settings: Settings = Depends(get_settings),
    structurer: OpenAICompatFormStructurer = Depends(get_form_structurer),
) -> HealthResponseDTO:
    """Public liveness and readiness probe."""
    await structurer.ping()
    return HealthResponseDTO(
        status="ok",
        ai_provider=structurer.effective_provider,
        service="coi-form-digitization",
        version="1.0.0",
        llm_enabled=structurer.enabled,
        ai_model=settings.ai_model_name,
        llm_status=structurer.health_status,
    )
