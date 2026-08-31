#!/usr/bin/env bash
#
# Validation Script — run locally or from CI
#
# Checks:
#   1. JSON syntax (catalog, Claude/Codex manifests, eval cases)
#   2. SKILL.md frontmatter (name, description required)
#   3. Component catalog and Claude/Codex installer lifecycle
#   4. Private static/runtime harnesses when present
#   5. Exact public tree construction through release.sh when present
#
# Usage:
#   scripts/validate.sh [--profile private|public]
#   scripts/validate.sh --release vX.Y.Z

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
cd "$REPO_DIR"

PROFILE=""
if [ "$#" -eq 0 ]; then
    if [ -f "$SCRIPT_DIR/release/main.py" ] || \
       [ -f "$SCRIPT_DIR/prepush/main.py" ] || \
       [ -f "$REPO_DIR/eval/run.py" ]; then
        PROFILE="private"
    else
        PROFILE="public"
    fi
elif [ "$#" -eq 2 ] && [ "$1" = "--profile" ]; then
    case "$2" in
        private|public) PROFILE="$2" ;;
        *)
            echo "validate: profile must be private or public." >&2
            exit 2
            ;;
    esac
elif [ "$#" -eq 2 ] && [ "$1" = "--release" ]; then
    if [ ! -f "$SCRIPT_DIR/release/main.py" ]; then
        echo "validate: --release is available only in the private source checkout." >&2
        exit 2
    fi
    exec python3 -m scripts.release.main validate "$2"
else
    echo "Usage: scripts/validate.sh [--profile private|public] [--release vX.Y.Z]" >&2
    exit 2
fi

PASSES=0
FAILURES=0
SKIPS=0
VALIDATE_TMP=$(mktemp -d -t hukuhaka-validate-XXXXXX)
trap 'rm -rf "$VALIDATE_TMP"' EXIT

pass() { PASSES=$((PASSES+1)); echo "  [ok] $1"; }
fail() { FAILURES=$((FAILURES+1)); echo "  [FAIL] $1"; }
skip() { SKIPS=$((SKIPS+1)); echo "  [skip] $1"; }

# ── 1. JSON Syntax ──────────────────────────────────────────────────

echo "JSON syntax:"

validate_json() {
    local file="$1"
    local label="${file#$REPO_DIR/}"
    if python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "$file" 2>/dev/null; then
        pass "$label"
    else
        fail "$label — invalid JSON"
    fi
}

# plugin.json — every plugin under marketplace/
found_any_plugin=0
for plugin_json in "$REPO_DIR"/marketplace/*/.claude-plugin/plugin.json; do
    [ -f "$plugin_json" ] || continue
    validate_json "$plugin_json"
    found_any_plugin=1
done
if [ "$found_any_plugin" -eq 0 ]; then
    fail "no marketplace/*/.claude-plugin/plugin.json found"
fi

# Codex plugin manifests and repo marketplace
for plugin_json in "$REPO_DIR"/marketplace/*/.codex-plugin/plugin.json; do
    [ -f "$plugin_json" ] && validate_json "$plugin_json"
done
[ -f "$REPO_DIR/.agents/plugins/marketplace.json" ] && \
    validate_json "$REPO_DIR/.agents/plugins/marketplace.json"
[ -f "$REPO_DIR/components.json" ] && validate_json "$REPO_DIR/components.json"

# eval v2 cases
for f in "$REPO_DIR"/eval/cases/*/case.json; do
    [ -f "$f" ] && validate_json "$f"
done

# ── 2. SKILL.md Frontmatter ─────────────────────────────────────────

echo ""
echo "SKILL.md frontmatter:"

validate_frontmatter() {
    local file="$1"
    local label="${file#$REPO_DIR/}"

    # Extract YAML frontmatter between --- delimiters
    local frontmatter
    frontmatter=$(awk '/^---$/{if(n++)exit;next}n' "$file")

    if [ -z "$frontmatter" ]; then
        fail "$label — no YAML frontmatter (missing --- delimiters)"
        return
    fi

    local has_name has_desc
    has_name=$(grep -c '^name:' <<<"$frontmatter" || true)
    has_desc=$(grep -c '^description:' <<<"$frontmatter" || true)

    if [ "$has_name" -ge 1 ] && [ "$has_desc" -ge 1 ]; then
        pass "$label"
    else
        local missing=""
        [ "$has_name" -eq 0 ] && missing="name"
        [ "$has_desc" -eq 0 ] && missing="${missing:+$missing, }description"
        fail "$label — missing: $missing"
    fi
}

# Plugin skills — every plugin under marketplace/
for f in "$REPO_DIR"/marketplace/*/skills/*/SKILL.md; do
    [ -f "$f" ] && validate_frontmatter "$f"
done

# Standalone skills
for f in "$REPO_DIR"/skills/*/SKILL.md; do
    [ -f "$f" ] && validate_frontmatter "$f"
done

# ── 3. Host support and installer lifecycle ─────────────────────────

echo ""
echo "Host support:"

if PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
    -s "$SCRIPT_DIR/tests" -p 'test_*.py' > "$VALIDATE_TMP/installer-tests.log" 2>&1; then
    pass "transactional installer state, rollback, drift, and recovery"
else
    fail "installer unit tests — $(tail -8 "$VALIDATE_TMP/installer-tests.log" | tr '\n' ' ')"
fi

if [ ! -d "$SCRIPT_DIR/prepush/tests" ]; then
    if [ "$PROFILE" = "private" ]; then
        fail "private pre-push workflow tests — required suite is missing"
    else
        skip "private pre-push workflow tests"
    fi
elif PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
    -s "$SCRIPT_DIR/prepush/tests" -p 'test_*.py' \
    > "$VALIDATE_TMP/prepush-tests.log" 2>&1; then
    pass "private push policy, public readiness, and workflow completion"
else
    fail "pre-push workflow tests — $(tail -8 "$VALIDATE_TMP/prepush-tests.log" | tr '\n' ' ')"
fi

if [ -d "$SCRIPT_DIR/prepush/tests" ]; then
    if bash -n \
        "$SCRIPT_DIR/push-private.sh" \
        "$SCRIPT_DIR/push-preflight.sh" \
        "$SCRIPT_DIR/prepush/pre-push" \
        "$SCRIPT_DIR/tests/run-codex-docker-e2e.sh"; then
        pass "private push shell entrypoints"
    else
        fail "private push shell entrypoints — syntax error"
    fi
fi

if [ ! -d "$SCRIPT_DIR/release/tests" ]; then
    if [ "$PROFILE" = "private" ]; then
        fail "private release workflow tests — required suite is missing"
    else
        skip "private release workflow tests"
    fi
elif PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
    -s "$SCRIPT_DIR/release/tests" -p 'test_*.py' \
    > "$VALIDATE_TMP/release-tests.log" 2>&1; then
    pass "release build safety + exact-tag public publish"
else
    fail "release workflow tests — $(tail -8 "$VALIDATE_TMP/release-tests.log" | tr '\n' ' ')"
fi

if [ ! -f "$REPO_DIR/eval/run.py" ]; then
    if [ "$PROFILE" = "private" ]; then
        fail "eval v2 runner tests — required private harness is missing"
    else
        skip "eval v2 runner tests (private harness not present in this checkout)"
    fi
elif PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
    -s "$REPO_DIR/eval/tests" -p 'test_*.py' > "$VALIDATE_TMP/eval-v2-tests.log" 2>&1; then
    pass "eval v2 transcript normalization and evidence contracts"
else
    fail "eval v2 runner tests — $(tail -8 "$VALIDATE_TMP/eval-v2-tests.log" | tr '\n' ' ')"
fi

if python3 "$SCRIPT_DIR/tests/check-component-catalog.py" > "$VALIDATE_TMP/component-catalog.log" 2>&1; then
    pass "component catalog"
else
    fail "component catalog — $(tail -3 "$VALIDATE_TMP/component-catalog.log" | tr '\n' ' ')"
fi

if python3 "$SCRIPT_DIR/tests/check-host-support.py" > "$VALIDATE_TMP/host-support.log" 2>&1; then
    pass "dual-host component contracts"
else
    fail "host support — $(tail -3 "$VALIDATE_TMP/host-support.log" | tr '\n' ' ')"
fi

if python3 "$SCRIPT_DIR/tests/plugin_contracts.py" > "$VALIDATE_TMP/plugin-contracts.log" 2>&1; then
    pass "plugin manifests, skill metadata, and hook schemas"
else
    fail "plugin contracts — $(tail -6 "$VALIDATE_TMP/plugin-contracts.log" | tr '\n' ' ')"
fi

if python3 "$SCRIPT_DIR/tests/document_contracts.py" > "$VALIDATE_TMP/document-contracts.log" 2>&1; then
    pass "tracked documentation links and current contracts"
else
    fail "document contracts — $(tail -6 "$VALIDATE_TMP/document-contracts.log" | tr '\n' ' ')"
fi

# ── 4. Official-docs refresh script ─────────────────────────────────

echo ""
echo "Official docs refresh:"

if [ ! -f "$SCRIPT_DIR/maintenance/refresh-officials.sh" ]; then
    skip "refresh-officials.sh (private maintainer script)"
elif bash -n "$SCRIPT_DIR/maintenance/refresh-officials.sh" && "$SCRIPT_DIR/maintenance/refresh-officials.sh" --help > /dev/null; then
    pass "refresh-officials.sh syntax + help"
else
    fail "refresh-officials.sh syntax + help"
fi

# ── 5. Report-planner contract tests ───────────────────────────────

REPORT_PLANNER_TEST="$REPO_DIR/scripts/tests/contracts/hukuhaka-report-planner.test.mjs"

echo ""
echo "Report planner contract:"

if [ ! -f "$REPORT_PLANNER_TEST" ]; then
    skip "report-planner static tests (private harness not present in this checkout)"
elif node --test "$REPORT_PLANNER_TEST" > "$VALIDATE_TMP/report-planner-test.log" 2>&1; then
    pass "document contract + selective reference routing"
else
    fail "report-planner static tests — $(tail -3 "$VALIDATE_TMP/report-planner-test.log" | tr '\n' ' ')"
fi

# ── 6. Codex runtime tests ──────────────────────────────────────────

CODEX_TESTS=(
    "$REPO_DIR/scripts/tests/contracts/hukuhaka-codex-broker.test.mjs"
    "$REPO_DIR/scripts/tests/contracts/hukuhaka-codex-hooks.test.mjs"
    "$REPO_DIR/scripts/tests/contracts/hukuhaka-memory-audit-hooks.test.mjs"
    "$REPO_DIR/scripts/tests/contracts/hukuhaka-codex-prompting.test.mjs"
    "$REPO_DIR/scripts/tests/contracts/hukuhaka-codex-transfer.test.mjs"
)

echo ""
echo "Codex runtime:"

codex_tests_present=0
codex_tests_missing=""
for test_file in "${CODEX_TESTS[@]}"; do
    if [ -f "$test_file" ]; then
        codex_tests_present=$((codex_tests_present+1))
    else
        test_name=$(basename "$test_file")
        codex_tests_missing="${codex_tests_missing:+$codex_tests_missing, }$test_name"
    fi
done

if [ "$codex_tests_present" -eq 0 ]; then
    skip "Codex runtime tests (private harness not present in this checkout)"
elif [ "$codex_tests_present" -ne "${#CODEX_TESTS[@]}" ]; then
    fail "Codex runtime tests — incomplete private harness; missing: $codex_tests_missing"
elif node --test "${CODEX_TESTS[@]}" > "$VALIDATE_TMP/codex-runtime-test.log" 2>&1; then
    pass "broker lifecycle + prompting workflows + memory pressure + session transfer"
else
    fail "Codex runtime tests — $(tail -3 "$VALIDATE_TMP/codex-runtime-test.log" | tr '\n' ' ')"
fi

# ── 7. Exact public tree ─────────────────────────────────────────────

echo ""
echo "Public release tree:"

# Guard on what is actually executed below, not on release.sh's exec bit: a
# private checkout that lost that one mode bit would turn the only check that
# inspects the generated public tree into a green skip.
if [ ! -f "$SCRIPT_DIR/release/stage.py" ]; then
    if [ "$PROFILE" = "private" ]; then
        fail "public tree build — required private release tool is missing"
    else
        skip "public tree build (private release tool not present)"
    fi
elif PYTHONDONTWRITEBYTECODE=1 python3 -m scripts.release.stage \
       --destination "$VALIDATE_TMP/public-stage" \
        > "$VALIDATE_TMP/public-stage.log" 2>&1; then
    pass "release.sh worktree build + public validation"
else
    fail "public tree — $(tail -8 "$VALIDATE_TMP/public-stage.log" | tr '\n' ' ')"
fi

# ── Summary ──────────────────────────────────────────────────────────

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "$PASSES passed, $SKIPS skipped, $FAILURES failed."
if [ "$FAILURES" -eq 0 ]; then
    exit 0
else
    exit 1
fi
