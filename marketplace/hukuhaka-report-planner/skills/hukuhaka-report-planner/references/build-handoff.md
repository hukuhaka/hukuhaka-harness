# Build handoff

Use this contract only after Stage 2 validates the final `spec.md` and the invocation mode is
`build-preflight`. Planning-only requests stop at the spec.

## Delegation payload

Send one designer all of the following:

```yaml
spec path: .hukuhaka/reports/<short-name>/spec.md
source material: <paths and verified URLs named by the spec>
design source: <explicit DESIGN.md path or none>
craft references: <the spec's selected references as absolute paths, or none>
form: <Document Model form>
output target: <user-requested path or build destination>
verification: <Acceptance Tests block>
```

Do not paste the spec into the prompt when the subagent can read the file. Pass paths so the
designer works from the same source of truth.

Resolve the spec's selected craft references against the planner's own skill directory and
pass absolute paths. The designer does not load the planner skill and cannot resolve
planner-relative paths.

## Host adapters

### Claude Code

Delegate to the plugin subagent `hukuhaka-report-planner:artifact-designer`. The plugin agent
preloads the portable `artifact-designer` skill and inherits the session's available build and
rendering tools.

### Codex

Codex plugins package skills but not custom-agent definitions. Spawn one write-capable worker
subagent and explicitly instruct it to use the installed `artifact-designer` skill with the
delegation payload above. Do not create or install a user-level `.codex/agents/` file.

## Completion

- Wait for the designer to finish; do not build in the parent or run a competing builder.
- Check that the returned receipt names artifact paths, direct visual inspection coverage, and
  every acceptance-test result.
- If the host cannot spawn a write-capable subagent or the designer skill is unavailable, stop
  and report the missing surface. Do not silently fall back to same-context construction.
