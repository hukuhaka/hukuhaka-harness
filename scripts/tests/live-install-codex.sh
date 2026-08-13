#!/usr/bin/env bash
# Cross-platform Codex release smoke. With no source directory it exercises the
# documented public bootstrap at the exact release tag. Tests may pass a source
# directory to exercise the same lifecycle without network access.
set -euo pipefail

EXPECTED_VERSION="${1:-}"
SOURCE_DIR="${2:-}"

if [ -z "$EXPECTED_VERSION" ]; then
    echo "usage: $0 <version> [source-dir]" >&2
    exit 2
fi
EXPECTED_VERSION="${EXPECTED_VERSION#v}"

SMOKE_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/hukuhaka-codex-live-install.XXXXXX")
cleanup() {
    local rc=$?
    rm -rf "$SMOKE_ROOT"
    return "$rc"
}
trap cleanup EXIT INT TERM

mkdir -p "$SMOKE_ROOT/bin" "$SMOKE_ROOT/home" "$SMOKE_ROOT/codex-home" "$SMOKE_ROOT/state"

if [ -n "$SOURCE_DIR" ]; then
    SOURCE_ROOT=$(cd "$SOURCE_DIR" && pwd -P)
    INSTALL_COMMAND=(
        /bin/bash "$SOURCE_ROOT/scripts/install.sh"
        --source-dir "$SOURCE_ROOT"
        --version "$EXPECTED_VERSION"
        codex install --recommended --yes
    )
else
    SOURCE_ROOT=$(git rev-parse --show-toplevel)
    git -C "$SOURCE_ROOT" rev-parse --verify "v${EXPECTED_VERSION}^{commit}" >/dev/null
    INSTALL_URL="https://raw.githubusercontent.com/hukuhaka/hukuhaka-harness/v${EXPECTED_VERSION}/scripts/install.sh"
fi

cat > "$SMOKE_ROOT/bin/codex" <<'SH'
#!/usr/bin/env bash
set -euo pipefail

state_dir="${FAKE_CODEX_STATE:?}"
marketplace="$state_dir/marketplace"
plugins="$state_dir/plugins"
touch "$plugins"

if [ "${1:-}" = "--version" ]; then
    printf 'codex release smoke\n'
elif [ "${1:-}" = "plugin" ] && [ "${2:-}" = "marketplace" ] && [ "${3:-}" = "add" ]; then
    printf '%s\n' "${4:?}" > "$marketplace"
    printf '{"alreadyAdded":false}\n'
elif [ "${1:-}" = "plugin" ] && [ "${2:-}" = "marketplace" ] && [ "${3:-}" = "list" ]; then
    if [ -f "$marketplace" ]; then
        source_value=$(cat "$marketplace")
        if [ "$source_value" = "hukuhaka/hukuhaka-harness" ]; then
            source_type=git
            source_value="https://github.com/hukuhaka/hukuhaka-harness.git"
        else
            source_type=local
        fi
        printf '{"marketplaces":[{"name":"hukuhaka-harness","root":"%s","marketplaceSource":{"sourceType":"%s","source":"%s"}}]}\n' \
            "$FAKE_SOURCE_ROOT" "$source_type" "$source_value"
    else
        printf '{"marketplaces":[]}\n'
    fi
elif [ "${1:-}" = "plugin" ] && [ "${2:-}" = "marketplace" ] && [ "${3:-}" = "remove" ]; then
    rm -f "$marketplace"
    printf '{}\n'
elif [ "${1:-}" = "plugin" ] && [ "${2:-}" = "list" ]; then
    first=1
    printf '{"installed":['
    while IFS= read -r name; do
        [ -n "$name" ] || continue
        [ "$first" -eq 1 ] || printf ','
        first=0
        version=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' \
            "$FAKE_SOURCE_ROOT/marketplace/$name/.codex-plugin/plugin.json")
        installed="$CODEX_HOME/plugins/cache/hukuhaka-harness/$name/$version"
        printf '{"name":"%s","marketplaceName":"hukuhaka-harness","pluginId":"%s@hukuhaka-harness","version":"%s","installedPath":"%s"}' \
            "$name" "$name" "$version" "$installed"
    done < "$plugins"
    printf ']}\n'
elif [ "${1:-}" = "plugin" ] && [ "${2:-}" = "add" ]; then
    name="${3%%@*}"
    version=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' \
        "$FAKE_SOURCE_ROOT/marketplace/$name/.codex-plugin/plugin.json")
    cache_root="$CODEX_HOME/plugins/cache/hukuhaka-harness/$name"
    installed="$cache_root/$version"
    rm -rf "$cache_root"
    mkdir -p "$cache_root"
    cp -R "$FAKE_SOURCE_ROOT/marketplace/$name" "$installed"
    if ! grep -Fxq "$name" "$plugins"; then
        printf '%s\n' "$name" >> "$plugins"
    fi
    printf '{"pluginId":"%s@hukuhaka-harness","name":"%s","marketplaceName":"hukuhaka-harness","version":"%s","installedPath":"%s"}\n' \
        "$name" "$name" "$version" "$installed"
elif [ "${1:-}" = "plugin" ] && [ "${2:-}" = "remove" ]; then
    name="${3%%@*}"
    next="$plugins.next"
    grep -Fxv "$name" "$plugins" > "$next" || true
    mv "$next" "$plugins"
    rm -rf "$CODEX_HOME/plugins/cache/hukuhaka-harness/$name"
    printf '{}\n'
elif [ "${1:-}" = "doctor" ] && [ "${2:-}" = "--json" ]; then
    config="$CODEX_HOME/config.toml"
    if grep -Eq '^[[:space:]]*(agents\.)?max_threads[[:space:]]*=' "$config" && \
       grep -Eq '^[[:space:]]*(agents\.)?max_concurrent_threads_per_session[[:space:]]*=' "$config"; then
        printf '{"checks":{"config.load":{"status":"warning","summary":"config loaded","details":{"startup warning":"Ignoring malformed agent role definition: duplicate field `max_concurrent_threads_per_session`"}}}}\n'
    else
        printf '{"checks":{"config.load":{"status":"ok","summary":"config loaded"}}}\n'
    fi
else
    printf 'unexpected fake codex args: %s\n' "$*" >&2
    exit 2
fi
SH
chmod +x "$SMOKE_ROOT/bin/codex"

python3 - "$SMOKE_ROOT/codex-home/models_cache.json" <<'PY'
import json
import sys

payload = {
    "client_version": "release-smoke",
    "models": [
        {
            "slug": "gpt-5.6-sol",
            "multi_agent_version": "v2",
            "display_name": "GPT-5.6-Sol",
        },
        {
            "slug": "gpt-5.6-luna",
            "multi_agent_version": "v1",
            "display_name": "GPT-5.6-Luna",
        },
    ],
}
with open(sys.argv[1], "w", encoding="utf-8") as handle:
    json.dump(payload, handle, separators=(",", ":"))
    handle.write("\n")
PY
cp "$SMOKE_ROOT/codex-home/models_cache.json" "$SMOKE_ROOT/source-models-cache.json"

export HOME="$SMOKE_ROOT/home"
export CODEX_HOME="$SMOKE_ROOT/codex-home"
export FAKE_CODEX_STATE="$SMOKE_ROOT/state"
export FAKE_SOURCE_ROOT="$SOURCE_ROOT"
export PATH="$SMOKE_ROOT/bin:$PATH"

cat > "$CODEX_HOME/config.toml" <<'TOML'
[agents]
max_threads = 4 # legacy alias
default_subagent_model = "user-model"
TOML

run_install() {
    if [ -n "$SOURCE_DIR" ]; then
        "${INSTALL_COMMAND[@]}"
    else
        curl -fsSL "$INSTALL_URL" \
            | /bin/bash -s -- --version "$EXPECTED_VERSION" codex install --recommended --yes
    fi
}

first_output=$(run_install 2>&1)
second_output=$(run_install 2>&1)
printf '%s\n' "$first_output"
printf '%s\n' "$second_output"

if [ -z "$SOURCE_DIR" ]; then
    grep -Fq "Downloading hukuhaka-harness v${EXPECTED_VERSION}..." <<<"$first_output"
fi
grep -Eq "  Codex: +success" <<<"$first_output"
grep -Eq "  Codex: +success" <<<"$second_output"
grep -Fq "concurrency ceiling 4" <<<"$second_output"

python3 - "$CODEX_HOME" "$SMOKE_ROOT/source-models-cache.json" "$EXPECTED_VERSION" <<'PY'
import json
import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1])
source_cache = pathlib.Path(sys.argv[2])
version = sys.argv[3]

agent = root / "agents" / "evidence-scout.toml"
routing = root / "AGENTS.md"
catalog_path = root / "models-luna-v2.json"
manifest_path = root / ".hukuhaka-evidence-scout-manifest.json"
config_path = root / "config.toml"

for path in (agent, routing, catalog_path, manifest_path, config_path):
    if not path.is_file():
        raise SystemExit("missing installed Evidence Scout artifact: {}".format(path))

if (root / "models_cache.json").read_bytes() != source_cache.read_bytes():
    raise SystemExit("models_cache.json changed")

catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
expected = json.loads(source_cache.read_text(encoding="utf-8"))
for model in expected["models"]:
    if model.get("slug") == "gpt-5.6-luna":
        model["multi_agent_version"] = "v2"
if catalog != expected:
    raise SystemExit("derived model catalog changed fields other than Luna multi_agent_version")

manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
if manifest.get("version") != version:
    raise SystemExit("manifest version {!r} != {!r}".format(manifest.get("version"), version))

routing_text = routing.read_text(encoding="utf-8")
if routing_text.count("<!-- hukuhaka-evidence-scout:begin -->") != 1 or routing_text.count("<!-- hukuhaka-evidence-scout:end -->") != 1:
    raise SystemExit("Evidence Scout routing marker count differs")

config = config_path.read_text(encoding="utf-8")
pointer = 'model_catalog_json = {}'.format(json.dumps(str(catalog_path)))
for expected_line in (
    pointer,
    "multi_agent = true",
    "max_concurrent_threads_per_session = 4",
):
    if expected_line not in config:
        raise SystemExit("missing config setting: {}".format(expected_line))
if config.index(pointer) > config.index("[features]"):
    raise SystemExit("model_catalog_json is not top-level")
if re.search(r"(?m)^\s*(?:agents\.)?max_threads\s*=", config):
    raise SystemExit("legacy agents.max_threads was not migrated")
if config.count("max_concurrent_threads_per_session = 4") != 1:
    raise SystemExit("canonical concurrency setting is not present exactly once")
if 'default_subagent_model = "user-model"' not in config:
    raise SystemExit("unmanaged agent default was not preserved")

backup = (root / "config.toml.hukuhaka-backup").read_text(encoding="utf-8")
if "max_threads = 4 # legacy alias" not in backup:
    raise SystemExit("legacy pre-migration config was not backed up")
PY

printf 'Codex Evidence Scout live install verified for v%s\n' "$EXPECTED_VERSION"
