---
name: codex-memory-audit
description: Audit Codex local memories when the user asks to inspect, prune, consolidate, or correct stale engineering context, or when a memory-pressure warning recommends an audit. Verify drift-prone claims against current sources, propose an approval-gated cleanup, and never hand-edit generated memory files.
---

# Codex Memory Audit

Audit retained coding context so historical implementation details do not silently become current facts.

## Boundaries

- Codex local memories normally live under `${CODEX_HOME:-~/.codex}/memories/` and are generated state. Inspect them, but do not edit `memory_summary.md`, `MEMORY.md`, rollout summaries, or evidence files directly.
- Required team or repository rules belong in `AGENTS.md` or checked-in documentation, not only in memory.
- Audit first. Apply nothing until the user approves the exact proposed changes.
- Do not treat old branches, versions, paths, commands, runtime results, project status, or design decisions as current without checking the active source.
- Do not claim full coverage unless the complete local memory inventory was accessible.

## Workflow

### 1. Establish scope and inventory

Record the reference date, Codex home used, and whether coverage is full or partial. Inspect the smallest useful set:

1. `memory_summary.md` for always-loaded context;
2. `MEMORY.md` for the durable index and pointers;
3. only the rollout summaries or evidence files needed to resolve a claim.

Report the summary byte and physical-line counts, index byte count, and rollout-summary file count. Do not dump unrelated memory content merely to prove access.

### 2. Split memories into atomic claims

Separate durable working preferences from volatile implementation state. For example, split “uses repository X on branch Y with tool version Z” into the repository relationship, branch, and tool-version claims before judging it.

Give extra scrutiny to:

- current repository paths, branches, worktrees, remotes, tags, and dirty state;
- current architecture, public/private boundaries, active milestones, TODOs, and completion claims;
- versions, models, SDKs, dependencies, ports, commands, generated artifacts, and runtime health;
- measurements, benchmark results, test counts, device state, deployment state, and external-service status;
- duplicated instructions already owned by `AGENTS.md`, project docs, configuration, or code.

### 3. Verify now when verification is available

For each drift-prone claim, inspect the current authoritative source before classifying it. Prefer, in order:

1. the user's latest explicit direction;
2. current repository source, configuration, Git state, runtime artifacts, or external authority when authorized;
3. current Worklog and maintained project documentation;
4. memory indexes and historical rollout evidence.

Do not ask the user for information that can be discovered safely. If verification is unavailable, too disruptive, or outside the authorized scope, report the claim as `UNRESOLVED`; do not preserve it as a current memory candidate.

`UNRESOLVED` is a report status, not a memory classification. Do not create a `VERIFY` class or postpone cheap current verification into a future memory item.

### 4. Classify each claim

Use exactly these memory actions:

- **KEEP** — durable, useful, low-drift context that remains supported and is not already owned by a stronger instruction source.
- **CONDENSE** — useful experience or preference buried in excessive episodic detail. Replace the detail with the smallest evidence-supported durable statement.
- **SUPERSEDE** — current authority disproves or replaces the stored claim. Remove the old claim and propose only the durable part of the verified replacement; do not automatically memorize another volatile snapshot.
- **DELETE** — duplicated, obsolete, misleading, unnecessary, sensitive, or one-off information with no durable future value.

Do not keep a claim merely because it was once true. Current values that are cheap to rediscover should usually remain in their authoritative source rather than memory.

### 5. Present an exact proposal

Lead with the main quality risk, then provide:

1. coverage and measured pressure;
2. KEEP;
3. CONDENSE with exact replacement wording;
4. SUPERSEDE with current evidence and exact replacement or removal;
5. DELETE;
6. UNRESOLVED claims and the missing authority;
7. conflicts and duplicates;
8. the proposed compact canonical memory.

For every non-KEEP item, identify the source memory and the exact proposed action. End with: `No memory changes have been applied.`

## Approval and application

Interpret approval narrowly. A bare approval applies only when the immediately preceding proposal is singular and unambiguous. Corrections or exclusions override the proposal for those items.

After approval:

1. Recheck any current authority that may have changed during the audit.
2. Translate the approved scope into explicit retain, replace, and remove operations.
3. Use an active Codex memory-management surface if one is available and verify its result.
4. If no supported write surface is available, return the exact approved change set and direct the user to `/memories`; do not hand-edit generated memory files or claim the cleanup was applied.

Never write secrets or unnecessary personal data into the proposed canonical memory. Never modify repository files, Git state, runtime services, or external systems merely to make a memory claim true.
