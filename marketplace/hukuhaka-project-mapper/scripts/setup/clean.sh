#!/usr/bin/env bash
# clean.sh — remove map-sync-managed CLAUDE.md from subdirectories (root preserved)
# Deletes ONLY files containing the managed-by marker; hand-written CLAUDE.md
# (and anything under hidden dirs / node_modules) is never touched.
# Usage: bash clean.sh [search_dir]   (default: .)
set -euo pipefail

SEARCH_DIR="${1:-.}"

# Root-sanity guard: refuse to walk a directory that doesn't look like a
# project root (e.g. accidentally run from $HOME).
if [ ! -e "$SEARCH_DIR/.claude" ] && [ ! -e "$SEARCH_DIR/.git" ]; then
    echo "ERROR: $SEARCH_DIR has no .claude/ or .git/ — not a project root. Refusing to walk it." >&2
    exit 1
fi

ROOT_FILE="$(cd "$SEARCH_DIR" && pwd)/CLAUDE.md"
MARKER="<!-- managed by map-sync -->"

targets=()
while IFS= read -r f; do
    abs="$(cd "$(dirname "$f")" && pwd)/$(basename "$f")"
    if [ "$abs" = "$ROOT_FILE" ]; then
        continue
    fi
    if ! grep -qF "$MARKER" "$f" 2>/dev/null; then
        continue
    fi
    targets+=("$f")
done < <(find "$SEARCH_DIR" -mindepth 1 \( -type d \( -name '.*' -o -name node_modules \) -prune \) -o -name "CLAUDE.md" -type f -print 2>/dev/null)

count=${#targets[@]}
if [ "$count" -eq 0 ]; then
    echo "Clean complete — no map-sync-managed CLAUDE.md files found."
    exit 0
fi

echo "Deleting $count map-sync-managed CLAUDE.md file(s):"
for f in ${targets[@]+"${targets[@]}"}; do
    echo "  - $f"
done
for f in ${targets[@]+"${targets[@]}"}; do
    rm "$f"
done
echo "Clean complete — deleted $count file(s)."
