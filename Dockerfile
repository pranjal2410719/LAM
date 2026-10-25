# Multi-stage production Dockerfile for LAM service
FROM python:3.11-slim-bookworm AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install uv for fast, deterministic dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Final runtime image
FROM python:3.11-slim-bookworm AS runner

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/src" \
    PORT=8000 \
    HOST=0.0.0.0

# Run as non-privileged service user
RUN groupadd -g 10001 lam && \
    useradd -u 10001 -g lam -s /bin/bash -m lamuser

COPY --from=builder /app/.venv /app/.venv
COPY pyproject.toml alembic.ini start.sh ./
COPY alembic ./alembic
COPY src ./src

RUN chmod +x /app/start.sh && chown -R lamuser:lam /app

USER lamuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python3 -c "import os, urllib.request, sys; port=os.getenv('PORT', '8000'); sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{port}/health/live', timeout=4).getcode() == 200 else 1)"

CMD ["/app/start.sh"]
