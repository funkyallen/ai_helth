#!/usr/bin/env bash
set -e

python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
