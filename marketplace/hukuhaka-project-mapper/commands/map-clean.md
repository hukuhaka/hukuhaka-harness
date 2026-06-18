---
name: map-clean
description: "Remove scattered CLAUDE.md files"
allowed-tools: Bash(bash:*)
---

# /hukuhaka-project-mapper:map-clean

Remove map-sync-managed CLAUDE.md files from subdirectories via bundled clean script. No agents.

## Steps

Invoke the bundled script via Bash from the project root (cwd):

```
bash ${CLAUDE_PLUGIN_ROOT}/scripts/setup/clean.sh
```

The script removes only `CLAUDE.md` files containing the `<!-- managed by map-sync -->` marker. Hand-written CLAUDE.md, root `./CLAUDE.md`, and anything under hidden dirs or `node_modules/` are never touched. The deletion list is printed before removal.

Display the script's stdout verbatim as the completion report.

## Rules

- Do NOT spawn any agents via Agent tool
- Do NOT use Glob/Read/Bash directly to find or delete CLAUDE.md — invoke only the bundled clean script
- NEVER delete root `./CLAUDE.md` (the script enforces this)
