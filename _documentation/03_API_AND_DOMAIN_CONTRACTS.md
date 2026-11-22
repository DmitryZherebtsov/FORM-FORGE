# API and Domain Contracts

All endpoints use the `/api/v1` prefix. Authentication is required for digitization and LLM warm-up when `AUTH_REQUIRED=true` (the default). The token endpoint checks `DEMO_ACCESS_KEY` and returns a signed bearer token.

## Endpoints

| Method and path | Access | Contract |
| --- | --- | --- |
| `GET /api/v1/health` | Public | `HealthResponseDTO`: `status`, `ai_provider`, `service`, `version`, `llm_enabled`, `ai_model`, `llm_status`. Refreshes configured inference endpoint readiness when LLM is enabled. |
| `POST /api/v1/auth/token` | Public | JSON request `{"access_key": string}`; response `TokenResponseDTO`: `access_token`, `token_type`. Invalid keys return 401. |
| `POST /api/v1/forms/digitize` | Bearer token if enabled | Multipart form field `file`; returns `DigitizeResponseDTO`. |
| `POST /api/v1/llm/warmup` | Bearer token if enabled | Returns `LlmWarmupResponseDTO` with status, model, latency, and optional detail. |

Digitization error statuses are 400 for filename rules, 401 for authentication, 413 for upload size, 415 for unsupported extension or MIME mismatch, and 422 for unreadable or invalid documents. Error bodies contain `detail`.

## Digitization response

`DigitizeResponseDTO` contains `status`, `filename`, `extension`, `size_bytes`, `detected_mime`, `extracted`, `structured_form`, `form_definition`, and `structuring_mode` (`heuristic`, `llm`, or `heuristic_fallback`).

`extracted` is an `ExtractedDocumentDTO`: `filename`, `format`, `total_pages`, `pages`, and `metadata`. Each page contains `page_number`, `headings`, `paragraphs`, `key_values`, `tables`, `checkboxes`, and `raw_text`. Key-value pairs contain `key`, `value`, and `confidence`; tables contain `headers`, `rows`, and optional `title`; checkboxes contain `label`, `is_checked`, and optional `context`.

`structured_form` is a `StructuredFormDTO`: `filename`, `format`, optional `form_title`, `sections`, `total_fields`, `fields_needing_review`, and `overall_confidence`. Sections contain `section_id`, `title`, `order`, `fields`, `choice_groups`, and `tables`. Fields contain `field_id`, `label`, `field_type`, `value`, `is_valid`, optional `validation_error`, `confidence`, and `needs_review`. Choice groups contain `group_id`, optional `label`, `selection_type`, `options`, and `needs_review`; each option contains `label` and `is_selected`.

## FormDefinition wire schema

The mapper returns `FormDefinitionDTO` with `title`, `tabs`, and `flow`. Pydantic serialization uses camelCase aliases for these nested fields:

- Tabs: `id`, `title`, `type` (`MAIN` or `FINISH`), and `questions`.
- Questions: `x`, `y`, `rows`, `cols`, and `field`.
- Fields: `id`, `type`, `techName`, `title`, `description`, `options`, `validation`, optional `dictionaryName`, `readOnly`, `repeatingSectionGrid`, optional `defaultValue`, optional `defaultValueType`, optional `consentSectionConfig`, `states`, `questionOrder`, `tooltipMessage`, and optional `multiLevelTree` and `searchEnabled`.
- Options: `id`, `name`, `techName`.
- States: `type` (`SHOW` or `READ_ONLY`) and `query`.
- Consent config: `consents` and `files`; consent items contain `description` and `required`.
- Flow: `links`, each with `id`, `source`, and `target`.

The frontend export filename is `konfiguracja_form_<slug>.json`.

## Runtime settings

Values are loaded by `Settings` from environment variables and the repository-root `.env`. The table lists supported environment names, aliases, and defaults from `Settings`, Docker Compose, and `_documentation/.env.example`.

| Setting | Default | Purpose |
| --- | --- | --- |
| `APP_PORT` | `8000` | Backend port. |
| `MAX_UPLOAD_SIZE_BYTES` / `MAX_FILE_SIZE_BYTES` | `20971520` | Maximum upload size in bytes (20 MiB). |
| `AUTH_REQUIRED` | `true` | Enables bearer authentication checks. |
| `JWT_SECRET_KEY` / `JWT_SECRET` | `CHANGE_ME_IN_PRODUCTION` | JWT signing secret. |
| `JWT_ALGORITHM` | `HS256` | JWT signing and verification algorithm. |
| `CORS_ORIGINS` | `[]` | Allowed origins; configured as a list. |
| `DEMO_ACCESS_KEY` | `demo-key-change-me` | Key accepted by the demo token endpoint. |
| `ENABLE_LLM` | `false` | Enables optional inference requests. |
| `AI_PROVIDER` | `openai_compat` | Accepted values: `heuristic`, `openai_compat`. |
| `AI_BASE_URL` | empty | Configured self-hosted compatible endpoint. |
| `AI_MODEL_NAME` | `hf.co/speakleash/Bielik-11B-v3.0-Instruct-GGUF:Q4_K_M` | Model identifier sent to the endpoint. |
| `AI_TIMEOUT_SECONDS` | `90` | Inference request timeout; connect timeout is 5 seconds. |
| `AI_MODEL_PATH` | empty | Present in settings; not used by the current structurer. |
| `KNOWLEDGE_BASE_DIR` | `/app/knowledge_base` | Present in settings; no knowledge-base directory or reader is included in the repository. |
| `FRONTEND_PORT` | `8080` | Docker Compose host port for the frontend; not a backend `Settings` field. |
