# syntax=docker/dockerfile:1

# ---------- Stage 1: Builder ----------
FROM python:3.12-alpine AS builder

COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Install build dependencies for compiling any C extensions if needed
RUN apk add --no-cache build-base libffi-dev

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# ---------- Stage 2: Runtime ----------
FROM python:3.12-alpine AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Create unprivileged user for secure execution
RUN addgroup -g 1000 appgroup && \
    adduser -u 1000 -G appgroup -s /bin/sh -D appuser && \
    mkdir -p /app/data && chown -R appuser:appgroup /app

COPY --from=builder /app/.venv /app/.venv
COPY --chown=appuser:appgroup app ./app
COPY --chown=appuser:appgroup simulators ./simulators
COPY --chown=appuser:appgroup pyproject.toml ./

USER appuser

EXPOSE 8005 8006 8007

# Runs the 3 Carrier HTTP servers (8005, 8006, 8007) + background 4h scheduler
CMD ["python", "-m", "simulators.type_c.server"]
