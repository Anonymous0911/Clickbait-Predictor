FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings \
    HF_HOME=/data/hf

RUN groupadd --gid 1000 app \
    && useradd --uid 1000 --gid 1000 --create-home app \
    && mkdir -p /data/media /data/hf /opt/venv /app/backend \
    && chown app:app /data/media /data/hf /opt/venv /app /app/backend

USER app
WORKDIR /app/backend

# Lockfile only, so code changes don't invalidate the dependency layer.
# Installed as app so no chown layer duplicates the venv; --no-cache keeps uv's cache out of the image.
COPY --chown=app:app backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-install-project --no-cache

COPY --chown=app:app . /app
