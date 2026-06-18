#!/usr/bin/env bash
# validate-spec.sh — optional self-check for a report plan spec.md
# usage: validate-spec.sh [<spec.md>]
#   no path arg → read spec content from stdin
#   path arg    → read the on-disk file
# contract source: references/spec-schema.md (Frame + Contents blocks)
#   (keep FRAME_FIELDS below in sync with spec-schema.md)
#
# This is a SELF-CHECK, not a gate: it is not wired to any hook and nothing blocks
# a write on failure. It exists so a stage can sanity-check its own output.
# Validates only the blocks PRESENT in the spec (it grows across the two stages).
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

# Contract: the four REQUIRED Frame lines (form is optional).
FRAME_FIELDS=( "purpose" "audience" "prose level" "design direction" )

has_block(){ printf '%s\n' "$SPEC" | grep -Eq "^## $1"; }
field_line(){ printf '%s\n' "$SPEC" | grep -E "^- $1:" | head -1; }

# A FILLED line never contains '<' — the template stub is "<what the report is for ...>".
check_frame(){
  local line val
  line="$(field_line "$1")"
  [ -n "$line" ] || { fail "Frame field missing: $1"; return; }
  case "$line" in *'<'*) fail "Frame field unfilled (<...> placeholder): $1"; return ;; esac
  val="${line#*:}"
  printf '%s' "$val" | grep -Eq '[^[:space:]]' || fail "Frame field empty: $1"
}

# Frame block
if has_block "Frame"; then
  for f in "${FRAME_FIELDS[@]}"; do check_frame "$f"; done
fi

# Contents block — need at least one "- NN <title>" section line.
if has_block "Contents"; then
  if ! printf '%s\n' "$SPEC" | grep -Eq '^- [0-9]+ +\S'; then
    fail "Contents block present but no section lines (need '- 01 <title> — figures: ...')"
  fi
fi

if [ "$ERRORS" -eq 0 ]; then
  f=absent; c=absent
  has_block "Frame" && f=present
  has_block "Contents" && c=present
  echo "OK: plan valid (frame=$f, contents=$c)"
  exit 0
else
  echo "$ERRORS error(s) in plan"
  exit 1
fi
