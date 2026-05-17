#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

HOST="${NEXUS_HOST:-127.0.0.1}"
PORT="${NEXUS_PORT:-8765}"

PYTHONPATH="${PYTHONPATH:-src}" python3 -m nexus_backend.main serve --host "$HOST" --port "$PORT"
