"""Infrastructure: JWT token issuance and verification."""

from datetime import UTC, datetime, timedelta

import jwt

from coi_form_digitization.domain.exceptions import AuthenticationError
from coi_form_digitization.infrastructure.config import Settings

_TOKEN_EXPIRY_HOURS = 24


class JwtTokenService:
    """Issues and verifies HS256 JWT tokens."""

    def __init__(self, settings: Settings) -> None:
        self._secret = settings.jwt_secret
        self._algorithm = settings.jwt_algorithm

    def issue(self, subject: str) -> str:
        now = datetime.now(tz=UTC)
        payload = {
            "sub": subject,
            "iat": now,
            "exp": now + timedelta(hours=_TOKEN_EXPIRY_HOURS),
        }
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def verify(self, token: str) -> dict:
        """Decode and validate a JWT token; raise AuthenticationError on failure."""
        try:
            return jwt.decode(token, self._secret, algorithms=[self._algorithm])
        except jwt.ExpiredSignatureError as exc:
            raise AuthenticationError("Token has expired.") from exc
        except jwt.InvalidTokenError as exc:
            raise AuthenticationError("Invalid token.") from exc
