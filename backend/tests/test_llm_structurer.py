"""Critical contracts for optional LLM refinement and deterministic fallback."""

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from coi_form_digitization.domain.extracted_document import (
    ExtractedDocument,
    ExtractedPage,
    KeyValuePair,
)
from coi_form_digitization.infrastructure.config import Settings, get_settings
from coi_form_digitization.infrastructure.jwt_service import JwtTokenService
from coi_form_digitization.infrastructure.structurers.deterministic_form_structurer import (
    DeterministicFormStructurer,
)
from coi_form_digitization.infrastructure.structurers.openai_compat_form_structurer import (
    OpenAICompatFormStructurer,
)
from coi_form_digitization.presentation.app_factory import create_app
from coi_form_digitization.presentation.dependencies import get_form_structurer


def _settings(**overrides) -> Settings:
    values = {
        "auth_required": True,
        "jwt_secret": "test-llm-secret-key-that-is-long-enough",
        "demo_access_key": "test-demo-key",
        "enable_llm": True,
        "ai_provider": "openai_compat",
        "ai_base_url": "http://llm.test",
        "ai_model_name": "test-model",
        "ai_timeout_seconds": 1.0,
    }
    values.update(overrides)
    return Settings(**values)


def _extracted() -> ExtractedDocument:
    return ExtractedDocument(
        filename="wniosek.pdf",
        format="pdf",
        pages=[
            ExtractedPage(
                page_number=1,
                headings=["Dane wnioskodawcy"],
                key_values=[
                    KeyValuePair("PESEL", "90010112346"),
                    KeyValuePair("NIP", "1234567890"),
                ],
                raw_text="Dane wnioskodawcy PESEL NIP",
            )
        ],
    )


def test_disabled_llm_bypasses_http() -> None:
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(500)

    structurer = OpenAICompatFormStructurer(
        _settings(enable_llm=False), transport=httpx.MockTransport(handle)
    )

    result = structurer.structure(_extracted())

    assert structurer.mode == "heuristic"
    assert result == DeterministicFormStructurer().structure(_extracted())
    assert requests == []


def test_llm_refinement_keeps_deterministic_pesel_and_nip_checksums() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        request_body = json.loads(request.content)
        prompt = json.loads(request_body["messages"][1]["content"])
        section = prompt["form"]["sections"][0]
        payload = {
            "form_title": "Ulepszony wniosek",
            "section_titles": {section["section_id"]: "Identyfikacja osoby"},
            "field_labels": {
                item["field_id"]: "Pole ujednolicone" for item in section["fields"]
            },
            "field_types": {item["field_id"]: "text" for item in section["fields"]},
            "choice_groups": {},
        }
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(payload)}}]},
        )

    structurer = OpenAICompatFormStructurer(
        _settings(), transport=httpx.MockTransport(handle)
    )

    result = structurer.structure(_extracted())
    fields = {item.field_id: item for item in result.sections[0].fields}

    assert structurer.mode == "llm"
    assert result.form_title == "Ulepszony wniosek"
    assert result.sections[0].title == "Identyfikacja osoby"
    assert fields["pesel"].field_type.value == "pesel"
    assert fields["pesel"].is_valid is False
    assert fields["nip"].field_type.value == "nip"
    assert fields["nip"].is_valid is False


@pytest.mark.parametrize("error_type", [httpx.ConnectError, httpx.ReadTimeout])
def test_llm_network_errors_fall_back_without_logging_document_text(
    error_type: type[httpx.HTTPError], caplog: pytest.LogCaptureFixture
) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        raise error_type("unavailable", request=request)

    structurer = OpenAICompatFormStructurer(
        _settings(), transport=httpx.MockTransport(handle)
    )

    result = structurer.structure(_extracted())

    assert structurer.mode == "heuristic_fallback"
    assert result == DeterministicFormStructurer().structure(_extracted())
    assert "90010112346" not in caplog.text
    assert "unavailable" not in caplog.text


def test_warmup_endpoint_is_protected_and_reports_readiness() -> None:
    methods: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": []})
        return httpx.Response(200, json={"choices": [{"message": {"content": "1"}}]})

    settings = _settings()
    structurer = OpenAICompatFormStructurer(
        settings, transport=httpx.MockTransport(handle)
    )
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_form_structurer] = lambda: structurer
    client = TestClient(app)
    token = JwtTokenService(settings).issue("test-user")

    assert client.post("/api/v1/llm/warmup").status_code == 401
    response = client.post(
        "/api/v1/llm/warmup", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["model"] == "test-model"
    assert response.json()["latency_ms"] >= 0
    assert methods == ["GET", "POST"]


def test_health_pings_configured_llm_without_running_completion() -> None:
    methods: list[tuple[str, str]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        methods.append((request.method, request.url.path))
        return httpx.Response(200, json={"models": []})

    settings = _settings(ai_base_url="http://health-llm.test")
    structurer = OpenAICompatFormStructurer(
        settings, transport=httpx.MockTransport(handle)
    )
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_form_structurer] = lambda: structurer

    response = TestClient(app).get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["llm_enabled"] is True
    assert response.json()["llm_status"] == "configured"
    assert methods == [("GET", "/api/tags")]


def test_health_reprobes_models_after_cached_unreachable_status() -> None:
    paths: list[str] = []
    model_attempts = 0

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal model_attempts
        paths.append(request.url.path)
        if request.url.path == "/api/tags":
            return httpx.Response(403)
        if request.url.path == "/v1/models":
            model_attempts += 1
            return httpx.Response(403 if model_attempts == 1 else 200, json={"data": []})
        return httpx.Response(404)

    settings = _settings(ai_base_url="http://health-retry.test")
    structurer = OpenAICompatFormStructurer(
        settings, transport=httpx.MockTransport(handle)
    )
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_form_structurer] = lambda: structurer
    client = TestClient(app)

    first_response = client.get("/api/v1/health")
    second_response = client.get("/api/v1/health")

    assert first_response.status_code == 200
    assert first_response.json()["llm_status"] == "unreachable"
    assert second_response.status_code == 200
    assert second_response.json()["llm_status"] == "configured"
    assert paths == ["/api/tags", "/v1/models", "/v1/models"]
