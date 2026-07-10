---
description: Full loop - Codex plans, Claude implements, Codex reviews, Claude hardens
argument-hint: '[--rounds N] [--fresh] [--base <ref>] [--model <model|spark>] [--effort <none|minimal|low|medium|high|xhigh>] [what to build]'
disable-model-invocation: true
allowed-tools: Skill, Read, Glob, Grep, Edit, Write, Bash(node:*), Bash(git:*), Bash(mktemp:*), Bash(cat:*), AskUserQuestion
---

Run the full collaboration loop:

```text
Codex plans read-only -> Claude implements -> Codex reviews read-only -> Claude hardens
```

Load `codex-plan` before taking action. It is the canonical contract for the
first two phases; do not duplicate or weaken its prompt, thread, validation,
approval, or implementation rules.

Raw slash-command arguments:
`$ARGUMENTS`

## Phase 1: Plan

1. If no task text was supplied, ask what to build, then stop.
2. Parse `--rounds`, `--fresh`, `--base`, `--model`, and `--effort` as
   orchestration controls; do not include them in the task text.
3. Follow `codex-plan` Phases 1-4 exactly. Use `task --workflow plan`, resume
   only an exact plan thread, keep Codex read-only, validate all seven sections,
   and allow at most one correction turn.
4. Present the usable plan verbatim. Unless the user already requested the full
   end-to-end loop, ask once whether to proceed with build and review.

## Phase 2: Implement

5. Follow `codex-plan` Phase 5. Claude is the only writer. Resolve open
   questions, implement steps in order, verify each step, and surface any
   disagreement with the plan instead of silently repairing or blindly
   following it.

## Phase 3: Review and harden

6. Run an adversarial Codex review against the implemented changes, preserving
   `--base` and explicit model/effort options where supported:

   ```bash
   node "${CLAUDE_PLUGIN_ROOT}/scripts/codex-companion.mjs" adversarial-review "<review args>"
   ```

7. Present findings verbatim in severity order. If there are no actionable
   findings, the loop has converged.
8. Otherwise ask once which findings to fix: all, critical/high only, or stop.
   Apply only the selected fixes with per-fix verification.
9. Re-review until clean or the round limit is reached. Default to two rounds.

Report the plan outcome, implemented steps and deviations, verification, review
rounds, hardening changes, residual findings, and whether the loop converged.
If Codex fails in either the plan or review phase, report the failure and stop;
never fabricate the missing result.
