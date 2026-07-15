#!/usr/bin/env bash
# Quick local dev bring-up without Docker (assumes Postgres already
# running locally and backend/.env pointing at it).
set -e
cd "$(dirname "$0")/.."

echo "Starting backend..."
(cd backend && PYTHONPATH=. uvicorn app.main:app --reload --port 8000) &
BACKEND_PID=$!

echo "Starting frontend..."
(cd frontend && npm run dev) &
FRONTEND_PID=$!

trap "kill $BACKEND_PID $FRONTEND_PID" EXIT
wait
