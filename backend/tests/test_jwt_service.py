"""JWT service unit tests — critical paths only."""

import jwt
import pytest

from coi_form_digitization.domain.exceptions import AuthenticationError
from coi_form_digitization.infrastructure.jwt_service import JwtTokenService
from tests.conftest import _build_test_settings


@pytest.fixture()
def jwt_service() -> JwtTokenService:
    return JwtTokenService(_build_test_settings())


class TestJwtTokenService:
    def test_verify_valid_token_returns_claims(self, jwt_service: JwtTokenService) -> None:
        token = jwt_service.issue("user-123")
        claims = jwt_service.verify(token)
        assert claims["sub"] == "user-123"

    def test_tampered_token_raises(self, jwt_service: JwtTokenService) -> None:
        token = jwt_service.issue("user-123")
        with pytest.raises(AuthenticationError):
            jwt_service.verify(token[:-4] + "XXXX")

    def test_wrong_secret_raises(self, jwt_service: JwtTokenService) -> None:
        other = JwtTokenService(_build_test_settings(jwt_secret="different-secret"))
        with pytest.raises(AuthenticationError):
            jwt_service.verify(other.issue("user"))

    def test_expired_token_raises(self) -> None:
        settings = _build_test_settings()
        expired = jwt.encode({"sub": "u", "iat": 0, "exp": 1}, settings.jwt_secret, algorithm=settings.jwt_algorithm)
        with pytest.raises(AuthenticationError, match="expired"):
            JwtTokenService(settings).verify(expired)
