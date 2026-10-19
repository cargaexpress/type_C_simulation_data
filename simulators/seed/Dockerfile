FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /usr/local/bin/uv

WORKDIR /app

COPY backend/pyproject.toml backend/uv.lock ./
# The dev group includes openpyxl imported by the seed package initializer.
RUN uv sync --frozen --no-install-project --group dev

COPY backend/app ./app
COPY simulators ./simulators

ENV PATH="/app/.venv/bin:$PATH"

RUN useradd --create-home --uid 1000 seeduser \
    && chown -R seeduser:seeduser /app

USER seeduser

CMD ["python", "-m", "simulators.seed"]
