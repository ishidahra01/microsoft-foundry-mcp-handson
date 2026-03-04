#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# startup.sh — App Service startup script for webapp-foundry-oauth
#
# Runs both the FastAPI backend (port 8000) and the Next.js frontend (port
# $PORT, which App Service routes public traffic to) inside a single Linux
# App Service instance.
#
# App Service sets the PORT environment variable automatically (matching the
# value of WEBSITES_PORT, default 8080). The Next.js process listens on $PORT;
# the FastAPI process listens only on localhost:8000 (internal only).
#
# Usage (App Service "Startup Command" field):
#   /bin/bash /home/site/wwwroot/startup.sh
#
# Note: Python dependencies are installed on each startup for simplicity in
# this hands-on guide. For production workloads, pre-install dependencies in
# a custom Docker image or during a build/deployment step to reduce startup
# time.
# ─────────────────────────────────────────────────────────────────────────────
set -e

APP_ROOT="/home/site/wwwroot"

echo "=== webapp-foundry-oauth startup ==="

# ── Backend: FastAPI (uvicorn) ────────────────────────────────────────────────
echo "[backend] Installing Python dependencies..."
pip3 install --quiet --disable-pip-version-check \
    -r "${APP_ROOT}/backend/requirements.txt"

echo "[backend] Starting FastAPI on 127.0.0.1:8000 ..."
cd "${APP_ROOT}/backend"
uvicorn server:app \
    --host 127.0.0.1 \
    --port 8000 \
    --workers 1 \
    --log-level info &

# ── Frontend: Next.js ────────────────────────────────────────────────────────
# App Service sets the PORT environment variable (matching WEBSITES_PORT,
# default 8080). Next.js 14+ honours PORT automatically; we also pass it
# explicitly via -p to be safe.
echo "[frontend] Starting Next.js on port ${PORT:-8080} ..."
cd "${APP_ROOT}/frontend"
exec npm start -- -p "${PORT:-8080}"
