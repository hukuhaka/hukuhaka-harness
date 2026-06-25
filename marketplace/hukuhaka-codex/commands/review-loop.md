---
description: Iterative review loop — Codex adversarially reviews your work, Claude fixes, repeat until clean
argument-hint: '[--rounds N] [--base <ref>] [--model <model|spark>] [focus ...]'
disable-model-invocation: true
allowed-tools: Read, Glob, Grep, Edit, Write, Bash(node:*), Bash(git:*), AskUserQuestion
---

Run a review loop: Codex challenges the current changes, Claude applies fixes, then re-reviews — until the review is clean or the round budget is spent.

This is the "Claude builds, Codex pressure-tests, Claude hardens" pattern. Codex stays read-only the whole time; Claude is the only writer.

Raw slash-command arguments:
`$ARGUMENTS`

Setup:
- Default round budget is 2. Honor `--rounds N` if present.
- `--base <ref>` and trailing focus text are passed through to the review, same as `/hukuhaka-codex:adversarial-review`.

Loop (repeat up to the round budget):

1. **Review.** Run an adversarial Codex review over the current state:
```bash
node "${CLAUDE_PLUGIN_ROOT}/scripts/codex-companion.mjs" adversarial-review "<--base / focus args>"
```
2. **Triage.** Present Codex's findings verbatim, ordered by severity (per `codex-result-handling`). If there are zero actionable findings, declare the loop converged and STOP.
3. **Gate.** Use `AskUserQuestion` once: which findings to fix this round — `Fix all`, `Fix critical/high only (Recommended)`, or `Stop`. Auto-applying fixes without this gate is forbidden.
4. **Fix.** Implement only the chosen fixes. Stay scoped to the findings — do not refactor unrelated code. After each fix, run the relevant test/check.
5. **Re-review.** If rounds remain and fixes were made, go back to step 1 against the new state. The next review should see the fixes applied.

Stop conditions:
- The review comes back with no actionable findings (converged), or
- The round budget is exhausted, or
- The user chooses `Stop`.

Final report: rounds run, what was fixed each round, what (if anything) Codex still flags as residual risk, and whether the loop converged or hit the round cap.

Failure handling:
- If Codex was never successfully invoked, report it and stop — do not turn a failed review into a blind Claude-side rewrite.
- If setup/auth is required, direct the user to `/hukuhaka-codex:setup`.
