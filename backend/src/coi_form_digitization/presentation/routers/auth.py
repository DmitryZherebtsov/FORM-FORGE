"""Router: POST /api/v1/auth/token"""

from fastapi import APIRouter, Depends, HTTPException

from coi_form_digitization.application.dtos import TokenRequestDTO, TokenResponseDTO
from coi_form_digitization.infrastructure.config import Settings, get_settings
from coi_form_digitization.infrastructure.jwt_service import JwtTokenService
from coi_form_digitization.presentation.dependencies import get_jwt_service

router = APIRouter(tags=["auth"])


@router.post("/token", response_model=TokenResponseDTO)
async def issue_token(
    body: TokenRequestDTO,
    settings: Settings = Depends(get_settings),
    jwt_service: JwtTokenService = Depends(get_jwt_service),
) -> TokenResponseDTO:
    """Issue a signed JWT for a valid DEMO_ACCESS_KEY."""
    if body.access_key != settings.demo_access_key:
        raise HTTPException(status_code=401, detail="Invalid access key.")
    token = jwt_service.issue(subject="demo-user")
    return TokenResponseDTO(access_token=token)
