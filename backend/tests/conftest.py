"""Shared test fixtures and helpers."""

import pytest
from fastapi.testclient import TestClient

from coi_form_digitization.infrastructure.config import Settings, get_settings
from coi_form_digitization.presentation.app_factory import create_app

# Minimal magic bytes for each supported format used across tests.
PDF_MAGIC = b"%PDF-1.4 test content" + b"\x00" * 100
PNG_MAGIC = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
JPEG_MAGIC = b"\xff\xd8\xff\xe0" + b"\x00" * 100
# ZIP magic (simulates docx/xlsx/ods container)
ZIP_MAGIC = b"PK\x03\x04" + b"\x00" * 100
# OLE2 magic for legacy .doc
OLE2_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 100


def _build_test_settings(**overrides) -> Settings:
    base = dict(
        app_port=8000,
        max_file_size_bytes=15_728_640,
        auth_required=True,
        jwt_secret="test-secret-key-for-tests",
        jwt_algorithm="HS256",
        demo_access_key="test-demo-key",
        ai_provider="heuristic",
        ai_base_url="",
        ai_model_name="local-model",
        ai_model_path="",
        knowledge_base_dir="/tmp/kb",
    )
    base.update(overrides)
    return Settings(**base)


@pytest.fixture()
def test_settings() -> Settings:
    return _build_test_settings()


@pytest.fixture()
def client(test_settings: Settings) -> TestClient:
    """API client with auth required (default)."""
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: test_settings
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def client_no_auth(test_settings: Settings) -> TestClient:
    """API client with AUTH_REQUIRED=false for upload-only tests."""
    settings = _build_test_settings(auth_required=False)
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def valid_token(test_settings: Settings) -> str:
    from coi_form_digitization.infrastructure.jwt_service import JwtTokenService

    return JwtTokenService(test_settings).issue("test-user")
