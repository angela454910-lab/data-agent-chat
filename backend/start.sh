#!/bin/bash
cd "$(dirname "$0")"
source .env 2>/dev/null || true

# Build frontend if dist doesn't exist
if [ ! -d "../web/dist" ]; then
  echo "Building frontend..."
  (cd ../web && npm run build)
fi

echo "Starting Data Agent Chat on http://127.0.0.1:3009"
uv run python -m uvicorn app.main:app --host 127.0.0.1 --port 3009 --reload
