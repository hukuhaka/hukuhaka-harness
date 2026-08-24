# hukuhaka-codex

A Codex + Claude collaboration harness for Claude Code. It lets a second model
(OpenAI Codex / GPT-5.x) plan, review, and diagnose alongside Claude through a
shared runtime, so you get a genuine second-model perspective without leaving
the session.

This is a modified Apache-2.0 distribution of OpenAI's official `codex` plugin.
See [`NOTICE`](NOTICE) and [`UPSTREAM-SYNC.md`](UPSTREAM-SYNC.md) for provenance.

Current local version: `0.4.1`. The fully incorporated official baseline is
`codex-plugin-cc` v1.0.4; upstream has been audited through v1.0.6 with later
changes adopted selectively. This plugin remains Apache-2.0 even though the
containing repository uses MIT for its other components.

## Mental model (read this first)

Three rules govern every interaction:

1. **Codex plans and reviews; Claude writes.** In the planning and review
   workflows Codex runs read-only and Claude is the only writer. This keeps a
   second model's independent design pass without giving it edit authority.
2. **Rescue is read-only by default.** `codex-rescue` hands a debugging or
   root-cause task to Codex. A *proactive* handoff (one you did not explicitly
   request) always runs read-only — it returns diagnosis or a plan, never a
   silent file edit. Codex writes only when you explicitly ask it to.
3. **The Stop review-gate is opt-in.** When enabled, Codex auto-reviews each
   turn's code changes before Claude stops. It is **OFF by default** (it adds
   latency and cost to every code-change turn). Enable per-repo with
   `/hukuhaka-codex:setup --enable-review-gate`.

### Proactive use — what "used when needed without asking" means here

Codex has two proactive shapes, with opposite risk profiles:

- **Proactive review / diagnosis (safe, read-only).** The Stop gate
  auto-reviews; `codex-rescue` auto-diagnoses when Claude is stuck. Neither
  edits files. This is the recommended form of "used without asking."
- **Proactive write (avoid as a default).** A model silently delegating
  *implementation* with write access is the pattern this project tried and
  removed — the orchestration decision (when/what to delegate) is the
  unreliable part, not the script. The defaults above keep proactive use in
  the read-only lane.

Three opt-in dials let you tune how proactive the safe lane is (all per-repo,
all off by default):

- `setup --enable-review-gate` — Codex reviews each code-change turn and
  **blocks** the stop until findings are addressed.
- `setup --report-only` — same review, but **never blocks**; findings are
  surfaced as a note (you still wait for the review at stop time).
- `setup --enable-stuck-detector` — after three Bash failures within five minutes, Claude is
  **nudged** to consider `/hukuhaka-codex:rescue` or `/hukuhaka-codex:duel`.
  Successful commands are not observed, and detection never invokes Codex on its own. `codex-rescue` itself
  hands off only on finite triggers (a repeated-failure streak, an
  un-understood subsystem after search, a high-risk design decision, or an
  explicit second-opinion request), never on a vague feeling of being stuck.

After a blocking Stop review continues the turn, the hook observes
`stop_hook_active=true`, reports only any still-running Codex task, and allows
the next Stop without paying for or looping through a second review.

## Commands

| Command | What it does | Model-invocable? |
|---|---|---|
| `/hukuhaka-codex:setup` | Check Codex CLI readiness; toggle the review-gate | yes |
| `/hukuhaka-codex:rescue` | Hand investigation / a fix request to the Codex rescue subagent | yes |
| `/hukuhaka-codex:plan` | Codex produces a read-only implementation plan; Claude implements | user-only |
| `/hukuhaka-codex:full` | Full loop: Codex plans → Claude implements → Codex reviews → Claude hardens | user-only |
| `/hukuhaka-codex:review` | Codex code review against local git state | user-only |
| `/hukuhaka-codex:adversarial-review` | Review that challenges the approach and design choices | user-only |
| `/hukuhaka-codex:review-loop` | Iterate review → fix → re-review until clean | user-only |
| `/hukuhaka-codex:duel` | Dual-solve: Codex and Claude solve independently, then Claude synthesizes | user-only |
| `/hukuhaka-codex:debate` | Deep debate: both solve, then cross-examine each other's solutions over bounded rounds; surfaces agreement and remaining disputes | user-only |
| `/hukuhaka-codex:transfer` | Import the current Claude transcript into a persistent, resumable Codex thread | user-only |
| `/hukuhaka-codex:status` | Show active/recent Codex jobs and review-gate status | user-only |
| `/hukuhaka-codex:result` | Fetch a finished Codex job's output | user-only |
| `/hukuhaka-codex:cancel` | Cancel a running Codex job | user-only |

"User-only" commands set `disable-model-invocation: true` — Claude will not
trigger them on its own; you invoke them explicitly.

`plan` and the plan phase of `full` use the local `codex-plan` contract. Plan
threads are tracked separately from rescue, duel, and debate tasks, so an
unrelated Codex thread cannot be resumed as planning context. General rescue
and independent-solve prompts use the model-neutral `codex-prompting` skill.

## Setup

```
/hukuhaka-codex:setup
```

Installs / verifies the Codex CLI and reports auth state. If Codex is installed
but not logged in, run `!codex login`.
