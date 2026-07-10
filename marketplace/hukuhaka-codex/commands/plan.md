---
description: Codex drafts a grounded read-only implementation plan, then Claude implements it with per-step verification
argument-hint: '[--plan-only] [--fresh] [--model <model|spark>] [--effort <none|minimal|low|medium|high|xhigh>] [what to plan and build]'
disable-model-invocation: true
allowed-tools: Skill, Read, Glob, Grep, Edit, Write, Bash(node:*), Bash(git:*), Bash(mktemp:*), Bash(cat:*), AskUserQuestion
---

Run the plan-then-implement workflow using the `codex-plan` skill as the
canonical contract. Load that skill before taking action. Do not recreate its
prompt schema, thread policy, validation rules, or implementation rules here.

Raw slash-command arguments:
`$ARGUMENTS`

1. If no task text was supplied, ask what to plan and build, then stop.
2. Parse `--plan-only`, `--fresh`, `--model`, and `--effort` as orchestration
   controls; do not include those flags in the natural-language task.
3. Follow `codex-plan` Phases 1-4 exactly:
   - select only a `--workflow plan` candidate;
   - use the full canonical prompt for a fresh thread or only the delta for an
     existing exact thread;
   - invoke `task --workflow plan` read-only, never `--write`;
   - preserve explicit model/effort options;
   - validate the seven-section result and allow at most one correction turn.
4. Present the usable Codex plan verbatim.
5. Follow `codex-plan` Phase 5 for plan-only handling, approval, Claude
   implementation, per-step verification, deviations, and final reporting.

On setup, authentication, invocation, or malformed-plan failure, apply the
`codex-plan` failure rules. Never silently replace Codex's failed plan with a
Claude-authored plan.
