#!/usr/bin/env bash
# =============================================================================
# InsureFlow AI — Container Entrypoint
# =============================================================================
set -e

echo "[entrypoint] Starting InsureFlow AI..."
echo "[entrypoint] Launching Uvicorn on port ${PORT:-8080}..."

exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8080}" \
    --workers 1 \
    --http h11 \
    --log-level "${LOG_LEVEL:-info}"
