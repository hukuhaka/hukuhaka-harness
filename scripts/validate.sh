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
#   scripts/validate.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
cd "$REPO_DIR"

if [ "$#" -ne 0 ]; then
    if [ "$#" -eq 2 ] && [ "$1" = "--release" ]; then
        if [ ! -x "$SCRIPT_DIR/release.sh" ]; then
            echo "validate: --release is available only in the private source checkout." >&2
            exit 2
        fi
        exec python3 -m scripts.release.main validate "$2"
    fi
    echo "Usage: scripts/validate.sh [--release vX.Y.Z]" >&2
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
    has_name=$(echo "$frontmatter" | grep -c '^name:' || true)
    has_desc=$(echo "$frontmatter" | grep -c '^description:' || true)

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

install_test_version=$(tr -d '[:space:]' < "$REPO_DIR/VERSION")

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
    skip "private pre-push workflow tests"
elif PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
    -s "$SCRIPT_DIR/prepush/tests" -p 'test_*.py' \
    > "$VALIDATE_TMP/prepush-tests.log" 2>&1; then
    pass "pre-push ref ranges"
else
    fail "pre-push workflow tests — $(tail -8 "$VALIDATE_TMP/prepush-tests.log" | tr '\n' ' ')"
fi

if [ ! -d "$SCRIPT_DIR/release/tests" ]; then
    skip "private release workflow tests"
elif PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
    -s "$SCRIPT_DIR/release/tests" -p 'test_*.py' \
    > "$VALIDATE_TMP/release-tests.log" 2>&1; then
    pass "release build safety + exact-tag public publish"
else
    fail "release workflow tests — $(tail -8 "$VALIDATE_TMP/release-tests.log" | tr '\n' ' ')"
fi

if [ ! -f "$REPO_DIR/eval/run.py" ]; then
    skip "eval v2 runner tests (private harness not present in this checkout)"
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
    pass "report-planner Claude/Codex contract"
else
    fail "host support — $(tail -3 "$VALIDATE_TMP/host-support.log" | tr '\n' ' ')"
fi

install_test_home=$(mktemp -d)
fake_host_bin="$install_test_home/host-bin"
mkdir -p "$fake_host_bin"
cat > "$fake_host_bin/claude" <<'SH'
#!/usr/bin/env bash
if [ "${1:-}" = "--version" ]; then
    echo "claude test double"
fi
exit 0
SH
chmod +x "$fake_host_bin/claude"
claude_test_path="$fake_host_bin:$PATH"

install_all_output=$(HOME="$install_test_home" "$SCRIPT_DIR/install.sh" \
    --source-dir "$REPO_DIR" --version "$install_test_version" --all --dry-run 2>&1 || true)
install_all_components=$(printf '%s\n' "$install_all_output" | sed -n 's/^Components: //p' | head -1)
if [ -n "$install_all_components" ] && \
   [[ ",$install_all_components," != *",hukuhaka-ltm,"* ]] && \
   [[ ",$install_all_components," != *",hukuhaka-project-mapper,"* ]] && \
   printf '%s\n' "$install_all_output" | grep -q '^  Claude Code: complete$' && \
   ! printf '%s\n' "$install_all_output" | grep -q '^  Codex:'; then
    pass "non-interactive installer defaults to supported Claude components"
else
    fail "installer non-interactive default/lifecycle policy"
fi

removed_component_policy_ok=1
for removed_component in hukuhaka-ltm hukuhaka-project-mapper; do
    if removed_output=$(HOME="$install_test_home" "$SCRIPT_DIR/install.sh" \
        --source-dir "$REPO_DIR" --version "$install_test_version" \
        --components "$removed_component" --dry-run 2>&1); then
        removed_component_policy_ok=0
    elif ! printf '%s\n' "$removed_output" | grep -q "unknown component '$removed_component'"; then
        removed_component_policy_ok=0
    fi
done
if [ "$removed_component_policy_ok" -eq 1 ]; then
    pass "removed components are rejected explicitly"
else
    fail "removed component selection policy"
fi

claude_runtime_home="$install_test_home/claude-runtime"
mkdir -p "$claude_runtime_home"
claude_install_args=(--source-dir "$REPO_DIR" --version "$install_test_version" --host claude \
    --all)
if PATH="$claude_test_path" HOME="$claude_runtime_home" \
       "$SCRIPT_DIR/install.sh" "${claude_install_args[@]}" \
       > "$VALIDATE_TMP/claude-install-1.log" 2>&1 && \
   PATH="$claude_test_path" HOME="$claude_runtime_home" \
       "$SCRIPT_DIR/install.sh" "${claude_install_args[@]}" \
       > "$VALIDATE_TMP/claude-install-2.log" 2>&1 && \
   PATH="$claude_test_path" HOME="$claude_runtime_home" \
       "$SCRIPT_DIR/install.sh" --host claude --uninstall \
       > "$VALIDATE_TMP/claude-remove-1.log" 2>&1 && \
   PATH="$claude_test_path" HOME="$claude_runtime_home" \
       "$SCRIPT_DIR/install.sh" --host claude --uninstall \
       > "$VALIDATE_TMP/claude-remove-2.log" 2>&1; then
    pass "Claude native install/reinstall/uninstall lifecycle"
else
    fail "Claude native lifecycle"
fi

claude_minimal_home="$install_test_home/claude-minimal"
mkdir -p "$claude_minimal_home"
claude_minimal_args=(--source-dir "$REPO_DIR" --version "$install_test_version" --host claude \
    --components claude-md)
if PATH="$claude_test_path" HOME="$claude_minimal_home" \
       "$SCRIPT_DIR/install.sh" "${claude_minimal_args[@]}" \
       > "$VALIDATE_TMP/claude-minimal-1.log" 2>&1 && \
   PATH="$claude_test_path" HOME="$claude_minimal_home" \
       "$SCRIPT_DIR/install.sh" "${claude_minimal_args[@]}" \
       > "$VALIDATE_TMP/claude-minimal-2.log" 2>&1 && \
   grep -q '^  Claude Code: complete$' "$VALIDATE_TMP/claude-minimal-2.log" && \
   ! grep -q 'unbound variable' "$VALIDATE_TMP/claude-minimal-2.log"; then
    pass "Claude plugin-free reinstall lifecycle"
else
    fail "Claude plugin-free reinstall — inspect $VALIDATE_TMP/claude-minimal-*.log"
fi

claude_partial_home="$install_test_home/claude-partial"
mkdir -p "$claude_partial_home/.claude"
cat > "$claude_partial_home/.claude/.hukuhaka-manifest.json" <<'JSON'
{
  "version": "1.0.9",
  "components": ["hukuhaka-ltm", "hukuhaka-project-mapper"],
  "files": []
}
JSON
claude_partial_args=(--source-dir "$REPO_DIR" --version "$install_test_version" --host claude
    --components hukuhaka-report-planner,hukuhaka-codex,claude-md)
if PATH="$claude_test_path" HOME="$claude_partial_home" \
       "$SCRIPT_DIR/install.sh" "${claude_partial_args[@]}" \
       > "$VALIDATE_TMP/claude-partial.log" 2>&1 && \
   python3 - "$claude_partial_home/.claude/.hukuhaka-manifest.json" "$install_test_version" <<'PY'
import json, sys
manifest = json.load(open(sys.argv[1]))
expected = {"hukuhaka-report-planner", "hukuhaka-codex", "claude-md"}
raise SystemExit(0 if manifest.get("version") == sys.argv[2] and set(manifest.get("components", [])) == expected else 1)
PY
then
    pass "Claude partial-state upgrade drops removed legacy components"
else
    fail "Claude partial-state upgrade — inspect $VALIDATE_TMP/claude-partial.log"
fi
rm -rf "$install_test_home"

codex_dry_run=$(HOME="$VALIDATE_TMP/codex-dry-home" "$SCRIPT_DIR/install.sh" \
    --source-dir "$REPO_DIR" --version "$install_test_version" --host codex \
    --all --dry-run 2>&1 || true)
if printf '%s\n' "$codex_dry_run" | grep -q '^Components: hukuhaka-report-planner,hukuhaka-engineering-plan,agents-md$' && \
   printf '%s\n' "$codex_dry_run" | grep -q 'plugin add hukuhaka-report-planner@hukuhaka-harness' && \
   printf '%s\n' "$codex_dry_run" | grep -q 'merge agents-md into'; then
    pass "Codex installer dry-run lifecycle"
else
    fail "Codex installer dry-run lifecycle"
fi

both_dry_run=$(HOME="$VALIDATE_TMP/both-dry-home" "$SCRIPT_DIR/install.sh" \
    --source-dir "$REPO_DIR" --version "$install_test_version" --host both \
    --all --dry-run 2>&1 || true)
if printf '%s\n' "$both_dry_run" | grep -q '^  Claude Code: hukuhaka-report-planner,hukuhaka-engineering-plan,hukuhaka-codex,claude-md$' && \
   printf '%s\n' "$both_dry_run" | grep -q '^  Codex:       hukuhaka-report-planner,hukuhaka-engineering-plan,agents-md$' && \
   printf '%s\n' "$both_dry_run" | grep -q '^  Claude Code: complete$' && \
   printf '%s\n' "$both_dry_run" | grep -q '^  Codex:       complete$'; then
    pass "both-host installer applies the component support matrix"
else
    fail "both-host installer plan/results"
fi

codex_unsupported=$(HOME="$VALIDATE_TMP/codex-unsupported-home" "$SCRIPT_DIR/install.sh" \
    --source-dir "$REPO_DIR" --version "$install_test_version" --host codex \
    --components hukuhaka-codex --dry-run 2>&1 || true)
if printf '%s\n' "$codex_unsupported" | grep -q "unknown component 'hukuhaka-codex'"; then
    pass "installer rejects components unsupported by selected host"
else
    fail "installer host compatibility rejection"
fi

if command -v codex >/dev/null 2>&1; then
    codex_runtime_root="$VALIDATE_TMP/codex-runtime"
    mkdir -p "$codex_runtime_root/home" "$codex_runtime_root/codex"
    codex_install_args=(--source-dir "$REPO_DIR" --version "$install_test_version" --host codex \
        --all)
    if HOME="$codex_runtime_root/home" CODEX_HOME="$codex_runtime_root/codex" \
       "$SCRIPT_DIR/install.sh" "${codex_install_args[@]}" > "$VALIDATE_TMP/codex-install-1.log" 2>&1 && \
       HOME="$codex_runtime_root/home" CODEX_HOME="$codex_runtime_root/codex" \
       "$SCRIPT_DIR/install.sh" "${codex_install_args[@]}" > "$VALIDATE_TMP/codex-install-2.log" 2>&1 && \
       HOME="$codex_runtime_root/home" CODEX_HOME="$codex_runtime_root/codex" \
       "$SCRIPT_DIR/install.sh" --host codex --uninstall > "$VALIDATE_TMP/codex-remove-1.log" 2>&1 && \
       HOME="$codex_runtime_root/home" CODEX_HOME="$codex_runtime_root/codex" \
       "$SCRIPT_DIR/install.sh" --host codex --uninstall > "$VALIDATE_TMP/codex-remove-2.log" 2>&1; then
        pass "Codex native install/reinstall/uninstall lifecycle"
    else
        fail "Codex native lifecycle — inspect $VALIDATE_TMP/codex-*.log"
    fi
else
    skip "Codex native lifecycle (codex CLI not available)"
fi

fake_codex_root="$VALIDATE_TMP/fake-codex-marketplace"
fake_codex_bin="$VALIDATE_TMP/fake-codex-bin"
fake_codex_state="$VALIDATE_TMP/fake-codex-state"
mkdir -p "$fake_codex_root" "$fake_codex_bin" "$fake_codex_state"
cat > "$fake_codex_bin/codex" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
state="${FAKE_CODEX_STATE:?}/marketplace"
if [[ "${1:-}" == "plugin" && "${2:-}" == "marketplace" && "${3:-}" == "add" ]]; then
    if [[ -f "$state" ]]; then
        printf '{"alreadyAdded":true}\n'
    else
        : > "$state"
        printf '{"alreadyAdded":false}\n'
    fi
elif [[ "${1:-}" == "plugin" && "${2:-}" == "marketplace" && "${3:-}" == "list" ]]; then
    printf '{"marketplaces":[{"name":"hukuhaka-harness","root":"%s","marketplaceSource":{"sourceType":"local","source":"%s"}}]}\n' "$FAKE_CODEX_ROOT" "$FAKE_SOURCE_ROOT"
elif [[ "${1:-}" == "plugin" && "${2:-}" == "marketplace" && "${3:-}" == "upgrade" ]]; then
    printf '{}\n'
elif [[ "${1:-}" == "plugin" && "${2:-}" == "add" ]]; then
    printf '{}\n'
else
    printf 'unexpected fake codex args: %s\n' "$*" >&2
    exit 2
fi
SH
chmod +x "$fake_codex_bin/codex"
codex_pinned_args=(--source-dir "$REPO_DIR" --host codex --components hukuhaka-report-planner \
    --version "$install_test_version")
if PATH="$fake_codex_bin:$PATH" FAKE_CODEX_ROOT="$fake_codex_root" FAKE_SOURCE_ROOT="$REPO_DIR" FAKE_CODEX_STATE="$fake_codex_state" \
       "$SCRIPT_DIR/install.sh" "${codex_pinned_args[@]}" > "$VALIDATE_TMP/codex-pinned-1.log" 2>&1 && \
   PATH="$fake_codex_bin:$PATH" FAKE_CODEX_ROOT="$fake_codex_root" FAKE_SOURCE_ROOT="$REPO_DIR" FAKE_CODEX_STATE="$fake_codex_state" \
       "$SCRIPT_DIR/install.sh" "${codex_pinned_args[@]}" > "$VALIDATE_TMP/codex-pinned-2.log" 2>&1 && \
   ! PATH="$fake_codex_bin:$PATH" FAKE_CODEX_ROOT="$fake_codex_root" FAKE_SOURCE_ROOT="$REPO_DIR" FAKE_CODEX_STATE="$fake_codex_state" \
       "$SCRIPT_DIR/install.sh" --source-dir "$REPO_DIR" --host codex \
       --components hukuhaka-report-planner --version 9.9.9 \
       > "$VALIDATE_TMP/codex-pinned-mismatch.log" 2>&1; then
    pass "Codex local-source reinstall and version mismatch rejection"
else
    fail "Codex local-source lifecycle — inspect $VALIDATE_TMP/codex-pinned-*.log"
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
    pass "broker lifecycle + prompting workflows + session transfer"
else
    fail "Codex runtime tests — $(tail -3 "$VALIDATE_TMP/codex-runtime-test.log" | tr '\n' ' ')"
fi

# ── 7. Exact public tree ─────────────────────────────────────────────

echo ""
echo "Public release tree:"

if [ ! -x "$SCRIPT_DIR/release.sh" ]; then
    skip "public tree build (private release tool not present)"
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
