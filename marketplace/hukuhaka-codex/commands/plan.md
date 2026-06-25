---
description: Codex (read-only) drafts a structured implementation plan, then Claude implements it
argument-hint: '[--plan-only] [--fresh] [--model <model|spark>] [--effort <none|minimal|low|medium|high|xhigh>] [what to plan and build]'
disable-model-invocation: true
allowed-tools: Read, Glob, Grep, Edit, Write, Bash(node:*), Bash(git:*), Bash(mktemp:*), AskUserQuestion
---

Plan-then-implement: hand the design pass to Codex (read-only), then implement the result yourself.

Use the `codex-plan` skill for the full contract. The division of labor is fixed:
**Codex produces the plan only (read-only, never edits); Claude is the only writer.**

Raw slash-command arguments:
`$ARGUMENTS`

Steps:

1. If no task text was supplied, ask the user what to plan and build. Stop until you have it.
2. **Resolve session continuity (no question asked — default is to keep the thread).** Unless the arguments include `--fresh`, check for a resumable Codex thread for this repo:
```bash
node "${CLAUDE_PLUGIN_ROOT}/scripts/codex-companion.mjs" task-resume-candidate --json
```
   - If `available` is `true` and `--fresh` was NOT passed: **continue that thread.** Set `RESUME=--resume-last` and tell the user one line: "Continuing the existing Codex thread (`<candidate.summary>`); pass `--fresh` to start a new one." Do NOT use AskUserQuestion for this.
   - If `available` is `false`, or `--fresh` was passed: start a new thread. Set `RESUME=` (empty).
3. Gather the minimal context Claude already knows about the goal (relevant files, the failure, the feature). Do not over-investigate — Codex will explore the repo itself.
4. Compose the read-only plan prompt:
   - **Fresh thread:** the full plan per the `codex-plan` skill's `<structured_output_contract>`, tightened with `gpt-5-4-prompting`. The prompt MUST forbid edits.
   - **Continuing a thread:** send only the DELTA — the new instruction or refinement (e.g. "revise the plan to also handle X"). Codex already has the prior plan and contract in the thread; do not restate the whole contract unless the direction changed materially. Still forbid edits.
5. Write that prompt to a temp file:
```bash
PF=$(mktemp); cat > "$PF" <<'PROMPT'
... composed plan / delta prompt ...
PROMPT
```
6. Run Codex read-only (NO `--write`). Pass `$RESUME` and preserve `--model` / `--effort` if the user gave them:
```bash
node "${CLAUDE_PLUGIN_ROOT}/scripts/codex-companion.mjs" task $RESUME --prompt-file "$PF" $MODEL_EFFORT_FLAGS
```
7. Present Codex's plan to the user **verbatim** first. The plan is a deliverable on its own.
8. Decide whether to build:
   - If the arguments include `--plan-only`, STOP after presenting the plan. Do not implement.
   - Otherwise use `AskUserQuestion` once: `Implement this plan (Recommended)` vs `Stop here, plan only`. If the user's request clearly asked to build end-to-end, you may skip the question and proceed.
9. If implementing, follow the `codex-plan` skill's Step 3: implement each STEP in order, run its VERIFICATION before the next, and surface any disagreement with the plan instead of silently following or rewriting it. Stay within the plan's scope.
10. Report which steps were implemented, which verifications passed, and any deviation from the plan and why.

Failure handling:
- If Codex was never successfully invoked or returned no usable plan, report that and stop. Do not silently substitute a Claude-authored plan — offer to plan it yourself only as an explicit fallback the user accepts.
- If setup/auth is required, direct the user to `/hukuhaka-codex:setup`.
