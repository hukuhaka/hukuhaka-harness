---
name: audit
description: >
  Analyze codebase for improvement opportunities (large files, dead code,
  duplicates, refactoring, anti-patterns) and add findings to backlog.
  Use when user asks to find issues, code health problems, or improvement items.
  Do NOT use for capturing a single known idea or task (use backlog skill) or
  for tracing a specific bug (use trace skill).
hooks:
  PreToolUse:
    - matcher: "Write"
      hooks:
        - type: command
          command: "printf 'audit only modifies backlog.md via Edit. Do not Write - use Edit on backlog.md instead.' >&2; exit 2"
---

# Audit

Analyze codebase for improvement opportunities via 2-agent pipeline. Format the findings via the bundled script (deterministic priority grouping). Then add confirmed items to backlog.

## Rules

- All `subagent_type` values MUST use `hukuhaka-project-mapper:` prefix (e.g., `hukuhaka-project-mapper:auditor`)
- Do NOT scan code yourself (no Glob, Read, Grep for analysis). Delegate to agents
- On failure: STOP. Do NOT attempt workarounds
- NEVER use the Write tool. Only use Edit to modify backlog.md
- Do NOT format findings yourself — pipe analyzer JSON through the bundled formatter

## Options

- `--focus <category>`: large-files, dead-code, duplicates, refactoring, health, or all (default: all)
- `--threshold <n>`: Line count threshold for large-files category (default: 300)

## Flow

Sequential 2-agent pipeline + script-based formatting + backlog edit. See [audit-pipeline.md](references/audit-pipeline.md) for agent steps.

1. Parse options from user input (defaults: focus=all, threshold=300)
2. **Step 0** — Preflight: run `test -f .claude/backlog.md` via Bash. If missing → "Run `/hukuhaka-project-mapper:map-init` first" and STOP (Step 5 needs it; fail before agents spend their work). Then Read `.claude/backlog.md` so Step 5's Edit has the file in context
3. **Step 1** — Spawn exactly 1 `hukuhaka-project-mapper:auditor` Agent → returns context JSON
4. **Step 2** — Spawn exactly 1 `hukuhaka-project-mapper:analyzer` Agent (improve mode + context from Step 1) → returns findings JSON
5. **Step 3** — Pipe the analyzer's findings JSON through the formatter script via Bash:

   ```
   cat <<'EOF' | python3 ${CLAUDE_PLUGIN_ROOT}/skills/audit/scripts/format-findings.py
   <paste analyzer JSON here verbatim>
   EOF
   ```

   Display the script's stdout verbatim. The script produces the standardized `## Audit Results` block with `### High Priority (N items)`-style groups and a `Stats:` line — do not paraphrase or reformat.

6. **Step 4** — Use AskUserQuestion to ask which findings to add to backlog (all, by priority, or specific items)
7. **Step 5** — For confirmed findings, Edit `.claude/backlog.md` to append under `## Planned` in the matching priority section. Transform each formatter bullet mechanically: `` - `files` title ... `` becomes `` - [ ] `files`: title ... `` (prepend the checkbox, add the colon after the backticked files, keep the rest verbatim — see Backlog Format below)

## Backlog Format

- High → `### High Priority`
- Medium → `### Medium Priority`
- Low → `### Low Priority`
- Format: `- [ ] \`file\`: title [confidence] effort:size — suggestion` (size = small | medium | large)
