---
description: Full loop — Codex plans, Claude implements, Codex reviews, Claude hardens. End-to-end Codex+Claude collaboration.
argument-hint: '[--rounds N] [--fresh] [--base <ref>] [--model <model|spark>] [--effort <none|minimal|low|medium|high|xhigh>] [what to build]'
disable-model-invocation: true
allowed-tools: Read, Glob, Grep, Edit, Write, Bash(node:*), Bash(git:*), Bash(mktemp:*), AskUserQuestion
---

The full collaboration loop, composing plan-then-implement with review-loop:

```
Codex plans (read-only)  ->  Claude implements  ->  Codex reviews (read-only)  ->  Claude hardens
```

Codex is read-only at both ends; Claude is the only writer. This is the highest-effort path — use it for substantial, risky, or unfamiliar changes.

Raw slash-command arguments:
`$ARGUMENTS`

Phase 1 — PLAN (delegates to the `codex-plan` skill):
1. If no task text was supplied, ask what to build. Stop until you have it.
2. **Resolve session continuity (no question — default keeps the thread).** Unless `--fresh` is present, run `task-resume-candidate --json`; if `available` is `true`, continue that thread (`RESUME=--resume-last`) and tell the user one line that you are continuing it (and that `--fresh` starts new). Otherwise `RESUME=` (empty). Never use AskUserQuestion for this.
3. Compose the read-only plan prompt: on a fresh thread, the full `codex-plan` `<structured_output_contract>` tightened with `gpt-5-4-prompting`; when continuing, send only the delta instruction. The prompt MUST forbid edits. Write it to a temp file and run Codex read-only (NO `--write`), passing `$RESUME`:
```bash
PF=$(mktemp); cat > "$PF" <<'PROMPT'
... composed plan / delta prompt ...
PROMPT
node "${CLAUDE_PLUGIN_ROOT}/scripts/codex-companion.mjs" task $RESUME --prompt-file "$PF" $MODEL_EFFORT_FLAGS
```
4. Present the plan verbatim. Use `AskUserQuestion` once: `Proceed: build then review (Recommended)` vs `Stop at the plan`. If the user clearly asked for the full loop, proceed directly.

Phase 2 — IMPLEMENT (Claude):
5. Implement the plan's STEPS in order per the `codex-plan` skill's Step 3 — verify each step, surface disagreement with the plan instead of silently following or rewriting it, and stay in scope. Resolve any OPEN QUESTIONS first.

Phase 3 — REVIEW + HARDEN (the review-loop, default 2 rounds; honor `--rounds N`):
6. Run an adversarial Codex review over the freshly implemented changes:
```bash
node "${CLAUDE_PLUGIN_ROOT}/scripts/codex-companion.mjs" adversarial-review "<--base / focus args>"
```
7. Present findings verbatim by severity. If zero actionable findings, the loop has converged — skip to the report.
8. Gate with `AskUserQuestion` (`Fix all` / `Fix critical/high only (Recommended)` / `Stop`), apply only the chosen fixes with per-fix verification, then re-review if rounds remain and fixes were made.

Final report: the plan summary, what was implemented (and any deviation from the plan + why), review rounds run, what was hardened, and residual risk Codex still flags — plus whether the loop converged or hit the round cap.

Failure handling:
- If Codex fails at the plan phase, report it and offer to plan it yourself as an explicit fallback. If Codex fails at the review phase, report it and stop — do not fabricate a review.
- If setup/auth is required, direct the user to `/hukuhaka-codex:setup`.
