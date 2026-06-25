---
description: Dual-solve and synthesize — Codex and Claude each solve the problem independently, then Claude merges the best of both
argument-hint: '[--model <model|spark>] [--effort <none|minimal|low|medium|high|xhigh>] [the problem to solve two ways]'
disable-model-invocation: true
allowed-tools: Read, Glob, Grep, Edit, Write, Bash(node:*), Bash(git:*), Bash(mktemp:*), AskUserQuestion
---

Dual-solve: get two independent solutions — one from Codex, one from Claude — then synthesize a better answer than either alone. The point is perspective diversity: two models miss different things.

Codex solves read-only (it proposes an approach/patch-plan, it does NOT edit files). Claude solves independently. Claude then compares and merges. Claude is the only writer.

Raw slash-command arguments:
`$ARGUMENTS`

Steps:

1. If no problem was supplied, ask for it. Stop until you have it.
2. **Claude's pass — first and independent.** Before consulting Codex, form your own solution: the approach, the key decisions, and the concrete changes you would make. Write it down so it is not contaminated by Codex's answer. Do NOT implement yet.
3. **Codex's pass — independent.** Compose a read-only prompt asking Codex to solve the SAME problem and return its approach as a concrete plan (goal, files, steps, risks) — explicitly forbidding edits. Tighten it with `gpt-5-4-prompting`. Write it to a temp file and run:
```bash
PF=$(mktemp); cat > "$PF" <<'PROMPT'
... composed solve prompt (read-only, return approach + concrete steps) ...
PROMPT
node "${CLAUDE_PLUGIN_ROOT}/scripts/codex-companion.mjs" task --prompt-file "$PF" $MODEL_EFFORT_FLAGS
```
4. **Compare.** Present a short side-by-side: where the two solutions agree, where they diverge, and the tradeoffs of each divergence. Be specific — name the decision, not just "they differ".
5. **Synthesize.** Recommend a merged solution that takes the stronger choice at each divergence, and say *why* each choice won. If the two genuinely conflict on something the user should decide, use `AskUserQuestion` to let them pick.
6. **Gate before building.** Use `AskUserQuestion` once: `Implement the synthesized solution (Recommended)` vs `Stop at the comparison`. If the user clearly asked to build, you may proceed directly.
7. If implementing, build the synthesized solution with verification per step, staying in scope. Report what was built and which parts came from which solution.

Failure handling:
- If Codex was never successfully invoked, say so and offer to proceed with Claude's solution alone as an explicit fallback — do not silently present a single-model answer as a synthesis.
- If setup/auth is required, direct the user to `/hukuhaka-codex:setup`.
