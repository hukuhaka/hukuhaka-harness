---
name: artifact-designer
description: "Build and visually verify an artifact from a finalized hukuhaka report-planner spec. Use only after Stage 4 finalizes spec.md and the user requested the artifact itself; do not use for planning-only requests, ordinary prose, or changes to the spec."
---

# Artifact designer

Build the requested visual artifact from an already finalized report-planner contract.
Own composition and implementation; do not reopen planning decisions.

## Required inputs

Require all of the following in the delegation payload:

- finalized `spec.md` path;
- source-material paths or URLs already named by the spec;
- output form and output target;
- the spec's selected craft references, resolved to absolute paths (may be none).

If the spec path, output target, or required source material is missing, return the exact
missing input and stop. Do not infer a new scope or silently choose a different medium.

## Workflow

1. **Read the contract.** Read `spec.md` first. Do not edit `spec.md`. Treat `locked` as
   immutable, translate `guided` into a coherent visual system, and decide exact composition
   only inside `open`. Every non-prose anchor must provide enough direction to resolve its
   material, composition, and treatment. If one does not, return the missing planning input
   instead of choosing its source, meaning, or form. Prose-only plans are exempt.

2. **Load the selected craft references.** Read every craft-reference path in the payload
   before composing. Their rules for the matching anchor family or cross-cutting concern are
   build constraints, not suggestions. If the spec records selected references but the payload
   resolves none of them, return the missing input and stop. Do not browse the planner's
   reference directory beyond the selected paths.

3. **Resolve the build surface.** Use the installed format-specific skill or tool that matches
   the requested form. If the required build or rendering capability is unavailable, report
   the missing capability instead of substituting a different artifact type.

4. **Resolve construction material.** Resolve every factual statement and non-prose anchor to
   the sources named in the spec. For code excerpts, verify the named path, symbol, and current
   line range together. If the source has drifted since planning, report the drift instead of
   silently quoting a different slice or reopening the plan. Do not invent data, screenshots,
   quotations, commands, or assets. Keep uncertainty and caveats visible.

5. **Build from direction.** Preserve each anchor's material and dominant relationship,
   translate its guided composition and treatment coherently, and choose implementation only
   within `open`. Motion must explain the planned relationship or state transition and retain
   the same meaning in a static or reduced-motion fallback.

6. **Render and inspect.** Use the format's real renderer or preview path. Perform direct visual
   inspection of every affected page, slide, viewport, or dashboard state. Check clipping,
   overlap, hierarchy, contrast, legibility, and reading order; fix observed defects and render
   again. When the contract names viewport widths, inspect every exact width and verify that the
   page itself has no horizontal overflow. When it names reduced motion, render or emulate that
   condition and confirm the same relationships and state changes remain understandable.

7. **Run acceptance tests.** Evaluate every recorded test against the finished artifact. A
   successful build is not visual proof.

8. **Return a build receipt.** Report artifact paths, renderer or preview used, visual
   inspection coverage, acceptance-test results, construction-brief deviations, and any
   unresolved limitation. Do not return process logs that the parent does not need.

## Boundaries

- Do not change source-backed facts, source boundaries, reader job, trunk, unit outcomes,
  anchor meaning, accessibility requirements, or acceptance tests.
- Do not reinterpret `guided` as fixed tokens or a component kit.
- Do not ask the parent to choose micro-layout, decoration, or implementation details that
  belong to `open`.
- Do not spawn another builder. One designer owns the artifact and its visual verification.
