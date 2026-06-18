# Compact Format Rules

Rules for the compact operation (changelog + backlog cleanup). This file
documents what `clean-backlog.py` and `compact-changelog.py` actually do —
the scripts are the source of truth; do not compensate for gaps by hand.

## changelog.md

- `## Recent` — latest 10 entries, format: `- [YYYY-MM-DD] description`
- Entries beyond 10 are moved verbatim to `## Archive` (order preserved; no monthly consolidation)

## backlog.md

- `## Planned` — future work
- `## In Progress` — active items
- `## Discovered TODOs` — auto-scanned from codebase
- Completed (`- [x]`) items move to changelog `## Recent`; the `[x]` becomes a `[YYYY-MM-DD]` date prefix
- Empty sub-sections (### High Priority etc.) are preserved, not removed
- User content in Planned/In Progress is never deleted
