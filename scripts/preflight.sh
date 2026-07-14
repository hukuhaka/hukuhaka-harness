#!/usr/bin/env bash
# Compatibility wrapper for the structured dependency scanner.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd -P)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

if ! command -v python3 >/dev/null 2>&1 || \
   ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1; then
    cat <<'JSON'
{
  "summary": {"missing_required": 1, "missing_optional": 0, "ok": 0},
  "requirements": [
    {"name": "python3", "kind": "system", "required": true, "found": false,
     "needed_by": ["installer runtime"]}
  ]
}
JSON
    exit 1
fi

export PYTHONPATH="$REPO_DIR${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONDONTWRITEBYTECODE=1
exec python3 -m scripts.harness_installer.preflight "$@"
