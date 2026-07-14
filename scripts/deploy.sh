#!/usr/bin/env bash
# Compatibility wrapper for the transactional Claude deployment runtime.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd -P)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: Python 3.9+ is required (python3)." >&2
    exit 1
fi

if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)'; then
    echo "Error: Python 3.9+ is required; found $(python3 --version 2>&1)." >&2
    exit 1
fi

export PYTHONPATH="$REPO_DIR${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONDONTWRITEBYTECODE=1
exec python3 -m scripts.harness_installer.claude --repo-root "$REPO_DIR" "$@"
