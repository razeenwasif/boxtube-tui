#!/usr/bin/env bash
# Launch BoxTube using the project virtualenv.
set -euo pipefail
cd "$(dirname "$0")"
exec .venv/bin/python -m boxtube "$@"
