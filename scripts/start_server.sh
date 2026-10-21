#!/usr/bin/env bash
# Quickstart script for StackDoc FastAPI Backend
set -e

PORT="${PORT:-8000}"
HOST="${HOST:-0.0.0.0}"

echo "=========================================================="
echo " Starting StackDoc Layout-Aware Document AI Backend"
echo " Sponsored by: Build with Stack (https://buildwithstack.com)"
echo " Repository:   https://github.com/anything14907-byte"
echo " Host:         http://${HOST}:${PORT}"
echo "=========================================================="

python3 -m uvicorn backend.app:app --host "${HOST}" --port "${PORT}" --reload
