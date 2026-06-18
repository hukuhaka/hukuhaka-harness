---
name: map-init
description: "Create .claude/ documentation scaffolding with 5 template files"
allowed-tools: Bash(bash:*)
---

# /hukuhaka-project-mapper:map-init

Create `.claude/` documentation scaffolding with 5 template files via bundled init script. No agents, no inline file writes. Existing files are preserved and reported — re-running init never overwrites user content (`--force` is the explicit override).

## Steps

### Step 1 — Run init script

Invoke the bundled script via Bash from the project root (cwd):

```
bash ${CLAUDE_PLUGIN_ROOT}/scripts/setup/init.sh
```

The script copies 5 templates into `.claude/`, skipping any file that already exists:
- `.claude/map.md` — Entry Points, Data Flow, Components, Structure
- `.claude/design.md` — Stack, Patterns, Decisions
- `.claude/backlog.md` — `## Planned`, `## In Progress`, `## Discovered TODOs`
- `.claude/changelog.md` — Recent, Archive
- `.claude/spec.md` — placeholder; filled by `/hukuhaka-project-mapper:map-spec generate`

### Step 2 — Report

Display the script's stdout verbatim as the completion report. The script lists created vs preserved files and the spec.md follow-up suggestion — do not paraphrase.

## Rules

- Do NOT spawn any agents via Agent tool
- Do NOT use the Write or Edit tools — invoke only the bundled init script
- Do NOT use AskUserQuestion — init is fully non-interactive
- Do NOT pass `--force` unless the user explicitly asked to reset existing docs
- Do NOT fill spec.md content — generation is the map-spec skill's job
