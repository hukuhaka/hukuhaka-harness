---
name: worklog
description: Maintain current project work, deferred work, completed outcomes, and closed decisions. Use when the user asks to record, start, pause, resume, finish, or close project work. Do not use for mechanical setup, status, or archive commands, implementation plans, or issue-tracker synchronization.
---

# Worklog

Use `.hukuhaka/work.md` for current work and `.hukuhaka/changelog.md` for completed or closed history. Never read, migrate, or write a legacy `backlog.md`.

## Manage lifecycle

1. Require `.hukuhaka/work.md` and `.hukuhaka/changelog.md`. If either is missing, stop and ask the user to invoke the host's mechanical `worklog setup` command. Do not create the files yourself.
2. Read both files and identify an existing matching item before adding a new one. Preserve the user's language and do not invent IDs, priorities, owners, or schedules.
3. Inspect the code or evidence needed to make the wording factual. Use at most three focused search rounds; pure ideas do not need a code anchor.
4. Choose the state from the observed intent:
   - active now → `In Progress`
   - intended but not active → `Planned`
   - intentionally paused or waiting on a condition → `On Hold`
   - finished with evidence → completed changelog entry
   - intentionally not pursuing → closed changelog entry
5. For completion or closure, write the changelog first and remove the current item second. Tell the user to invoke the mechanical `worklog archive` command only when Recent exceeds 10 entries.
6. Report the exact item, state, and files changed.

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
