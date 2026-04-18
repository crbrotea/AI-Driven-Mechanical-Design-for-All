# syntax=docker/dockerfile:1.7

FROM python:3.11-slim AS builder

RUN pip install --no-cache-dir uv==0.5.0

WORKDIR /app

COPY pyproject.toml ./
RUN uv sync --no-dev --frozen || uv sync --no-dev

COPY services ./services
COPY prompts ./prompts
COPY data ./data
COPY main.py ./

FROM python:3.11-slim AS runtime

RUN useradd --create-home --shell /bin/bash app
WORKDIR /app

COPY --from=builder --chown=app:app /app /app
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

USER app
EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
