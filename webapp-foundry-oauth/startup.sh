#!/bin/bash
set -e

APP_ROOT="/home/site/wwwroot"
PORT="${PORT:-8080}"

echo "=== webapp-foundry-oauth startup ==="
echo "[backend] Installing Python dependencies..."
python -m pip install --quiet --disable-pip-version-check -r "${APP_ROOT}/backend/requirements.txt"

echo "[backend] Starting FastAPI on 0.0.0.0:${PORT} ..."
cd "${APP_ROOT}/backend"
exec python -m uvicorn server:app --host 0.0.0.0 --port "${PORT}" --workers 1 --log-level info