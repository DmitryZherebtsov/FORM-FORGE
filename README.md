# COI Form Digitization

A local API and web workspace for converting public administration forms into editable structured JSON.

## Quick Start

- macOS/Linux: `./start.sh`
- Windows: `start.bat`
- Docker Compose: `./start.sh --docker` or `start.bat --docker`
- Run backend and frontend checks: `./start.sh --test` or `start.bat --test`

The local launcher creates `.env` with fresh development secrets when needed, installs missing dependencies, starts both services, prints a JWT, and opens the web workspace.

## Supported formats

PDF, DOCX, legacy DOC, XLSX, ODS, PNG, JPG/JPEG/JPE, and TIFF.

## Runtime

Uploads are processed in memory. Deterministic structuring is the default and makes no outbound network requests. Optional LLM structuring uses a self-hosted local inference server, such as Ollama, with an open-weights model. The default model is Bielik-11B-v3.0-Instruct. Extracted form structure is sent only to the configured `AI_BASE_URL`; deterministic Polish validators always run after model refinement. Commercial cloud OpenAI APIs are not used.

## Run with Docker Compose

```sh
cp _documentation/.env.example .env
# Replace the development JWT and demo keys before deployment.
docker compose up --build -d
```

Open [http://localhost:8080](http://localhost:8080). The default upload limit is 20 MiB.

The token endpoint expects the `DEMO_ACCESS_KEY` from `.env`:

```sh
curl -X POST http://localhost:8080/api/v1/auth/token \
  -H 'Content-Type: application/json' \
  -d '{"access_key":"<DEMO_ACCESS_KEY>"}'
```

Use the returned `access_token` for digitization and warm-up:

```sh
curl -X POST http://localhost:8080/api/v1/forms/digitize \
  -H 'Authorization: Bearer <TOKEN>' \
  -F 'file=@wniosek.pdf'

curl -X POST http://localhost:8080/api/v1/llm/warmup \
  -H 'Authorization: Bearer <TOKEN>'
```

## Optional local LLM

Set `ENABLE_LLM=true` and `AI_BASE_URL` in `.env` for a self-hosted OpenAI-compatible endpoint. For Ollama running on the Docker host, use `http://host.docker.internal:11434`; for a service on the same Compose network, use its service URL, such as `http://ollama:11434`. Set `AI_MODEL_NAME` to the locally served model. The default is `hf.co/speakleash/Bielik-11B-v3.0-Instruct-GGUF:Q4_K_M`. `AI_TIMEOUT_SECONDS` defaults to `90`. Recreate the backend service after changing these values.

`GET /api/v1/health` reports LLM configuration and reachability. The warm-up request checks the endpoint and sends a one-token completion. Failed or malformed model responses fall back to deterministic structuring.

## Local development

Backend:

```sh
cd backend
uv sync
uv run ruff check src tests
uv run pytest
uv run uvicorn coi_form_digitization.main:app --reload --host 0.0.0.0 --port 8000
```

Frontend, in a second terminal:

```sh
cd frontend
npm ci
npm run dev
npx tsc --noEmit
npm run build
```

## Configuration

| Variable | Purpose |
| --- | --- |
| `JWT_SECRET_KEY` | JWT signing key |
| `DEMO_ACCESS_KEY` | Key for the demo token endpoint |
| `MAX_UPLOAD_SIZE_BYTES` | Upload limit in bytes; defaults to 20 MiB |
| `CORS_ORIGINS` | JSON list of allowed origins; defaults to `[]` |
| `FRONTEND_PORT` | Host port; defaults to `8080` |
| `ENABLE_LLM` | Enables local LLM structuring; defaults to `false` |
| `AI_PROVIDER` | `heuristic` or `openai_compat`; defaults to `openai_compat` |
| `AI_BASE_URL` | Self-hosted inference URL; blank disables LLM requests |
| `AI_MODEL_NAME` | Served model name; defaults to Bielik-11B-v3.0-Instruct GGUF Q4_K_M |
| `AI_TIMEOUT_SECONDS` | LLM response timeout; defaults to `90` seconds |
