# syntax=docker/dockerfile:1

# ---- base: uv + Python, dependencies resolved from uv.lock -------------------------------
FROM python:3.12-slim-trixie AS base

COPY --from=ghcr.io/astral-sh/uv:0.11.6 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    DATA_DIR=/app/data

WORKDIR /app

# Install third-party dependencies first so this layer is cached across code changes.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

COPY README.md ./
COPY src ./src
COPY data ./data

# ---- dev: adds test/lint tooling; used by docker compose ---------------------------------
FROM base AS dev
COPY tests ./tests
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen
CMD ["pytest"]

# ---- runtime: production dependencies only -----------------------------------------------
FROM base AS runtime
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev
CMD ["python", "-c", "import triage; print('triage installed')"]
