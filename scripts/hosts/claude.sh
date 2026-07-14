#!/usr/bin/env bash
# Claude Code host adapter. Keeps the established manifest deployment intact.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$SCRIPT_DIR/../deploy.sh" "$@"
