---
description: Check whether the local Codex CLI is ready and toggle the stop-time review gate, report-only review, and the stuck-detector
argument-hint: '[--enable-review-gate|--report-only|--disable-review-gate] [--enable-stuck-detector|--disable-stuck-detector]'
allowed-tools: Bash(node:*), Bash(npm:*), AskUserQuestion
---

Run:

```bash
node "${CLAUDE_PLUGIN_ROOT}/scripts/codex-companion.mjs" setup --json $ARGUMENTS
```

Toggles (all opt-in, per-repo):
- `--enable-review-gate` — Codex reviews each code-change turn and BLOCKS the stop until a finding is addressed.
- `--report-only` — same review, but it never blocks: findings are surfaced as a note and you can stop freely (still waits for the review at stop time).
- `--disable-review-gate` — turn the stop-time review off.
- `--enable-stuck-detector` / `--disable-stuck-detector` — after a streak of Bash failures, nudge Claude to consider `/hukuhaka-codex:rescue` or `/hukuhaka-codex:duel`. Detection only; it never invokes Codex on its own.

If the result says Codex is unavailable and npm is available:
- Use `AskUserQuestion` exactly once to ask whether Claude should install Codex now.
- Put the install option first and suffix it with `(Recommended)`.
- Use these two options:
  - `Install Codex (Recommended)`
  - `Skip for now`
- If the user chooses install, run:

```bash
npm install -g @openai/codex
```

- Then rerun:

```bash
node "${CLAUDE_PLUGIN_ROOT}/scripts/codex-companion.mjs" setup --json $ARGUMENTS
```

If Codex is already installed or npm is unavailable:
- Do not ask about installation.

Output rules:
- Present the final setup output to the user.
- If installation was skipped, present the original setup output.
- If Codex is installed but not authenticated, preserve the guidance to run `!codex login`.
