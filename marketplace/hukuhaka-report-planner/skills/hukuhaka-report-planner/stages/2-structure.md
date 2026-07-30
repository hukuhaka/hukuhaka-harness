---
stage: 2
purpose: structure verified evidence into a trunk, units, reader outcomes, and anchor needs before choosing visual forms
prereq: Stage 1 Document Model and initial Evidence blocks exist in .hukuhaka/reports/tmp-draft/spec.md
deliverable: draft spec extended with completed Evidence and Structure blocks plus unresolved anchor intents
verification_gate: every unit has a source-backed purpose and an anchor need or prose decision
---

## Structure

Read the material deeply enough to design the document from its evidence and reader job.
This stage decides what the document must explain, not how its anchors will look.

## Required reading

- `.hukuhaka/reports/tmp-draft/spec.md`
- `references/spec-schema.md`
- `references/principles.md`

For a new plan, read and write only `.hukuhaka/reports/`. If that draft is absent and an
explicit continuation refers to `.claude/reports/tmp-draft/spec.md`, read the legacy draft as
a fallback, leave it untouched, and write the continued draft to `.hukuhaka/reports/`.

## Process

1. **Deep-read and verify.** Expand the Evidence block with verified sources, established
   facts, conflicts, freshness constraints, and unresolved gaps. Keep inference explicit.

2. **Choose the structural trunk.** State the central claim, decision, sequence, taxonomy,
   comparison, timeline, spatial map, or operating loop that gives the document coherence.
   Do not start with generic sections.

3. **Derive units and anchor needs.** For each unit record:
   - the reader question;
   - the reader outcome;
   - supporting source IDs;
   - an anchor ID or `prose`.

   Record only the relationship or exact evidence the reader needs. Do not choose chart,
   diagram, table, code, animation, or another visual form yet. Do not force an anchor where
   prose is clearer. For a small memo, two to four units and zero to three non-prose anchors
   are usually enough.

4. **Resolve meaningful ambiguity.** If two structures would materially change the artifact,
   present one recommendation and one distinct alternative. Otherwise select the defensible
   direction and state the assumption without adding a mandatory approval round.

5. **Update the draft spec.** Preserve Document Model; complete Evidence and add Structure.
   Give each intended non-prose anchor a stable ID and reader question, but leave its form and
   construction brief for Stage 3. Keep each field concise and use source IDs instead of
   repeating exact facts.

## Output

```
SHORT-NAME: <kebab-case>
TRUNK: <central structure>
UNITS: <U1 ... Un>
ANCHOR NEEDS: <A1 ... An, including prose-only decisions, without visual forms>
```

## Failure modes

- Choosing chart, diagram, code, animation, or layout before Stage 3.
- Adding visuals without evidence or a reader question.
- Forcing a visual into every unit.
- Using a generic Background/Method/Results outline without deriving it from the trunk.
