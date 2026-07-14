#!/usr/bin/env bash
#
# Validation Script — run locally or from CI
#
# Checks:
#   1. JSON syntax (catalog, Claude/Codex manifests, specs, scenarios)
#   2. SKILL.md frontmatter (name, description required)
#   3. Claude deploy dry-run
#   4. Component catalog and Claude/Codex installer lifecycle
#   5. Private static/runtime harnesses when present
#   6. Exact public staging through release-public.sh when present
#
# Usage:
#   scripts/validate.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

ERRORS=0
CHECKS=0
VALIDATE_TMP=$(mktemp -d -t hukuhaka-validate-XXXXXX)
trap 'rm -rf "$VALIDATE_TMP"' EXIT

pass() { CHECKS=$((CHECKS+1)); echo "  [ok] $1"; }
fail() { CHECKS=$((CHECKS+1)); ERRORS=$((ERRORS+1)); echo "  [FAIL] $1"; }

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

# eval specs
for f in "$REPO_DIR"/eval/specs/*.json; do
    [ -f "$f" ] && validate_json "$f"
done

# eval scenarios
for f in "$REPO_DIR"/eval/scenarios/*.json; do
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

# ── 3. Deploy Dry Run ───────────────────────────────────────────────

echo ""
echo "Deploy dry run:"

if "$SCRIPT_DIR/deploy.sh" --dry-run > /dev/null 2>&1; then
    pass "deploy.sh --dry-run"
else
    fail "deploy.sh --dry-run failed"
fi

# ── 4. Host support and installer lifecycle ─────────────────────────

echo ""
echo "Host support:"

if python3 "$SCRIPT_DIR/component_catalog.py" validate > "$VALIDATE_TMP/component-catalog.log" 2>&1; then
    pass "component catalog"
else
    fail "component catalog — $(tail -3 "$VALIDATE_TMP/component-catalog.log" | tr '\n' ' ')"
fi

if python3 "$SCRIPT_DIR/check-host-support.py" > "$VALIDATE_TMP/host-support.log" 2>&1; then
    pass "report-planner Claude/Codex contract"
else
    fail "host support — $(tail -3 "$VALIDATE_TMP/host-support.log" | tr '\n' ' ')"
fi

bash "$SCRIPT_DIR/preflight.sh" --host claude --components hukuhaka-report-planner \
    --src-dir "$REPO_DIR" > "$VALIDATE_TMP/preflight-claude.json" 2>/dev/null || true
bash "$SCRIPT_DIR/preflight.sh" --host codex --components hukuhaka-report-planner \
    --src-dir "$REPO_DIR" > "$VALIDATE_TMP/preflight-codex.json" 2>/dev/null || true
if python3 - "$VALIDATE_TMP/preflight-claude.json" "$VALIDATE_TMP/preflight-codex.json" <<'PY'
import json, sys
claude = {item["name"] for item in json.load(open(sys.argv[1]))["requirements"]}
codex = {item["name"] for item in json.load(open(sys.argv[2]))["requirements"]}
raise SystemExit(0 if "codex" not in claude and "codex" in codex else 1)
PY
then
    pass "host-aware dependency preflight"
else
    fail "host-aware dependency preflight"
fi

install_test_home=$(mktemp -d)
install_test_version=$(tr -d '[:space:]' < "$REPO_DIR/VERSION")
install_all_output=$(HOME="$install_test_home" "$SCRIPT_DIR/install.sh" \
    --source-dir "$REPO_DIR" --version "$install_test_version" --all --dry-run \
    --skip-preflight --skip-extras 2>&1 || true)
install_all_components=$(printf '%s\n' "$install_all_output" | sed -n 's/^Components: //p' | head -1)
if [ -n "$install_all_components" ] && \
   [[ ",$install_all_components," != *",hukuhaka-ltm,"* ]] && \
   [[ ",$install_all_components," != *",hukuhaka-project-mapper,"* ]] && \
   printf '%s\n' "$install_all_output" | grep -q '^  Claude Code: complete$' && \
   ! printf '%s\n' "$install_all_output" | grep -q '^  Codex:'; then
    pass "non-interactive installer defaults to Claude and excludes deprecated plugins"
else
    fail "installer non-interactive default/lifecycle policy"
fi

install_legacy_output=$(HOME="$install_test_home" "$SCRIPT_DIR/install.sh" \
    --source-dir "$REPO_DIR" --version "$install_test_version" \
    --components hukuhaka-ltm --dry-run \
    --skip-preflight --skip-extras 2>&1 || true)
if printf '%s\n' "$install_legacy_output" | grep -q "deprecated component(s) selected: hukuhaka-ltm" && \
   printf '%s\n' "$install_legacy_output" | grep -q "^Components: hukuhaka-ltm$"; then
    pass "explicit deprecated install remains available with warning"
else
    fail "explicit deprecated install policy"
fi

claude_runtime_home="$install_test_home/claude-runtime"
mkdir -p "$claude_runtime_home"
claude_install_args=(--source-dir "$REPO_DIR" --version "$install_test_version" --host claude \
    --all --skip-preflight --skip-extras)
if HOME="$claude_runtime_home" "$SCRIPT_DIR/install.sh" "${claude_install_args[@]}" \
       > "$VALIDATE_TMP/claude-install-1.log" 2>&1 && \
   HOME="$claude_runtime_home" "$SCRIPT_DIR/install.sh" "${claude_install_args[@]}" \
       > "$VALIDATE_TMP/claude-install-2.log" 2>&1 && \
   HOME="$claude_runtime_home" "$SCRIPT_DIR/install.sh" --host claude --uninstall \
       > "$VALIDATE_TMP/claude-remove-1.log" 2>&1 && \
   HOME="$claude_runtime_home" "$SCRIPT_DIR/install.sh" --host claude --uninstall \
       > "$VALIDATE_TMP/claude-remove-2.log" 2>&1; then
    pass "Claude native install/reinstall/uninstall lifecycle"
else
    fail "Claude native lifecycle"
fi

claude_minimal_home="$install_test_home/claude-minimal"
mkdir -p "$claude_minimal_home"
claude_minimal_args=(--source-dir "$REPO_DIR" --version "$install_test_version" --host claude \
    --components claude-md --skip-preflight --skip-extras)
if HOME="$claude_minimal_home" "$SCRIPT_DIR/install.sh" "${claude_minimal_args[@]}" \
       > "$VALIDATE_TMP/claude-minimal-1.log" 2>&1 && \
   HOME="$claude_minimal_home" "$SCRIPT_DIR/install.sh" "${claude_minimal_args[@]}" \
       > "$VALIDATE_TMP/claude-minimal-2.log" 2>&1 && \
   grep -q '^  Claude Code: complete$' "$VALIDATE_TMP/claude-minimal-2.log" && \
   ! grep -q 'unbound variable' "$VALIDATE_TMP/claude-minimal-2.log"; then
    pass "Claude plugin-free reinstall lifecycle"
else
    fail "Claude plugin-free reinstall — inspect $VALIDATE_TMP/claude-minimal-*.log"
fi
rm -rf "$install_test_home"

codex_dry_run=$(HOME="$VALIDATE_TMP/codex-dry-home" "$SCRIPT_DIR/install.sh" \
    --source-dir "$REPO_DIR" --version "$install_test_version" --host codex \
    --all --dry-run --skip-preflight --skip-extras 2>&1 || true)
if printf '%s\n' "$codex_dry_run" | grep -q '^Components: hukuhaka-report-planner$' && \
   printf '%s\n' "$codex_dry_run" | grep -q 'plugin add hukuhaka-report-planner@hukuhaka-harness'; then
    pass "Codex installer dry-run lifecycle"
else
    fail "Codex installer dry-run lifecycle"
fi

both_dry_run=$(HOME="$VALIDATE_TMP/both-dry-home" "$SCRIPT_DIR/install.sh" \
    --source-dir "$REPO_DIR" --version "$install_test_version" --host both \
    --all --dry-run --skip-preflight --skip-extras 2>&1 || true)
if printf '%s\n' "$both_dry_run" | grep -q '^  Claude Code: hukuhaka-report-planner,hukuhaka-codex,claude-md$' && \
   printf '%s\n' "$both_dry_run" | grep -q '^  Codex:       hukuhaka-report-planner$' && \
   printf '%s\n' "$both_dry_run" | grep -q '^  Claude Code: complete$' && \
   printf '%s\n' "$both_dry_run" | grep -q '^  Codex:       complete$'; then
    pass "both-host installer applies the component support matrix"
else
    fail "both-host installer plan/results"
fi

codex_unsupported=$(HOME="$VALIDATE_TMP/codex-unsupported-home" "$SCRIPT_DIR/install.sh" \
    --source-dir "$REPO_DIR" --version "$install_test_version" --host codex \
    --components hukuhaka-codex --dry-run --skip-preflight --skip-extras 2>&1 || true)
if printf '%s\n' "$codex_unsupported" | grep -q "unknown component 'hukuhaka-codex'"; then
    pass "installer rejects components unsupported by selected host"
else
    fail "installer host compatibility rejection"
fi

if command -v codex >/dev/null 2>&1; then
    codex_runtime_root="$VALIDATE_TMP/codex-runtime"
    mkdir -p "$codex_runtime_root/home" "$codex_runtime_root/codex"
    codex_install_args=(--source-dir "$REPO_DIR" --version "$install_test_version" --host codex \
        --all --skip-preflight --skip-extras)
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
    echo "  [skip] Codex native lifecycle (codex CLI not available)"
fi

fake_codex_root="$VALIDATE_TMP/fake-codex-marketplace"
fake_codex_bin="$VALIDATE_TMP/fake-codex-bin"
fake_codex_state="$VALIDATE_TMP/fake-codex-state"
mkdir -p "$fake_codex_root" "$fake_codex_bin" "$fake_codex_state"
git -C "$fake_codex_root" init -q
git -C "$fake_codex_root" config user.name validate
git -C "$fake_codex_root" config user.email validate@example.com
git -C "$fake_codex_root" commit --allow-empty -q -m fixture
git -C "$fake_codex_root" tag "v$install_test_version"
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
    printf '{"marketplaces":[{"name":"hukuhaka-harness","root":"%s","marketplaceSource":{"sourceType":"github","source":"hukuhaka/hukuhaka-harness"}}]}\n' "$FAKE_CODEX_ROOT"
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
codex_pinned_args=(--components hukuhaka-report-planner --version "$install_test_version" --version-explicit)
if PATH="$fake_codex_bin:$PATH" FAKE_CODEX_ROOT="$fake_codex_root" FAKE_CODEX_STATE="$fake_codex_state" \
       "$SCRIPT_DIR/hosts/codex.sh" "${codex_pinned_args[@]}" > "$VALIDATE_TMP/codex-pinned-1.log" 2>&1 && \
   PATH="$fake_codex_bin:$PATH" FAKE_CODEX_ROOT="$fake_codex_root" FAKE_CODEX_STATE="$fake_codex_state" \
       "$SCRIPT_DIR/hosts/codex.sh" "${codex_pinned_args[@]}" > "$VALIDATE_TMP/codex-pinned-2.log" 2>&1 && \
   ! PATH="$fake_codex_bin:$PATH" FAKE_CODEX_ROOT="$fake_codex_root" FAKE_CODEX_STATE="$fake_codex_state" \
       "$SCRIPT_DIR/hosts/codex.sh" --components hukuhaka-report-planner \
       --version 9.9.9 --version-explicit > "$VALIDATE_TMP/codex-pinned-mismatch.log" 2>&1; then
    pass "Codex version-pinned reinstall and mismatch rejection"
else
    fail "Codex version-pinned lifecycle — inspect $VALIDATE_TMP/codex-pinned-*.log"
fi

# ── 5. Skeleton golden tests (deterministic; dual-mode on/off) ──────
# The harness lives in an internal-only dir that is not part of public
# releases — skip cleanly when it is absent (e.g. public-repo CI).

GOLDEN="$REPO_DIR/eval/static-checks/skeleton-golden.sh"

echo ""
echo "Skeleton golden tests:"

if [ ! -f "$GOLDEN" ]; then
    echo "  [skip] skeleton-golden (harness not present in this checkout)"
elif bash "$GOLDEN" > "$VALIDATE_TMP/skeleton-golden.log" 2>&1; then
    pass "skeleton-golden ($(tail -1 "$VALIDATE_TMP/skeleton-golden.log"))"
else
    fail "skeleton-golden — $(tail -3 "$VALIDATE_TMP/skeleton-golden.log" | tr '\n' ' ')"
fi

# ── 6. Official-docs refresh script ─────────────────────────────────

echo ""
echo "Official docs refresh:"

if [ ! -f "$SCRIPT_DIR/refresh-officials.sh" ]; then
    echo "  [skip] refresh-officials.sh (private maintainer script)"
elif bash -n "$SCRIPT_DIR/refresh-officials.sh" && "$SCRIPT_DIR/refresh-officials.sh" --help > /dev/null; then
    pass "refresh-officials.sh syntax + help"
else
    fail "refresh-officials.sh syntax + help"
fi

# ── 7. Report-planner contract tests ───────────────────────────────

REPORT_PLANNER_TEST="$REPO_DIR/eval/static-checks/hukuhaka-report-planner.test.mjs"

echo ""
echo "Report planner contract:"

if [ ! -f "$REPORT_PLANNER_TEST" ]; then
    echo "  [skip] report-planner static tests (private harness not present in this checkout)"
elif node --test "$REPORT_PLANNER_TEST" > "$VALIDATE_TMP/report-planner-test.log" 2>&1; then
    pass "document contract + selective reference routing"
else
    fail "report-planner static tests — $(tail -3 "$VALIDATE_TMP/report-planner-test.log" | tr '\n' ' ')"
fi

# ── 8. Codex runtime tests ──────────────────────────────────────────

CODEX_TESTS=(
    "$REPO_DIR/eval/static-checks/hukuhaka-codex-broker.test.mjs"
    "$REPO_DIR/eval/static-checks/hukuhaka-codex-prompting.test.mjs"
    "$REPO_DIR/eval/static-checks/hukuhaka-codex-transfer.test.mjs"
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
    echo "  [skip] Codex runtime tests (private harness not present in this checkout)"
elif [ "$codex_tests_present" -ne "${#CODEX_TESTS[@]}" ]; then
    fail "Codex runtime tests — incomplete private harness; missing: $codex_tests_missing"
elif node --test "${CODEX_TESTS[@]}" > "$VALIDATE_TMP/codex-runtime-test.log" 2>&1; then
    pass "broker lifecycle + prompting workflows + session transfer"
else
    fail "Codex runtime tests — $(tail -3 "$VALIDATE_TMP/codex-runtime-test.log" | tr '\n' ' ')"
fi

# ── 9. Exact public staging ─────────────────────────────────────────

echo ""
echo "Public release staging:"

if [ ! -x "$SCRIPT_DIR/release-public.sh" ]; then
    echo "  [skip] public staging (private release script not present)"
elif "$SCRIPT_DIR/release-public.sh" --stage-only "$VALIDATE_TMP/public-stage" \
        > "$VALIDATE_TMP/public-stage.log" 2>&1; then
    pass "release-public.sh stage-only + staged validation"
else
    fail "public staging — $(tail -5 "$VALIDATE_TMP/public-stage.log" | tr '\n' ' ')"
fi

# ── Summary ──────────────────────────────────────────────────────────

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ "$ERRORS" -eq 0 ]; then
    echo "All $CHECKS checks passed."
    exit 0
else
    echo "$ERRORS/$CHECKS checks failed."
    exit 1
fi
