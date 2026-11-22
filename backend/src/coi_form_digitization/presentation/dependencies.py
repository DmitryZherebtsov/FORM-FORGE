"""Presentation: JWT Bearer FastAPI dependency."""

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from coi_form_digitization.domain.exceptions import AuthenticationError
from coi_form_digitization.domain.ports import FormDefinitionMapperPort
from coi_form_digitization.infrastructure.config import Settings, get_settings
from coi_form_digitization.infrastructure.jwt_service import JwtTokenService
from coi_form_digitization.infrastructure.structurers.coi_form_definition_mapper import (
    DeterministicFormDefinitionMapper,
)
from coi_form_digitization.infrastructure.structurers.deterministic_form_structurer import (
    DeterministicFormStructurer,
)
from coi_form_digitization.infrastructure.structurers.openai_compat_form_structurer import (
    OpenAICompatFormStructurer,
)

_bearer_scheme = HTTPBearer(auto_error=False)


def get_jwt_service(settings: Settings = Depends(get_settings)) -> JwtTokenService:
    return JwtTokenService(settings)


def get_form_structurer(
    settings: Settings = Depends(get_settings),
) -> OpenAICompatFormStructurer:
    return OpenAICompatFormStructurer(settings, deterministic=DeterministicFormStructurer())


def get_form_definition_mapper() -> FormDefinitionMapperPort:
    return DeterministicFormDefinitionMapper()


async def require_jwt(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    settings: Settings = Depends(get_settings),
    jwt_service: JwtTokenService = Depends(get_jwt_service),
) -> dict:
    """FastAPI dependency that enforces JWT auth when AUTH_REQUIRED is true."""
    if not settings.auth_required:
        return {}

    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Missing Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return jwt_service.verify(credentials.credentials)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=401,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
