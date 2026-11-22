# Documentation Index

## Documentation

- `01_COI_REQUIREMENTS.md`: Supported uploads, validation and security behavior, Polish field rules, and `FormDefinition` mapping.
- `02_SYSTEM_ARCHITECTURE.md`: Backend and frontend components, inference options, and launch/deployment paths.
- `03_API_AND_DOMAIN_CONTRACTS.md`: REST endpoints, wire schemas, and runtime configuration.

## Repository

- `backend/`: Python 3.14+ FastAPI service, domain models, use cases, extractors, structurers, mapper, and tests.
- `frontend/`: React + TypeScript + Vite web application.
- `scripts/`: `run.py` developer launcher and `google_colab_run.py` temporary inference demonstration helper.
- `docker-compose.yml`: Backend and frontend container deployment.
- `start.sh`, `start.bat`: Unix and Windows wrappers for `scripts/run.py`.
- `_documentation/`: Current system documentation and separately maintained reference material.
- `README.md`: Quick start, runtime configuration, API examples, and development commands.
