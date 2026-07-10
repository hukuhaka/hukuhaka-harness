---
description: Deep debate — Codex and Claude each solve, then cross-examine each other's actual solutions over bounded rounds, surfacing agreement and the disputes that remain
argument-hint: '[--rounds N] [--model <model|spark>] [--effort <none|minimal|low|medium|high|xhigh>] [the problem to debate]'
disable-model-invocation: true
allowed-tools: Read, Glob, Grep, Edit, Write, Bash(node:*), Bash(git:*), Bash(mktemp:*), AskUserQuestion
---

Debate, not parallel submission. Both models solve, then each is shown the
OTHER's actual solution and made to attack it and defend its own, for a bounded
number of rounds. The goal is not consensus — it is a pressure-tested answer
plus an honest map of what the two models still disagree on.

This is the deeper sibling of `/hukuhaka-codex:duel`. Duel keeps the two
solutions independent (perspective diversity, no cross-talk); debate
deliberately crosses them so each critiques the other. Use debate when the
problem is contested or high-stakes and you want the disagreement stress-tested,
not when you just want two independent takes.

Codex stays read-only the whole time (it argues and revises a plan, it never
edits files). Claude is the only writer.

Raw slash-command arguments:
`$ARGUMENTS`

Setup:
- Cross-examination round budget defaults to 2. Honor `--rounds N`; hard-cap at 3 (debate past round 3 rarely adds value and burns Codex calls).
- Strip `--rounds`, `--model`, `--effort` as routing controls; the rest is the problem statement. If no problem was supplied, ask for it and stop until you have it.
- Build `$MODEL_EFFORT_FLAGS` from `--model` / `--effort` exactly as `/hukuhaka-codex:duel` does (map `spark` to `gpt-5.3-codex-spark`). Apply the same flags to every Codex call below.

Stance you must hold for the whole debate:
- Agreement is NOT the target and agreement is NOT evidence of correctness. Two models tend to converge socially — one defers — and can agree fast and wrong. Do not steer toward consensus.
- A stable, well-argued disagreement is a valid and useful terminal state. Surface it; do not paper over it.
- Keep each side's words intact. When you report Codex's position, use its own claims; do not soften or merge them prematurely.

### Round 1 — independent solutions

1. **Claude solves first, uncontaminated.** Before invoking Codex, write down your own solution: approach, key decisions, concrete changes, and the one or two points you are least sure about. Do NOT implement.
2. **Codex solves independently.** Compose a read-only prompt (tighten it with `codex-prompting`) asking Codex to solve the SAME problem and return a concrete plan (goal, files, steps, risks), edits forbidden. This first call opens the Codex thread that later rounds resume:
```bash
PF=$(mktemp); cat > "$PF" <<'PROMPT'
... composed solve prompt (read-only, return approach + concrete steps + the parts you are least confident about) ...
PROMPT
node "${CLAUDE_PLUGIN_ROOT}/scripts/codex-companion.mjs" task --prompt-file "$PF" $MODEL_EFFORT_FLAGS
```
3. Record both R1 positions verbatim enough to diff against later rounds. **Also capture the Codex thread id** from the R1 output — the line `Thread ready (<id>)`. Save it as `$TID`. Every later round resumes THIS exact thread with `--resume-thread "$TID"`, not `--resume-last` — `--resume-last` resolves "the latest Codex thread for the repo" and would silently jump to the wrong thread if any other Codex call (another debate, a rescue, a review) lands between rounds.

### Cross-examination rounds (repeat up to the round budget)

Each round is one exchange where each side sees the other's CURRENT position and responds to it.

4. **Codex cross-examines Claude.** Send Codex the other side's actual solution (full text, not a paraphrase) and make it adversarial. Resume the SAME Codex thread with `--resume-thread "$TID"` (the id captured in step 3) so it argues with memory of its own prior reasoning and cannot be redirected to another thread:
```bash
PF=$(mktemp); cat > "$PF" <<'PROMPT'
Here is the other solver's current solution to the same problem:
<paste Claude's current position verbatim>

Cross-examine it. Be specific and grounded:
- Where is it wrong, unsafe, or incomplete? Cite the exact decision, not "it differs".
- What did it get right that your plan missed? Concede those explicitly.
- Revise YOUR plan in light of this, or defend it unchanged and say why.
Return: (a) concrete objections, (b) concessions, (c) your updated position.
Do not edit any files.
PROMPT
node "${CLAUDE_PLUGIN_ROOT}/scripts/codex-companion.mjs" task --prompt-file "$PF" --resume-thread "$TID" $MODEL_EFFORT_FLAGS
```
5. **Claude cross-examines Codex.** In your own reasoning, do the symmetric thing against Codex's current position: name where Codex is wrong/unsafe/incomplete, concede what Codex got right that you missed, and revise or defend your own position. Be as hard on yourself as on Codex.
6. **Convergence check (this is the stop logic).** Compare each side's updated position to its position at the start of this round:
   - If NEITHER side changed materially this round → the debate has stabilized. STOP, whether or not they agree. A stable disagreement is a terminal state, not a failure.
   - If the round budget is now exhausted → STOP.
   - Otherwise → go back to step 4 with the updated positions.

### Resolution

7. **Map the outcome.** Present three explicit buckets:
   - **Settled** — points both sides now agree on (and, briefly, who moved and why — so the user can sanity-check that it wasn't a soft cave).
   - **Still disputed** — points where they did not converge. Give BOTH positions in their own terms, plus the crux of the disagreement.
   - **Claude's synthesis** — your recommended answer, clearly labeled as Claude's call, taking the stronger choice at each settled point.
8. **User gate on genuine forks.** For each item in "Still disputed" that the user should actually decide, use `AskUserQuestion` (recommend an option, but make the disagreement visible). Do not resolve a genuine value/judgment fork silently.
9. **Gate before building.** Use `AskUserQuestion` once: `Implement the resolved solution (Recommended)` vs `Stop at the debate map`. If the user clearly asked to build, you may proceed directly.
10. If implementing, build it with verification per step, staying in scope. Report what was built and which parts came from which side (including anything adopted from the losing position).

Final report: rounds run, whether the debate converged or hit the cap, what each side conceded, and what remains genuinely disputed.

Failure handling:
- If Codex was never successfully invoked at Round 1, say so and offer to proceed with Claude's solution alone as an explicit fallback — do not present a single-model answer as a debate.
- If Codex drops out mid-debate (a later `--resume-thread` fails), report the last good round, present the debate map up to that point, and do not fabricate Codex's side of an unfinished round.
- If setup/auth is required, direct the user to `/hukuhaka-codex:setup`.
