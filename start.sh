#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
exec uv run --project backend python scripts/run.py "$@"
