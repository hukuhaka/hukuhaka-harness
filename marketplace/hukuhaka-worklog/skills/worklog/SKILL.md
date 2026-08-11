---
name: worklog
description: Use automatically when a project has .hukuhaka/work.md and .hukuhaka/changelog.md and the user starts, resumes, pauses, completes, or abandons non-trivial project work, even if they do not mention Worklog. Also use for explicit requests to record or change work state. Do not use for analysis-only requests, implementation planning, routine one-off edits, mechanical setup/status/archive commands, or issue-tracker synchronization.
---

# Worklog

Use `.hukuhaka/work.md` for current work and `.hukuhaka/changelog.md` for completed or closed history. Never read, migrate, or write a legacy `backlog.md`.

## Orient the session

When both Worklog files exist, read `work.md` before changing project files for the first non-trivial project task in a new session. Read `changelog.md` only when resuming, completing, closing, or checking a prior decision. This orientation does not by itself authorize a Worklog update.

## Manage lifecycle

1. If the user explicitly asks to record or change Worklog state and either file is missing, stop and ask them to invoke the exact host command: `/hukuhaka-worklog:worklog setup` in Claude Code or `$hukuhaka-worklog:worklog setup` in Codex. For automatic use, missing files do not block the underlying task: continue without creating or changing Worklog files. If a Codex setup command reached the model instead of the hook, tell the user to open `/hooks`, review and trust the worklog hook, then retry; do not emulate setup in the Skill.
2. Read both files and identify an existing matching item before adding a new one. Preserve the user's language and do not invent IDs, priorities, owners, or schedules.
3. Before an automatic write, inspect working-tree status for both Worklog files. If either already has user changes, do not modify either file; continue the underlying task and report the conflict.
4. Only the primary agent changes Worklog state. Delegated agents may read it for context but must not modify it.
5. Inspect the code or evidence needed to make the wording factual. Use at most three focused search rounds; pure ideas do not need a code anchor.
6. Choose the state from the observed intent:
   - active now → `In Progress`
   - intended but not active → `Planned`
   - intentionally paused or waiting on a condition → `On Hold`
   - finished with evidence → completed changelog entry
   - intentionally not pursuing → closed changelog entry
7. For completion or closure, write the changelog first and remove the current item second. Tell the user to invoke the mechanical `worklog archive` command only when Recent exceeds 10 entries.
8. Report the exact item, state, and files changed.

Ask one concise question only when different state choices would materially change the record.

## Write the files

Keep exactly these `work.md` sections:

```markdown
## In Progress
## Planned
## On Hold
```

Start every current item with one top-level list line. Indent optional evidence, next gate, action, or reconsideration condition beneath it. Planned work needs a current fact or purpose and one concrete next action. In Progress needs verified current state and the next gate. On Hold needs the pause reason and an observable reconsideration condition. Do not keep completed or closed items in `work.md`.

Start every history entry under `## Recent` with:

```markdown
### YYYY-MM-DD — Short title
```

Put the newest entry first. Completed entries state the result, verification, and any material caveat. Closed entries state the decision, reason, and a concrete `Reopen when` condition. Do not impose IDs, priority tiers, fixed owners, or a rigid field order.
