---
stage: 1
purpose: explore the evidence, structural trunk, units, anchors, and a reference-free design concept before selecting optional references
prereq: Stage 0 Document Model and initial Evidence blocks exist in .hukuhaka/reports/tmp-draft/spec.md
deliverable: draft spec extended with Evidence, Structure, Anchors, and Design Direction
verification_gate: ask only when materially different directions would change the build
---

## Explore

Read the material deeply enough to design the document from its evidence and reader job.
The sequence is important: concept first, references second.

## Required reading

- `.hukuhaka/reports/tmp-draft/spec.md`
- `references/spec-schema.md`
- `references/principles.md`
- `references/reference-index.md`

Do not read all of `references/craft/`. Select zero to three files only after step 4.

For a new plan, read and write only `.hukuhaka/reports/`. If that draft is absent and an
explicit continuation refers to `.claude/reports/tmp-draft/spec.md`, read the legacy draft as
a fallback, leave it untouched, and write the continued draft to `.hukuhaka/reports/`.

## Process

1. **Deep-read and verify.** Expand the Evidence block with verified sources, established
   facts, conflicts, freshness constraints, and unresolved gaps. Keep inference explicit.

2. **Choose the structural trunk.** State the central claim, decision, sequence, taxonomy,
   comparison, timeline, spatial map, or operating loop that gives the document coherence.
   Do not start with generic sections.

3. **Derive units and anchors.** For each unit record:
   - the reader question;
   - the reader outcome;
   - supporting source IDs;
   - an anchor ID or `prose`.

   An anchor may be a chart, table, diagram, screenshot, code example, decision matrix,
   checklist, quotation, or prose explanation. Do not force an anchor where prose is clearer.
   For a small memo, two to four units and zero to three non-prose anchors are usually enough.

4. **Create the design concept without reference names.** Describe information density,
   reading rhythm, typographic voice, contrast, geometry, surface behavior, color semantics,
   and anchor treatment. Generate an alternative only when it changes at least structure,
   typography voice, or anchor grammar; color swaps are not alternatives.

   A concept is two or three concrete sentences, e.g.: "Calm, dense decision surface:
   near-monochrome chrome with a single cool accent reserved for the recommended route;
   tabular numerals and hairline rules carry the comparisons; prose stays brief between
   anchors, and each unit leads with its takeaway line so a scanning reader collects the
   argument from takeaways alone."

5. **Select references.** Use `reference-index.md` to choose zero to three craft files that
   address specific unresolved design problems. User-supplied `DESIGN.md` files and named
   external style targets are off by default unless the user explicitly selects them. For each
   selected source record:
   - mechanism borrowed;
   - how it is transformed for this document;
   - what is rejected;
   - clone risk.

6. **Specify anchors.** Each non-prose anchor records its reader question, evidence, selected
   form, takeaway, and caveat. Consider alternatives only when validity is genuinely unclear.
   Do not select a form merely to increase visual variety.

7. **Resolve meaningful ambiguity.** If two directions would materially change the artifact,
   present one recommendation and one distinct alternative. Otherwise select the defensible
   direction and state the assumption without adding a mandatory approval round.

8. **Update the draft spec.** Preserve Document Model; complete Evidence and add Structure,
   Anchors, and Design Direction. Keep each field to one concise sentence where possible and
   use source IDs instead of repeating exact facts. Stage 2 locks the contract and renames
   the directory.

## Output

```
SHORT-NAME: <kebab-case>
TRUNK: <central structure>
UNITS: <U1 ... Un>
ANCHORS: <A1 ... An, including prose-only decisions>
DESIGN CONCEPT: <reference-free concept>
REFERENCES: <zero to three selected sources with borrow/transform/reject>
```

## Failure modes

- Reading all craft files or an entire `DESIGN.md` before forming a concept.
- Loading a project `DESIGN.md` merely because it exists or copying its whole website grammar.
- Treating a chart name as an anchor specification.
- Adding visuals without evidence or a reader question.
- Forcing a visual into every unit.
- Using a generic Background/Method/Results outline without deriving it from the trunk.
- Offering alternatives that differ only in color.
- Reintroducing modes, registers, pinned components, or fixed style rules.
