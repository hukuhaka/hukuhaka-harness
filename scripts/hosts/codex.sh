#!/usr/bin/env bash
# Codex host adapter. Uses Codex's native marketplace and plugin lifecycle.
set -euo pipefail

COMPONENTS=""
MARKETPLACE_SOURCE="hukuhaka/hukuhaka-harness"
MARKETPLACE_NAME="hukuhaka-harness"
VERSION=""
VERSION_EXPLICIT=false
DRY_RUN=false
LOCAL_SOURCE=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --components) COMPONENTS="$2"; shift 2 ;;
        --marketplace-source) MARKETPLACE_SOURCE="$2"; shift 2 ;;
        --marketplace-name) MARKETPLACE_NAME="$2"; shift 2 ;;
        --version) VERSION="$2"; shift 2 ;;
        --version-explicit) VERSION_EXPLICIT=true; shift ;;
        --local-source) LOCAL_SOURCE=true; shift ;;
        --dry-run) DRY_RUN=true; shift ;;
        -h|--help)
            echo "Usage: $0 --components a,b [--marketplace-source SOURCE] [--version VERSION] [--dry-run]"
            exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 2 ;;
    esac
done

[ -n "$COMPONENTS" ] || exit 0

if $DRY_RUN; then
    echo "Codex deploy:"
    echo "  [dry-run] marketplace add $MARKETPLACE_SOURCE"
    IFS=',' read -r -a items <<< "$COMPONENTS"
    for component in "${items[@]}"; do
        [ -n "$component" ] && echo "  [dry-run] plugin add $component@$MARKETPLACE_NAME"
    done
    exit 0
fi

if ! command -v codex >/dev/null 2>&1; then
    echo "Error: codex CLI is required for --host codex." >&2
    exit 1
fi

add_args=(plugin marketplace add "$MARKETPLACE_SOURCE" --json)
if $VERSION_EXPLICIT && ! $LOCAL_SOURCE; then
    add_args+=(--ref "v${VERSION#v}")
fi

add_result=$(codex "${add_args[@]}")
already_added=$(python3 -c 'import json,sys; print("true" if json.load(sys.stdin).get("alreadyAdded") else "false")' <<< "$add_result")

marketplace_info=$(codex plugin marketplace list --json | python3 -c '
import json,sys
name=sys.argv[1]
for item in json.load(sys.stdin).get("marketplaces", []):
    if item.get("name") == name:
        source=item.get("marketplaceSource", {})
        print("{}\t{}\t{}".format(
            source.get("sourceType", ""), source.get("source", ""), item.get("root", "")
        ))
        break
' "$MARKETPLACE_NAME")
IFS=$'\t' read -r marketplace_type marketplace_value marketplace_root <<< "$marketplace_info"

if $LOCAL_SOURCE; then
    if [ "$marketplace_type" != "local" ] || \
       [ "$(cd "$marketplace_value" 2>/dev/null && pwd -P)" != "$(cd "$MARKETPLACE_SOURCE" && pwd -P)" ]; then
        echo "Error: marketplace '$MARKETPLACE_NAME' already points at a different source." >&2
        exit 1
    fi
elif [ "$marketplace_type" = "local" ]; then
    echo "Error: marketplace '$MARKETPLACE_NAME' points at local source $marketplace_value." >&2
    echo "Remove or repoint it explicitly before using the public installer." >&2
    exit 1
fi

if [ "$already_added" = "true" ]; then
    if $VERSION_EXPLICIT && ! $LOCAL_SOURCE; then
        expected_ref="v${VERSION#v}"
        current_commit=$(git -C "$marketplace_root" rev-parse HEAD 2>/dev/null || true)
        expected_commit=$(git -C "$marketplace_root" rev-parse "$expected_ref^{commit}" 2>/dev/null || true)
        if [ -z "$current_commit" ] || [ -z "$expected_commit" ] || \
           [ "$current_commit" != "$expected_commit" ]; then
            echo "Error: Codex marketplace '$MARKETPLACE_NAME' already exists at a different ref." >&2
            echo "Remove or repoint it explicitly before installing $expected_ref." >&2
            exit 1
        fi
    fi
    if ! $LOCAL_SOURCE && ! $VERSION_EXPLICIT; then
        codex plugin marketplace upgrade "$MARKETPLACE_NAME" --json >/dev/null
    fi
fi

IFS=',' read -r -a items <<< "$COMPONENTS"
for component in "${items[@]}"; do
    [ -n "$component" ] || continue
    codex plugin add "$component@$MARKETPLACE_NAME" --json >/dev/null
    echo "  [ok] $component@$MARKETPLACE_NAME"
done
