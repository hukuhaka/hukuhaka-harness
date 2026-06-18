#!/usr/bin/env bash
# init.sh — create .claude/ with 5 template files
# Existing files are preserved (reported as such); --force overwrites them.
# Usage: bash init.sh [--force] [target_dir]   (default: .claude)
set -euo pipefail

FORCE=0
if [ "${1:-}" = "--force" ]; then
    FORCE=1
    shift
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATES_DIR="$SCRIPT_DIR/templates"
TARGET_DIR="${1:-.claude}"

if [ ! -d "$TEMPLATES_DIR" ]; then
    echo "ERROR: templates directory not found: $TEMPLATES_DIR" >&2
    exit 1
fi

mkdir -p "$TARGET_DIR"

files=(map.md design.md backlog.md changelog.md spec.md)
created=()
preserved=()
for f in "${files[@]}"; do
    src="$TEMPLATES_DIR/$f"
    dst="$TARGET_DIR/$f"
    if [ ! -f "$src" ]; then
        echo "ERROR: template missing: $src" >&2
        exit 1
    fi
    if [ -f "$dst" ] && [ "$FORCE" -ne 1 ]; then
        preserved+=("$f")
        continue
    fi
    cp "$src" "$dst"
    created+=("$f")
done

echo "Init complete — $TARGET_DIR/ ready (${#created[@]} created, ${#preserved[@]} preserved)."
for f in ${created[@]+"${created[@]}"}; do
    echo "  created   - $TARGET_DIR/$f"
done
for f in ${preserved[@]+"${preserved[@]}"}; do
    echo "  preserved - $TARGET_DIR/$f (already exists; use --force to overwrite)"
done
echo ""
echo "Run \`/hukuhaka-project-mapper:map-spec generate\` to fill spec.md with project rules."
