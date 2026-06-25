# Provenance & upstream re-sync

`hukuhaka-codex` is a modified distribution of OpenAI's **codex** plugin for
Claude Code (Apache-2.0). See `NOTICE` for the modification statement.

## What we added (ours)
- `commands/plan.md`, `commands/review-loop.md`, `commands/duel.md`, `commands/full.md`
- `skills/codex-plan/SKILL.md`
- `.claude-plugin/plugin.json` (renamed), `NOTICE` (modification statement), this file

## What we changed in upstream files
Only a namespace rename, applied because the plugin name changed from `codex`
to `hukuhaka-codex` and the namespace is baked into slash-command hint strings
and the rescue subagent type:

- `/codex:<cmd>`  ->  `/hukuhaka-codex:<cmd>`   (command-ref strings, runtime + command docs)
- `codex:codex-rescue`  ->  `hukuhaka-codex:codex-rescue`   (subagent type)
- `Skill(codex:rescue)`  ->  `Skill(hukuhaka-codex:rescue)`

JS object keys / status labels like `codex: ...` were intentionally NOT touched.

## Re-syncing a new upstream codex release
1. Copy the new upstream `plugins/codex/{scripts,prompts,schemas,hooks,agents}`
   and the upstream `commands/*.md` / `skills/{codex-cli-runtime,codex-result-handling,gpt-5-4-prompting}`
   over this directory (do NOT overwrite our added files above).
2. Re-apply the namespace rename:
   ```bash
   D=marketplace/hukuhaka-codex
   grep -rl '/codex:'        "$D" --include='*.md' --include='*.mjs' | xargs -r perl -pi -e 's{/codex:}{/hukuhaka-codex:}g'
   grep -rl 'codex:codex-rescue' "$D" --include='*.md' --include='*.mjs' | xargs -r perl -pi -e 's{codex:codex-rescue}{hukuhaka-codex:codex-rescue}g'
   perl -pi -e 's{Skill\(codex:rescue\)}{Skill(hukuhaka-codex:rescue)}g' "$D/commands/rescue.md"
   ```
3. Confirm the only remaining bare `codex:` is the `- codex:` status label in
   `scripts/lib/render.mjs`, then `node --check` the modified `.mjs` files.
4. Keep `.claude-plugin/plugin.json`, `NOTICE`, and the four added commands +
   `codex-plan` skill as-is.
