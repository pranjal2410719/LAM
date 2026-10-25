#!/bin/sh
set -e

echo "==> Running Alembic migrations..."
alembic upgrade head

echo "==> Starting LAM Uvicorn service on port ${PORT:-8000}..."
exec uvicorn lam.main:app --host 0.0.0.0 --port "${PORT:-8000}" --timeout-graceful-shutdown 15
