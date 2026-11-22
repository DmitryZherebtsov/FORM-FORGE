"""API integration tests — critical paths only."""

import io
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from coi_form_digitization.infrastructure.extractors.legacy_doc_extractor import LegacyDocExtractor
from tests.conftest import OLE2_MAGIC, PDF_MAGIC, PNG_MAGIC
from tests.fixtures_generator import (
    make_test_docx_bytes,
    make_test_image_bytes,
    make_test_ods_bytes,
    make_test_pdf_bytes,
    make_test_xlsx_bytes,
)


class TestHealthEndpoint:
    def test_health_ok(self, client: TestClient) -> None:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["ai_provider"] == "heuristic"
        assert data["service"] == "coi-form-digitization"
        assert data["llm_enabled"] is False
        assert data["llm_status"] == "disabled"
        assert data["ai_model"] == "local-model"


class TestAuthEndpoint:
    def test_valid_key_returns_token(self, client: TestClient) -> None:
        response = client.post("/api/v1/auth/token", json={"access_key": "test-demo-key"})
        assert response.status_code == 200
        assert "access_token" in response.json()

    def test_invalid_key_returns_401(self, client: TestClient) -> None:
        response = client.post("/api/v1/auth/token", json={"access_key": "wrong-key"})
        assert response.status_code == 401


class TestDigitizeSecurityValidation:
    def _upload(self, client: TestClient, filename: str, data: bytes, token: str | None = None):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return client.post(
            "/api/v1/forms/digitize",
            files={"file": (filename, io.BytesIO(data), "application/octet-stream")},
            headers=headers,
        )

    def test_missing_token_returns_401(self, client: TestClient) -> None:
        assert self._upload(client, "form.pdf", PDF_MAGIC).status_code == 401

    def test_invalid_token_returns_401(self, client: TestClient) -> None:
        assert self._upload(client, "form.pdf", PDF_MAGIC, token="bad.token.here").status_code == 401

    def test_auth_disabled_accepts_without_token(self, client_no_auth: TestClient) -> None:
        pdf_bytes = make_test_pdf_bytes()
        res = self._upload(client_no_auth, "form.pdf", pdf_bytes)
        assert res.status_code == 200
        assert res.json()["status"] == "success"
        assert res.json()["structuring_mode"] == "heuristic"

    def test_filename_too_long_returns_400(self, client_no_auth: TestClient) -> None:
        assert self._upload(client_no_auth, "a" * 247 + ".pdf", PDF_MAGIC).status_code == 400

    def test_forbidden_char_in_filename_returns_400(self, client_no_auth: TestClient) -> None:
        assert self._upload(client_no_auth, "bad;file.pdf", PDF_MAGIC).status_code == 400

    def test_spoofed_mime_returns_415(self, client_no_auth: TestClient) -> None:
        assert self._upload(client_no_auth, "evil.pdf", PNG_MAGIC).status_code == 415

    def test_unsupported_extension_returns_415(self, client_no_auth: TestClient) -> None:
        assert self._upload(client_no_auth, "malware.exe", PDF_MAGIC).status_code == 415

    def test_oversized_file_returns_413(self, client_no_auth: TestClient) -> None:
        from coi_form_digitization.infrastructure.config import get_settings
        from coi_form_digitization.presentation.app_factory import create_app
        from tests.conftest import _build_test_settings

        app = create_app()
        app.dependency_overrides[get_settings] = lambda: _build_test_settings(
            max_file_size_bytes=10, auth_required=False
        )
        tiny_client = TestClient(app, raise_server_exceptions=False)
        response = tiny_client.post(
            "/api/v1/forms/digitize",
            files={"file": ("form.pdf", io.BytesIO(b"\x00" * 11), "application/octet-stream")},
        )
        assert response.status_code == 413


class TestDigitizeExtractorsIntegration:
    """Representative integration tests: one per format + corrupt file 422."""

    def _upload(self, client: TestClient, filename: str, data: bytes, token: str):
        return client.post(
            "/api/v1/forms/digitize",
            files={"file": (filename, io.BytesIO(data), "application/octet-stream")},
            headers={"Authorization": f"Bearer {token}"},
        )

    def test_pdf_extraction_success(self, client: TestClient, valid_token: str) -> None:
        pdf_bytes = make_test_pdf_bytes(
            [
                "1. DANE WNIOSKODAWCY:",
                "PESEL: 90010112345",
                "Nazwisko: Kowalski",
                "[x] Tak   [ ] Nie",
            ]
        )
        res = self._upload(client, "form.pdf", pdf_bytes, valid_token)
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "success"
        definition = body["form_definition"]
        assert definition["title"]
        assert any(tab["type"] == "MAIN" for tab in definition["tabs"])
        assert definition["tabs"][-1]["type"] == "FINISH"
        assert len(definition["flow"]["links"]) == len(definition["tabs"]) - 1
        structured = body["structured_form"]
        assert structured["filename"] == "form.pdf"
        assert structured["total_fields"] >= 2
        assert structured["overall_confidence"] >= 0.0
        assert any(
            field["field_type"] == "pesel"
            for section in structured["sections"]
            for field in section["fields"]
        )
        extracted = body["extracted"]
        assert extracted["total_pages"] >= 1
        page = extracted["pages"][0]

        # Verify colon-ended line is classified as a heading, not an empty key-value
        assert "1. DANE WNIOSKODAWCY:" in page["headings"]

        # Verify key-values
        kv_keys = {kv["key"]: kv["value"] for kv in page["key_values"]}
        assert kv_keys.get("PESEL") == "90010112345"
        assert kv_keys.get("Nazwisko") == "Kowalski"

        # Verify multiple checkboxes on a single line (checked and unchecked)
        cb_dict = {cb["label"]: cb["is_checked"] for cb in page["checkboxes"]}
        assert cb_dict.get("Tak") is True
        assert cb_dict.get("Nie") is False

    def test_docx_extraction_success(self, client: TestClient, valid_token: str) -> None:
        docx_bytes = make_test_docx_bytes()
        res = self._upload(client, "wniosek.docx", docx_bytes, valid_token)
        assert res.status_code == 200
        extracted = res.json()["extracted"]
        assert len(extracted["pages"]) == 1
        page = extracted["pages"][0]

        # Verify checkboxes extracted from body paragraphs
        cb_dict = {cb["label"]: cb["is_checked"] for cb in page["checkboxes"]}
        assert cb_dict.get("Obywatel polski") is True
        assert cb_dict.get("Cudzoziemiec") is False

        # Verify table and key-values extracted from 2-column table rows
        assert len(page["tables"]) >= 1
        kv_dict = {kv["key"]: kv["value"] for kv in page["key_values"]}
        assert kv_dict.get("Nazwisko") == "Kowalski"
        assert kv_dict.get("Numer PESEL") == "90010112345"
        assert "[x] Tak" not in kv_dict
        assert "[ ] Nie" not in kv_dict

    def test_xlsx_extraction_success(self, client: TestClient, valid_token: str) -> None:
        xlsx_bytes = make_test_xlsx_bytes()
        res = self._upload(client, "tabela.xlsx", xlsx_bytes, valid_token)
        assert res.status_code == 200
        extracted = res.json()["extracted"]
        assert extracted["format"] == "xlsx"
        page = extracted["pages"][0]
        assert len(page["tables"]) >= 1
        kv_dict = {kv["key"]: kv["value"] for kv in page["key_values"]}
        assert kv_dict.get("PESEL") == "90010112345"
        assert kv_dict.get("Województwo") == "Mazowieckie"

    def test_ods_extraction_success(self, client: TestClient, valid_token: str) -> None:
        ods_bytes = make_test_ods_bytes()
        res = self._upload(client, "arkusz.ods", ods_bytes, valid_token)
        assert res.status_code == 200
        extracted = res.json()["extracted"]
        assert extracted["format"] == "ods"
        page = extracted["pages"][0]
        assert len(page["tables"]) >= 1
        kv_dict = {kv["key"]: kv["value"] for kv in page["key_values"]}
        assert kv_dict.get("PESEL") == "90010112345"

    def test_image_png_extraction_success(self, client: TestClient, valid_token: str) -> None:
        img_bytes = make_test_image_bytes("PNG", text="DOKUMENT")
        res = self._upload(client, "skan.png", img_bytes, valid_token)
        assert res.status_code == 200
        extracted = res.json()["extracted"]
        assert extracted["format"] == "png"
        assert extracted["total_pages"] == 1
        # RapidOCR should detect the drawn text
        page = extracted["pages"][0]
        assert any(
            "DOKUMENT" in line.upper()
            for line in [page["raw_text"]] + page["headings"] + page["paragraphs"]
        )

    def test_image_tiff_extraction_success(self, client: TestClient, valid_token: str) -> None:
        image_bytes = make_test_image_bytes("TIFF", text="DOKUMENT")
        response = self._upload(client, "skan.tiff", image_bytes, valid_token)
        assert response.status_code == 200
        assert response.json()["extracted"]["format"] == "tiff"

    def test_legacy_doc_extraction_with_mocked_soffice(self) -> None:
        """Test LegacyDocExtractor subprocess execution and profile isolation with mocked soffice."""
        docx_bytes = make_test_docx_bytes(title="Wniosek DOC")

        def fake_run(cmd, capture_output=True, timeout=30):
            # Assert -env:UserInstallation is passed in command
            user_inst = [arg for arg in cmd if arg.startswith("-env:UserInstallation=")]
            assert len(user_inst) == 1
            # Write a valid docx output file where soffice would place it
            out_dir = Path(cmd[cmd.index("--outdir") + 1])
            (out_dir / "input.docx").write_bytes(docx_bytes)
            mock_res = MagicMock()
            mock_res.returncode = 0
            return mock_res

        extractor = LegacyDocExtractor()
        with patch.object(extractor, "_find_soffice", return_value="/usr/bin/soffice"):
            extractor._soffice_cmd = "/usr/bin/soffice"
            with patch("subprocess.run", side_effect=fake_run):
                doc = extractor.extract("wniosek.doc", OLE2_MAGIC)
                assert doc.format == "doc"
                assert len(doc.pages) == 1
                assert "Wniosek DOC" in doc.pages[0].headings

    def test_corrupt_file_returns_422(self, client: TestClient, valid_token: str) -> None:
        # Valid PDF header magic so it passes security MIME validator, but invalid/truncated PDF syntax
        corrupt_pdf = b"%PDF-1.4\n%%EOF\nGARBAGE_CONTENT_CORRUPT"
        res = self._upload(client, "corrupt.pdf", corrupt_pdf, valid_token)
        assert res.status_code == 422
        assert "detail" in res.json()
