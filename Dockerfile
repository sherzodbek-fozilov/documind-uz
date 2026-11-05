# API image: FastAPI + uvicorn, tesseract with uzb, uzb_cyrl and rus, non-root user.
# No secrets are baked in: settings come from the environment at run time (see
# docker-compose.yml and .env.example); .env is excluded by .dockerignore.
#
#   docker build -t documind-api .
#
# The same image runs the one-off jobs on a server (download the model, fetch the
# lex.uz documents, ingest); see docs/deploy.md.

FROM python:3.12-slim-trixie AS build
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /src
RUN python -m venv /venv
COPY pyproject.toml README.md ./
COPY documind ./documind
# api: FastAPI + uvicorn; models: huggingface_hub for scripts/download_model.py
RUN /venv/bin/pip install ".[api,models]"

FROM python:3.12-slim-trixie
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      tesseract-ocr tesseract-ocr-uzb tesseract-ocr-uzb-cyrl tesseract-ocr-rus \
 && rm -rf /var/lib/apt/lists/* \
 && tesseract --list-langs | grep -qx uzb_cyrl
RUN groupadd --system --gid 10001 documind \
 && useradd --system --uid 10001 --gid documind --home-dir /app --shell /usr/sbin/nologin \
      documind
COPY --from=build /venv /venv
ENV PATH=/venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
# code and committed data stay owned by root (read-only for the service user)
COPY scripts ./scripts
COPY data/sources.json data/splits.json ./data/
# writable directories; named volumes mounted here take over this ownership
RUN mkdir -p models data/raw data/store data/cache data/user_store \
 && chown documind:documind models data/raw data/store data/cache data/user_store
USER documind
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"]
CMD ["uvicorn", "documind.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
