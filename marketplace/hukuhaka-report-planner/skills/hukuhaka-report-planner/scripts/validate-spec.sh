#!/usr/bin/env bash
# validate-spec.sh — structural check for a final document-plan spec.md
# usage: validate-spec.sh [<spec.md>]
#   no path arg → read spec content from stdin
#   path arg    → read the on-disk file
# contract source: references/spec-schema.md
set -uo pipefail

FILE=""
for arg in "$@"; do
  case "$arg" in
    --*) echo "FAIL: unknown flag: $arg (usage: validate-spec.sh [<spec.md>])"; exit 2 ;;
    *) if [ -z "$FILE" ]; then FILE="$arg"; else echo "FAIL: extra argument: $arg"; exit 2; fi ;;
  esac
done
if [ -n "$FILE" ]; then
  # -r (not -f) so a process-substitution fd (/dev/fd/NN) or fifo is accepted, not just regular files
  if [ ! -r "$FILE" ]; then echo "FAIL: spec not found or unreadable: $FILE"; exit 1; fi
  SPEC="$(cat "$FILE")"
else
  SPEC="$(cat)"
fi

ERRORS=0
fail(){ echo "FAIL: $1"; ERRORS=$((ERRORS+1)); }

block_text(){
  printf '%s\n' "$SPEC" | awk -v heading="## $1" '
    $0 == heading { inside=1; next }
    inside && /^## / { exit }
    inside { print }
  '
}

require_block(){
  local count
  count="$(printf '%s\n' "$SPEC" | grep -Fxc "## $1" || true)"
  [ "$count" -ge 1 ] || { fail "block missing: $1"; return; }
  [ "$count" -eq 1 ] || fail "block duplicated: $1"
}

check_field(){
  local block="$1" field="$2" text line value
  text="$(block_text "$block")"
  line="$(printf '%s\n' "$text" | grep -E "^- $field:" | head -1 || true)"
  [ -n "$line" ] || { fail "$block field missing: $field"; return; }
  case "$line" in *'<'*) fail "$block field unfilled: $field"; return ;; esac
  value="${line#*:}"
  printf '%s' "$value" | grep -Eq '[^[:space:]]' || fail "$block field empty: $field"
}

BLOCKS=( "Document Model" "Evidence" "Structure" "Anchors" "Design Direction" "Build Contract" "Acceptance Tests" )
for block in "${BLOCKS[@]}"; do require_block "$block"; done

LAST_LINE=0
for block in "${BLOCKS[@]}"; do
  line="$(printf '%s\n' "$SPEC" | grep -Fn "## $block" | head -1 | cut -d: -f1 || true)"
  [ -n "$line" ] || continue
  [ "$line" -gt "$LAST_LINE" ] || fail "block out of order: $block"
  LAST_LINE="$line"
done

MODEL_FIELDS=( "job" "reading behavior" "form" "audience" "success test" "prose level" )
for field in "${MODEL_FIELDS[@]}"; do check_field "Document Model" "$field"; done

EVIDENCE="$(block_text "Evidence")"
printf '%s\n' "$EVIDENCE" | grep -Eq '^- source S[0-9]+:' || fail "Evidence needs at least one '- source S<number>:' line"
for field in "established" "gap"; do check_field "Evidence" "$field"; done
SOURCE_IDS="$(printf '%s\n' "$EVIDENCE" | sed -n 's/^- source \(S[0-9][0-9]*\):.*/\1/p')"

STRUCTURE="$(block_text "Structure")"
check_field "Structure" "trunk"
UNIT_COUNT="$(printf '%s\n' "$STRUCTURE" | grep -Ec '^- U[0-9]+ +[^[:space:]]' || true)"
[ "$UNIT_COUNT" -ge 1 ] || fail "Structure needs at least one '- U<number> <title>' line"
for field in "reader question" "reader outcome" "evidence" "anchor"; do
  count="$(printf '%s\n' "$STRUCTURE" | grep -Ec "^  - $field:" || true)"
  [ "$count" -ge "$UNIT_COUNT" ] || fail "Structure needs '$field' for every unit"
done

ANCHORS="$(block_text "Anchors")"
ANCHOR_COUNT="$(printf '%s\n' "$ANCHORS" | grep -Ec '^### A[0-9]+ +[^[:space:]]' || true)"
if [ "$ANCHOR_COUNT" -eq 0 ]; then
  printf '%s\n' "$ANCHORS" | grep -Eq '^- none: +[^[:space:]]' || fail "Anchors needs an A<number> block or '- none: <reason>'"
else
  for field in "reader question" "evidence" "selected form" "takeaway" "caveat"; do
    count="$(printf '%s\n' "$ANCHORS" | grep -Ec "^- $field:" || true)"
    [ "$count" -ge "$ANCHOR_COUNT" ] || fail "Anchors needs '$field' for every anchor"
  done
fi

for anchor_id in $(printf '%s\n' "$STRUCTURE" | sed -n 's/^  - anchor: \(A[0-9][0-9]*\)$/\1/p'); do
  printf '%s\n' "$ANCHORS" | grep -Eq "^### $anchor_id +" || fail "Structure references missing anchor: $anchor_id"
done

for source_id in $(printf '%s\n' "$STRUCTURE\n$ANCHORS" | grep -Eo 'S[0-9]+' | sort -u); do
  printf '%s\n' "$SOURCE_IDS" | grep -Fxq "$source_id" || fail "plan references missing source: $source_id"
done

for field in "concept" "selected references" "borrow" "transform" "reject" "clone risk"; do
  check_field "Design Direction" "$field"
done

for field in "locked" "guided" "open"; do check_field "Build Contract" "$field"; done

ACCEPTANCE="$(block_text "Acceptance Tests")"
printf '%s\n' "$ACCEPTANCE" | grep -Eq '^- \[ \] +[^[:space:]]' || fail "Acceptance Tests needs at least one unchecked test"

if [ "$ERRORS" -eq 0 ]; then
  echo "OK: document plan contract valid"
  exit 0
else
  echo "$ERRORS error(s) in plan"
  exit 1
fi
