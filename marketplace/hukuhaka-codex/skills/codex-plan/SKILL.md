---
name: codex-plan
description: Canonical plan-then-implement contract for obtaining a grounded read-only Codex plan and having Claude implement it with per-step verification
user-invocable: false
---

# Codex Plan -> Claude Implement

Use this skill inside `/hukuhaka-codex:plan` and the plan phase of
`/hukuhaka-codex:full`. This file is the single source for the plan prompt,
thread selection, plan validation, and Claude implementation rules. Commands
should orchestrate these phases, not duplicate the contract.

## Fixed division of labor

- Codex investigates and produces the plan in a read-only `plan` workflow.
- Claude presents and validates the plan, then implements only after approval.
- Codex never edits files in this workflow. Never pass `--write`.
- The plan is advice from a second model, not ground truth.

## Phase 1: Select the plan thread

Planning may continue across Claude sessions, but it must never resume a
generic rescue, duel, or debate task.

1. Unless the user passed `--fresh`, run:

   ```bash
   node "${CLAUDE_PLUGIN_ROOT}/scripts/codex-companion.mjs" task-resume-candidate --workflow plan --json
   ```

2. If a candidate exists, continue its exact `candidate.threadId` with
   `--resume-thread <id>`. Tell the user which plan thread is continuing and
   that `--fresh` starts a new one. Do not ask continue-vs-new.
3. If no plan candidate exists, or `--fresh` was passed, start a fresh plan
   thread. Legacy unclassified task threads are not plan candidates.

## Phase 2: Build the Codex prompt

For a fresh thread, use the complete contract below. Include only context
Claude already knows; Codex should inspect the repository itself.

```xml
<task>
{the user's concrete goal and the relevant failure or repository context}
</task>

<role>
Produce an implementation plan for Claude to execute. You are read-only.
Do not edit, create, rename, or delete files, and do not run write commands.
Investigate the repository as needed, then return the plan.
</role>

<structured_output_contract>
Return exactly these sections in order:

1. GOAL - one or two sentences describing the verified end state.
2. ASSUMPTIONS - inferred facts that would materially change the plan if wrong.
3. FILES - exact repo-relative paths to create, modify, rename, or delete, each
   with a one-line reason.
4. STEPS - ordered, concrete changes. Each step names its files and is small
   enough to verify independently.
5. RISKS - material failure modes, edge cases, migration concerns, and likely
   regressions.
6. VERIFICATION - a specific test, command, or observable check for each risky
   step and for the completed plan.
7. OPEN QUESTIONS - only high-risk unknowns that must be resolved before
   implementation, or "none".
</structured_output_contract>

<default_follow_through_policy>
Use the most reasonable low-risk interpretation and keep investigating until
the plan is implementation-ready. Ask only when missing information changes
correctness, safety, or an irreversible action.
</default_follow_through_policy>

<completeness_contract>
Cover the complete requested behavior, including necessary tests, compatibility
surfaces, and documentation. Exclude unrelated cleanup and speculative work.
</completeness_contract>

<grounding_rules>
Anchor every path and behavioral claim to repository evidence you inspected.
Label inferences as assumptions. Do not invent files, APIs, or current behavior.
</grounding_rules>

<missing_context_gating>
Retrieve missing repository facts with read-only tools. If a high-risk fact
cannot be established, put it in OPEN QUESTIONS instead of guessing.
</missing_context_gating>

<verification_loop>
Before finalizing, check that every step advances the GOAL, every listed file
exists or is explicitly new, risky behavior has verification, and the plan does
not require writes from Codex.
</verification_loop>

<action_safety>
Keep the plan tightly scoped. Identify destructive or irreversible actions
explicitly and require user approval before Claude performs them.
</action_safety>
```

For an existing plan thread, send only the user's delta or refinement plus a
short reminder that the run remains read-only. Do not restate the full contract
unless the requested direction materially changes it.

Write the prompt to a temporary file. Long structured prompts must use
`--prompt-file`; do not pass them through positional shell quoting.

## Phase 3: Run Codex read-only

Fresh plan:

```bash
node "${CLAUDE_PLUGIN_ROOT}/scripts/codex-companion.mjs" task --workflow plan --prompt-file <tmp> [--model <m>] [--effort <e>]
```

Continued plan:

```bash
node "${CLAUDE_PLUGIN_ROOT}/scripts/codex-companion.mjs" task --workflow plan --resume-thread <thread-id> --prompt-file <tmp> [--model <m>] [--effort <e>]
```

Preserve the returned thread ID. Do not use generic `--resume-last` for plans.

## Phase 4: Validate and present the plan

Before implementation, check that the response contains all seven required
sections, uses concrete paths, separates assumptions from observed facts, and
provides meaningful verification. If the response is malformed or incomplete:

1. send one concise correction request to the same exact plan thread;
2. ask only for the missing or invalid sections;
3. stop and report failure if the corrected response is still unusable.

Present the usable Codex plan verbatim before adding Claude's assessment. Do
not silently rewrite it into a Claude-authored plan.

## Phase 5: Approval and implementation

- If the user requested `--plan-only`, stop after presenting the plan.
- If the user already requested end-to-end implementation, proceed.
- Otherwise ask once whether to implement the plan.
- Resolve OPEN QUESTIONS before their dependent steps.
- Implement STEPS in order and run each step's VERIFICATION before continuing.
- Re-check the actual code before every edit. If the plan is wrong, unsafe, or
  stale, stop and surface the disagreement; do not blindly follow or silently
  repair it.
- Preserve scope, not mistaken paths. If reality differs from the plan, explain
  the deviation and use the correct path only after establishing evidence.
- Report implemented steps, passed checks, deviations, and residual risk.

## Failure handling

- If Codex was not invoked or returned no usable plan after one correction
  attempt, report the failure and stop.
- Offer a Claude-authored plan only as an explicit fallback; never substitute
  one silently.
- If setup or authentication is required, direct the user to
  `/hukuhaka-codex:setup`.
