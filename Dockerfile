# -- UI build --
FROM node:22-slim AS ui
WORKDIR /build
COPY ui/package.json ui/package-lock.json ./
RUN npm ci
COPY ui/ .
RUN npm run build

# -- App --
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Writable workspace for claude agent sdk
RUN mkdir -p /tmp/deep-review-workspace /tmp/deep-review-uploads \
    && chmod 777 /tmp/deep-review-workspace /tmp/deep-review-uploads

WORKDIR /app

# Install deps first (cache-friendly)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# App source
COPY agent/ agent/
COPY prompts/ prompts/
COPY app.py app_models.py models.py telemetry.py utils.py ./

# Built UI
COPY --from=ui /build/dist ui/dist/

ENV HOME=/tmp
EXPOSE 8000
CMD ["sh", "-c", "uv run uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
