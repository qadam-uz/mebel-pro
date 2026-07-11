# syntax=docker/dockerfile:1

# --- builder: resolve & install deps into the system interpreter -------------
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.8.22 /uv /uvx /bin/

# Deps go into the system interpreter (/usr/local), not a .venv under /app —
# the container is the isolation. Keeping site-packages out of /app means the
# dev source bind-mount (deploy/compose.yaml) can never shadow installed
# dependencies, so no venv-preserving volume is needed.
ENV UV_PROJECT_ENVIRONMENT=/usr/local \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

# Deps only — the project is `package = false`, so nothing of it is installed.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    uv sync --frozen --no-install-project --no-dev

COPY . /app

# --- runtime -----------------------------------------------------------------
FROM python:3.12-slim AS runtime

RUN useradd --create-home --uid 1000 app
WORKDIR /app

# Same base image, so overlaying /usr/local transplants site-packages and the
# console scripts (uvicorn, fastapi, alembic) verbatim; they're on PATH already.
COPY --from=builder /usr/local /usr/local
COPY --from=builder --chown=app:app /app /app
ENV PYTHONUNBUFFERED=1

USER app
EXPOSE 8000

# Run migrations then start the server. Override CMD in compose for dev.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
