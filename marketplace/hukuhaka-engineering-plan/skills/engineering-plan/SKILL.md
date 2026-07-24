---
name: engineering-plan
description: Use for explicit engineering planning or plan-mode requests involving multiple files or layers, public APIs, CLIs, schemas, migrations, risky refactors, or multi-step verification. Do not use for routine local edits, visual-document planning, or hukuhaka-codex plan/full workflows.
---

# Engineering Plan Protocol

Produce a repository-grounded, decision-complete plan that another engineer or
agent can execute without making hidden product or implementation decisions.

Planning is read-only. Do not edit implementation files, generate tracked
artifacts, stage changes, commit, push, or perform lifecycle mutations while
using this skill.

## 1. Ground the plan

- Read every applicable repository instruction before planning.
- Inspect the current implementation, adjacent tests, generated sources,
  documentation, and verified repository commands.
- Inspect Git state and branch ancestry when worktree safety or multi-branch
  execution matters.
- Prefer discovered facts over questions. Ask only about product choices or
  tradeoffs that inspection cannot resolve.
- Never invent a file, symbol, command, test, or line number.

Keep three evidence classes distinct:

- **Confirmed** — explicitly requested or approved by the user.
- **Verified** — observed in the current repository or environment.
- **Assumed** — a disclosed default selected because the first two are silent.

Do not ask the user to reconfirm confirmed decisions.

## 2. Define the contract

Define observable behavior before proposing file changes. Cover only dimensions
that materially apply: public interfaces, input/output shapes, null and missing
semantics, ordering, state transitions, errors, exit codes, compatibility,
partial results, read-only guarantees, accessibility, and security boundaries.

For API, CLI, schema, persisted-state, or finite-state changes, read
[references/contract-checklist.md](references/contract-checklist.md). Use a truth
table when a finite set of combinations would otherwise remain ambiguous.

Separate required work from non-goals and deferred work. When requirements
conflict, demonstrate the conflict and expose only the viable decisions.

## 3. Construct the implementation path

Order changes by dependency. For each material slice, identify:

- purpose and existing pattern to reuse;
- files or symbols to change when verified;
- invariants that remain unchanged;
- data flow and compatibility effects;
- tests or runtime evidence;
- the exact verified gate that closes the slice.

Express multi-step work as `step → verification`. Separate behavior-preserving
refactors from new behavior when that improves reviewability. Keep branch,
commit, migration, and rollout ordering feasible in the observed repository.

## 4. Try to break the plan

For each material identity or invariant, construct at least one concrete
boundary or adversarial example and calculate or trace the expected result.

Read only the applicable sections of
[references/adversarial-checklist.md](references/adversarial-checklist.md):
numeric, temporal, filesystem/state, scale, or integration.

Classify every failed invariant as:

- resolved by revising the implementation or contract;
- accepted with explicit user-visible behavior;
- blocked on a product or architecture decision.

Revise the main plan after this audit. Never leave a stale plan in place and
bury its contradiction in a risk list.

## 5. Design verification

Map every material requirement to evidence:

- test level and fixture or scenario;
- exact expected result;
- verified repository command;
- manual or runtime check when automation cannot prove it.

Include before/after evidence for read-only or state-preservation guarantees.
Distinguish unit, contract, integration, generation-drift, build, and live-host
checks instead of treating one passing suite as universal proof.

## 6. Publish the revised plan

Use the host's native plan envelope and interaction rules. Do not impose a
Claude- or Codex-specific wrapper from this skill.

Keep the output proportional, but include:

- readiness and the decisive reason;
- confirmed work and non-goals;
- contracts and invariants;
- dependency-ordered implementation;
- verification evidence;
- assumptions and blockers.

End with one status:

- **Ready** — no unresolved contract or implementation decision remains.
- **Ready with assumptions** — disclosed defaults remain but do not block work.
- **Blocked** — implementation would require an unresolved decision.

Do not mark the plan Ready when requirements are mathematically or behaviorally
incompatible, public failure semantics are missing, referenced repository facts
were not verified, or the implementer would still need to choose the behavior.
