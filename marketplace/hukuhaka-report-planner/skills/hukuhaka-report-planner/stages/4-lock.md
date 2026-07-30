---
stage: 4
purpose: lock the evidence-backed document plan, construction briefs, build contract, and acceptance tests
prereq: Stage 3 completed Evidence, Structure, Anchors, and Design Direction blocks
deliverable: finalized .hukuhaka/reports/<short-name>/spec.md
verification_gate: the complete contract passes the Stage 4 self-review
---

## Lock

Convert the explored direction into a contract that a builder can follow without
re-deciding the document's meaning.

## Process

1. **Resolve material gaps.** Do not present unresolved claims as established facts. When a
   gap blocks a final conclusion but not the plan, encode the required measurement, decision
   gate, or fallback in the structure and acceptance tests. Ask the user only when a scope or
   evidence-boundary decision cannot be inferred.

2. **Check structural coverage.** Every unit must answer a reader question, produce a reader
   outcome, cite evidence, and identify an anchor or `prose`. Remove redundant units.

3. **Check anchor direction.** Every non-prose anchor must have supporting evidence, a
   selected form, expected takeaway, material caveat, and a construction brief that resolves
   material, composition, and treatment. Repetition is acceptable when the same comparison
   grammar is genuinely required. Prose-only plans need only explain why prose is clearer.

4. **Write the Build Contract.** Divide decisions into:
   - `locked`: facts, source boundaries, reader job, structure, anchor meaning, accessibility;
   - `guided`: density, type roles, color roles, rhythm, surface and anchor grammar;
   - `open`: exact composition, decorative geometry, micro-layout, and implementation details.

   Refer to the blocks above instead of restating their contents. Add only the constraints a
   builder could otherwise violate.

5. **Write Acceptance Tests.** Include the Document Model success test plus evidence fidelity,
   structure scan, anchor validity, and medium-specific behavior where applicable. Tests must
   describe observable outcomes rather than aesthetic approval. Four to six tests are enough
   for a small artifact unless a real risk requires more.

6. **Derive `<short-name>`.** Use lowercase kebab-case, at most 24 characters, based on the
   subject rather than the output form.

7. **Run the final self-review.** Re-read the complete spec as the future designer. Confirm
   that every unit resolves to evidence and an anchor or prose decision, every non-prose
   anchor has a usable construction brief, Build Contract boundaries agree with the blocks
   above, and every acceptance test is observable. Fix contradictions before finalizing.

8. **Finalize and hand off by invocation mode.** Rename
   `.hukuhaka/reports/tmp-draft/` to `.hukuhaka/reports/<short-name>/` and write the complete
   contract. If `<short-name>/` already exists, confirm whether this plan revises it;
   otherwise derive a distinct name rather than overwriting a finished spec.
   - `plan`: report the finalized spec path and stop.
   - `build-preflight`: read `references/build-handoff.md`, delegate the finalized spec, its
     source paths, and the spec's selected craft references resolved to absolute paths to one
     designer subagent in the foreground, wait for the build receipt, and check that every
     recorded acceptance test was run. Do not set `run_in_background`, return before the
     receipt, or build in the planner context.

   When continuing an existing spec that lacks construction briefs, preserve its established
   evidence and structure but return through Stages 3 and 4 before delegation. A legacy
   `.claude/reports/` source remains read-only and is continued under `.hukuhaka/reports/`.

## Failure modes

- Converting `guided` preferences into exact CSS tokens or fixed components.
- Leaving core decisions in `open` and forcing the builder to reinterpret them.
- Finalizing while a designer would still have to choose source material or anchor meaning.
- Building in the parent after delegating or running multiple competing designers.
