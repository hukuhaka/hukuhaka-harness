---
name: map-summary
description: "Compress .claude/ docs for LLM context"
allowed-tools: Read, Task, Agent
---

# /hukuhaka-project-mapper:map-summary

Compress `.claude/` documentation into a single LLM-friendly summary.

## Pre-flight

Read `.claude/map.md` and `.claude/design.md` to confirm docs exist:

- `.claude/` directory absent, or BOTH files missing → tell user to run `/hukuhaka-project-mapper:map-init` first and STOP
- Exactly one exists → proceed; the summary notes which doc was missing
- Both exist → proceed

## Steps

1. Spawn summarizer agent:

```
Agent(subagent_type: "hukuhaka-project-mapper:summarizer", prompt: "Compress .claude/ documentation into a single summary")
```

2. Display summarizer results.

## Rules

- `subagent_type` MUST use `hukuhaka-project-mapper:summarizer` (fully qualified)
