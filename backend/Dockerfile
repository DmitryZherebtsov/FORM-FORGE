FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TMPDIR=/tmp

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        libreoffice-writer \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src ./src

# RapidOCR's 1.4.4 metadata predates Python 3.14; the locked runtime is verified on 3.14.
RUN python -m pip install --ignore-requires-python --no-cache-dir . \
    && python -c "from rapidocr_onnxruntime import RapidOCR; RapidOCR()" \
    && useradd --create-home --uid 10001 appuser

USER appuser

EXPOSE 8000

CMD ["uvicorn", "coi_form_digitization.main:app", "--host", "0.0.0.0", "--port", "8000"]
