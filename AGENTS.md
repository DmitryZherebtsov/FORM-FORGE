# AGENTS.md — Repository Engineering & AI Rules

## 1. Context & Documentation Protocol
- Before writing code, read `_documentation/00_INDEX.md` and open **only** the specific documentation files required for your current task.
- Do not load unrelated files or invent requirements outside `_documentation/`.
- When official COI sample schemas or dictionaries are added to `knowledge_base/`, treat them as the source of truth for output structure.

## 2. Hard Compliance Rules (COI HackNation 2026)
- **Zero External Runtime Dependencies:** Never call external APIs, cloud LLMs, MCP servers, or SaaS services at runtime. All processing must run offline inside the container.
- **Strict License Policy:** Use **only** permissive open-source licenses (`MIT`, `Apache-2.0`, `BSD-2-Clause`, `BSD-3-Clause`, `ISC`, `MPL-2.0`). Never add dependencies licensed under `GPL`, `AGPL`, `LGPL` (unless dynamically linked and verified), or commercial terms.
- **Ephemeral Memory Processing:** Process uploaded files strictly in RAM (`BytesIO` / `tmpfs`). Never persist uploaded user documents to disk.
- **Input Security:** Enforce extension + real MIME-type matching, filename length `<= 250`, forbidden filename characters `; : > < / \ | ' * % $`, and configurable max upload size.

## 3. Architecture & Code Quality Standards
- **Principles:** Strictly follow **Clean Architecture**, **SOLID**, **OOP**, **GRASP**, **DRY**, **KISS**, and **YAGNI**.
- **Backend (`backend/`):** Python 3.14+. Enforce inward dependency flow (`domain` <- `application` <- `infrastructure` & `presentation`). Keep `domain` free of FastAPI, Pydantic HTTP DTOs, and I/O libraries.
- **Frontend (`frontend/`):** React + TypeScript + Vite following **MVVM** (`models/`, `viewmodels/` with Zustand, `views/`). Keep UI components purely presentational; isolate business/form-rule logic in ViewModels. Follow **Material 3** (tonal surface hierarchy, M3 color roles, shape tokens, elevation, state layers, accessible typography) and responsive/adaptive layout. UI packages must be **MIT** or **Apache-2.0** only: Tailwind CSS with M3 design tokens, or `@mui/material`.
- **No Over-Engineering:** Build clean, extensible abstractions only where variation exists (document extractors, AI engine providers, output schema mappers).

## 4. Commenting & Anti-Slop Rules
- Write self-explanatory code through precise naming and strict static typing (Python type hints, TypeScript `strict: true`).
- **Comments:** Keep comments minimal, concise, and in **English**. Write comments **only** to explain *why* (non-obvious domain rules, security constraints, edge cases) — never narrate *what* the code does.
- **Docstrings:** Add brief, single-purpose docstrings only on public interfaces, domain services, and non-trivial algorithms. Never write multi-paragraph prose or boilerplate headers.

## 5. Testing Policy (Critical Paths Only)
Write tests **only** for logic where a bug causes a security breach, data corruption, or a broken API contract. Everything else is noise.

**Write tests for:**
- Security enforcement: MIME/magic-byte spoofing, filename length/character rules, payload size limits, JWT issuance and rejection.
- Domain algorithms with legal or financial impact: PESEL/NIP checksums, Polish validator logic.
- Core API contracts: status codes and response shapes for `/health`, `/auth/token`, and `/forms/digitize` (happy path + each distinct failure mode exactly once).

**Strictly forbidden:**
- Exhaustive permutation tests over simple constants (e.g., testing every forbidden character individually when one representative sample already covers the code path).
- Tests that only verify framework defaults, config field names, or DTO field presence.
- Duplicate coverage of the same code path under slightly different names.
- Any test whose failure would not indicate a real defect in business or security logic.

Keep the full suite runnable in under 2 seconds. Every test must earn its place.

## 6. Git Commit Convention
Use a plain, concise English title — one line, no emoji, no conventional-commit prefixes (`feat:`, `chore:`, `fix:`). Optionally follow with a blank line and a short bullet list naming the key changes (3–6 bullets max).

**Forbidden:** long explanations, multi-sentence prose, essays, marketing copy, or restating the diff in paragraph form.