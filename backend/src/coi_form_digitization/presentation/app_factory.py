"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from coi_form_digitization.infrastructure.config import get_settings
from coi_form_digitization.presentation.exception_handlers import register_exception_handlers
from coi_form_digitization.presentation.routers import auth, forms, health, llm

_API_V1_PREFIX = "/api/v1"


def create_app() -> FastAPI:
    """Construct and configure the FastAPI application."""
    app = FastAPI(
        title="COI Form Digitization API",
        description="Converts public administration forms into structured COI e-Service JSON.",
        version="1.0.0",
    )

    settings = get_settings()
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    register_exception_handlers(app)

    app.include_router(health.router, prefix=_API_V1_PREFIX)
    app.include_router(llm.router, prefix=_API_V1_PREFIX)
    app.include_router(auth.router, prefix=f"{_API_V1_PREFIX}/auth")
    app.include_router(forms.router, prefix=f"{_API_V1_PREFIX}/forms")

    return app
