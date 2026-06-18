---
name: map-compact
description: "Clean up changelog and backlog docs"
allowed-tools: Bash(python3:*)
---

# /hukuhaka-project-mapper:map-compact

Clean up changelog.md and backlog.md via two bundled scripts run in sequence.

## Steps

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/maintain/clean-backlog.py
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/maintain/compact-changelog.py
```

- `clean-backlog.py`: moves `- [x]` (completed) items from backlog.md to changelog.md `## Recent`
- `compact-changelog.py`: keeps top 10 entries in `## Recent`, moves older to `## Archive`

This order matters: clean-backlog prepends to `## Recent`, so compact-changelog must run after it — the reverse can leave Recent over the limit it just enforced.

Display both scripts' stdout verbatim.

## Rules

- Do NOT spawn any agents via Agent tool
- Do NOT use Edit/Write to modify changelog.md or backlog.md — invoke only the bundled scripts
- Both scripts must be run; do not skip either
