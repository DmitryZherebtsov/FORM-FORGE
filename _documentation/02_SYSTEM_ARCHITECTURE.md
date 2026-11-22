# System Architecture

## Backend

The Python service uses four source layers under `backend/src/coi_form_digitization/`:

- `domain/`: extracted-document, structured-form, and COI form-definition models; exceptions; and ports. It has no FastAPI or I/O dependencies.
- `application/`: DTOs for API requests and responses.
- `infrastructure/`: `Settings`, JWT service, upload validation, format extractors, structurers, and the COI mapper.
- `presentation/`: FastAPI app factory, dependencies, exception handlers, and routers.

`POST /api/v1/forms/digitize` reads the upload, validates it, extracts document content, structures fields, maps a `FormDefinition`, and returns all three representations.

`CompositeDocumentExtractor` selects an extractor by extension:

- `PdfExtractor` reads PDF text and tables and invokes OCR for pages with little extractable text.
- `DocxExtractor` reads paragraphs, tables, form labels, and `w:txbxContent` textboxes from DOCX.
- `LegacyDocExtractor` converts DOC to DOCX using headless LibreOffice in a temporary directory, then delegates to `DocxExtractor`.
- `SpreadsheetExtractor` handles XLSX and ODS.
- `ImageOcrExtractor` uses bundled RapidOCR models for PNG, JPEG-family images, and TIFF.

`DeterministicFormStructurer` derives sections, fields, choices, and local validation results. `OpenAICompatFormStructurer` always starts with the deterministic result. When enabled, it sends extracted text and the structured summary to the configured inference endpoint for label, title, field-type, and choice-group refinement. It accepts only refinements keyed by existing IDs, protects sensitive field types, revalidates fields, and falls back to the deterministic result on errors (`structuring_mode: "heuristic_fallback"`). `DeterministicFormDefinitionMapper` builds COI tabs, fields, dictionaries-as-names, consent sections, `SHOW` states, and flow links.

## Frontend

The React application is implemented in `frontend/src/`:

- `App.tsx` holds upload, response, health, and token state.
- `TopBar.tsx` exposes health, model warm-up, and token controls.
- `FileUploadZone.tsx` selects and submits a document.
- `DocumentPreview.tsx` previews the selected source file.
- `ExtractedDataWorkspace.tsx` displays and edits extracted and structured content.
- `StructuredFormReview.tsx` presents structured fields for review.
- `FormDefinitionPreview.tsx` renders the generated COI form.
- `utils/coiFormPreview.ts` serializes and downloads the definition and evaluates the mapper's supported `SHOW` query pattern. It is a constrained evaluator, not a general JSONata engine.

The JWT is held in React state in memory. The app can read it from the URL fragment or `VITE_DEV_TOKEN`; it removes a `#token=` fragment from browser history after reading it. No persistent browser storage is used.

## Deployment and inference

The production target is self-hosted institutional infrastructure. With `ENABLE_LLM=false`, extraction, structuring, validation, and mapping run locally without inference network requests. Docker Compose configures a read-only backend root filesystem and a `/tmp` `tmpfs`; the backend serves port 8000 inside the Compose network and the frontend is exposed on host port 8080 by default. Air-gapped operation requires locally available images, packages, and OCR model files.

The optional inference integration uses the open `/v1/chat/completions` HTTP JSON protocol. `AI_PROVIDER=openai_compat` names this protocol; the application has no commercial OpenAI API endpoint or OpenAI SDK integration. It sends requests to the configured `AI_BASE_URL`, so the deployment must point it to a self-hosted endpoint to keep inference traffic on-premise. The default Compose settings leave LLM requests disabled. When enabled, the request includes extracted document text. Configure an internal Ollama, vLLM, or llama.cpp service, or leave `ENABLE_LLM=false` for deterministic CPU processing.

For a temporary GPU demonstration, `scripts/google_colab_run.py` installs Ollama and Cloudflare Tunnel in Colab, attempts to pull `Bielik-11B-v3.0-Instruct-GGUF:Q4_K_M`, falls back to `qwen2.5:7b`, and prints an HTTPS `trycloudflare.com` URL. The corresponding Colab notebook is [available here](https://colab.research.google.com/drive/1fJGLzy5s9LYxDSbVbDGmsDcKVupS00IZ). This demonstration exposes the Colab Ollama endpoint through a public tunnel; it is separate from the self-hosted deployment model.

The LLM timeout defaults to 90 seconds with a 5-second connect timeout. Health checks use shorter timeouts. Model failures, malformed replies, and unsupported refinements use deterministic fallback.

## Launchers

- `scripts/run.py` bootstraps local development, runs the Docker Compose stack, or runs checks with `--test`.
- `start.sh` and `start.bat` invoke `scripts/run.py` through `uv`.
- `docker-compose.yml` builds and runs backend and frontend services; `backend/Dockerfile` and `frontend/Dockerfile` define their images.
