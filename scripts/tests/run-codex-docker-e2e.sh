#!/usr/bin/env bash
# Run the real Codex installer lifecycle in a disposable Linux container.
set -euo pipefail

SOURCE_DIR="${1:-.}"
SOURCE_DIR=$(cd "$SOURCE_DIR" && pwd -P)
VERSION_FILE="$SOURCE_DIR/scripts/tests/codex-e2e-version.txt"
DOCKERFILE="$SOURCE_DIR/scripts/tests/codex-real-e2e.Dockerfile"

if [ ! -f "$VERSION_FILE" ] || [ ! -f "$DOCKERFILE" ]; then
    echo "codex-e2e: source tree is missing its Docker contract" >&2
    exit 2
fi

CODEX_VERSION=$(tr -d '[:space:]' < "$VERSION_FILE")
case "$CODEX_VERSION" in
    ''|*[!0-9A-Za-z._-]*)
        echo "codex-e2e: invalid Codex version in $VERSION_FILE" >&2
        exit 2
        ;;
esac

if ! command -v docker >/dev/null 2>&1; then
    echo "codex-e2e: docker CLI is required" >&2
    exit 1
fi
if ! docker info >/dev/null 2>&1; then
    echo "codex-e2e: the selected Docker context is unavailable" >&2
    exit 1
fi

IMAGE="hukuhaka-codex-e2e:${CODEX_VERSION}"
docker build \
    --build-arg "CODEX_VERSION=$CODEX_VERSION" \
    --file "$DOCKERFILE" \
    --tag "$IMAGE" \
    "$SOURCE_DIR"
docker run --rm "$IMAGE"
