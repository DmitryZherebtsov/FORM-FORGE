"""COI Form Digitization backend package."""

from coi_form_digitization.presentation.app_factory import create_app

app = create_app()


def main() -> None:
    import uvicorn

    from coi_form_digitization.infrastructure.config import get_settings

    settings = get_settings()
    uvicorn.run(
        "coi_form_digitization:app",
        host="0.0.0.0",
        port=settings.app_port,
        reload=False,
    )
