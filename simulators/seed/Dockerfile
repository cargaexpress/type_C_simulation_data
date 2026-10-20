# syntax=docker/dockerfile:1

# ---------- Stage 1: builder ----------
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# ---------- Stage 2: runtime ----------
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

RUN useradd --create-home --uid 1000 seeduser

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --chown=seeduser:seeduser app ./app
COPY --chown=seeduser:seeduser simulators ./simulators

USER seeduser

CMD ["python", "-m", "simulators.seed"]
