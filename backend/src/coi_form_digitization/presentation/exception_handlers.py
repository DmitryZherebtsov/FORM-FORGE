"""Presentation: maps domain exceptions to FastAPI HTTP responses."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from coi_form_digitization.domain.exceptions import (
    AuthenticationError,
    DocumentProcessingError,
    PayloadTooLargeError,
    SecurityValidationError,
    UnsupportedFormatError,
)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(SecurityValidationError)
    async def _security_handler(_: Request, exc: SecurityValidationError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": exc.detail})

    @app.exception_handler(PayloadTooLargeError)
    async def _payload_handler(_: Request, exc: PayloadTooLargeError) -> JSONResponse:
        return JSONResponse(
            status_code=413,
            content={"detail": str(exc)},
        )

    @app.exception_handler(UnsupportedFormatError)
    async def _format_handler(_: Request, exc: UnsupportedFormatError) -> JSONResponse:
        return JSONResponse(status_code=415, content={"detail": exc.detail})

    @app.exception_handler(AuthenticationError)
    async def _auth_handler(_: Request, exc: AuthenticationError) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content={"detail": str(exc)},
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.exception_handler(DocumentProcessingError)
    async def _doc_handler(_: Request, exc: DocumentProcessingError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})
