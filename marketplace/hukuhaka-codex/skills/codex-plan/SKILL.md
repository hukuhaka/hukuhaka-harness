---
name: codex-plan
description: Internal contract for the plan-then-implement workflow — how to ask Codex (read-only) for a structured implementation plan, and how Claude consumes that plan to implement it
user-invocable: false
---

# Codex Plan -> Claude Implement

Use this skill inside `/hukuhaka-codex:plan` and `/hukuhaka-codex:full`.

The split of labor is fixed:
- Codex produces the PLAN only. It runs read-only (`task` without `--write`). It never edits files.
- Claude does the IMPLEMENTATION, following the plan. Claude is the only writer.

This keeps Codex's strength (a second model's independent design pass) without
handing it the working tree, and keeps Claude accountable for every edit.

## Session continuity — default is to KEEP the thread

Planning is iterative ("refine the plan", "also handle X"), so the default is to
continue the existing Codex thread for this repo rather than ask every time:

- Before composing the prompt, run
  `node "${CLAUDE_PLUGIN_ROOT}/scripts/codex-companion.mjs" task-resume-candidate --json`.
- If `available` is `true` and the user did NOT pass `--fresh`: continue that
  thread — pass `--resume-last` to `task` and send only the DELTA instruction
  (Codex already holds the prior plan + contract). Tell the user in one line that
  you are continuing it and that `--fresh` starts a new thread. Do NOT use
  AskUserQuestion to ask continue-vs-new; keeping the thread is the default.
- If `available` is `false` or the user passed `--fresh`: start a new thread and
  send the full contract below.

The thread lives in Codex (not the Claude session), is scoped to this repo, and
survives Claude session restarts — so "keep the thread" works across sessions.

## Step 1 — Build the plan prompt

Compose a single read-only Codex `task` prompt. Use the
[gpt-5-4-prompting](../gpt-5-4-prompting/SKILL.md) skill to tighten it. The
prompt MUST forbid edits and MUST request the plan in the contract below.

Recommended block layout (XML tags, per gpt-5-4-prompting conventions):

```
<task>
{the user's goal, plus the relevant files / failure context Claude already knows}
</task>

<role>
You are producing an implementation PLAN for a separate engineer (Claude) to
execute. You are read-only. Do NOT edit, create, or delete any files. Do NOT
run write commands. Investigate the repository as needed, then return the plan.
</role>

<structured_output_contract>
Return exactly these sections, in order:

1. GOAL — one or two sentences on the end state.
2. ASSUMPTIONS — anything you inferred that, if wrong, changes the plan.
3. FILES — each file to create/modify/delete, with a one-line reason. Use exact
   repo-relative paths.
4. STEPS — an ordered, numbered list. Each step is a concrete, self-contained
   change small enough to verify on its own. Reference the file(s) it touches.
5. RISKS — failure modes, edge cases, and anything easy to get wrong.
6. VERIFICATION — for each risky step or the plan as a whole, how to prove it
   works (specific test to write/run, command to execute, or observable check).
7. OPEN QUESTIONS — high-risk unknowns that should be resolved before building,
   or "none".
</structured_output_contract>

<grounding_rules>
Anchor every file path and claim to what you actually observed in the repo. If
a path or behavior is a guess, mark it as an assumption, do not state it as
fact.
</grounding_rules>
```

Write this prompt to a temp file and pass it with `--prompt-file` (long
structured prompts do not survive shell quoting as a positional). Do NOT pass
`--write` — read-only is the whole point.

## Step 2 — Run Codex read-only

```bash
node "${CLAUDE_PLUGIN_ROOT}/scripts/codex-companion.mjs" task --prompt-file <tmp> [--model <m>] [--effort <e>]
```

Return Codex's plan to the user verbatim first, before any implementation. The
plan is a deliverable on its own — the user may want to adjust it.

## Step 3 — Implement the plan (Claude)

Once the user approves the plan (or asked for end-to-end build), Claude
implements it directly. Rules:

- Follow the plan's STEPS in order. Implement each step, then run its
  VERIFICATION before moving on.
- The plan is advice from another model, not ground truth. If a step is wrong,
  unsafe, or contradicts the actual code, STOP and surface the disagreement to
  the user — do not silently "fix" the plan or blindly follow it off a cliff.
- If the plan listed OPEN QUESTIONS, resolve them (ask the user or investigate)
  before building the dependent steps.
- Stay within the plan's scope. Do not bolt on unrelated refactors.
- Preserve the plan's exact file paths; if reality differs, say so.
- Report at the end: which steps were implemented, which verifications passed,
  and any deviation from the plan and why.

## Failure handling

- If Codex was never successfully invoked, or returned no usable plan, report
  that and stop. Do NOT substitute a Claude-authored plan silently — tell the
  user Codex failed and offer to plan it yourself as an explicit fallback.
- If Codex reports that setup or authentication is required, direct the user to
  `/hukuhaka-codex:setup`.
