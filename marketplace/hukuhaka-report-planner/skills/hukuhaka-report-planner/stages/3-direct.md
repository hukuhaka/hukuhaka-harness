---
stage: 3
purpose: direct each non-prose anchor through a source-backed construction brief and designer-view self-critique
prereq: Stage 2 completed Document Model, Evidence, Structure, and stable anchor intents
deliverable: draft spec extended with complete Anchors and Design Direction blocks
verification_gate: a designer can build each anchor without re-deciding its meaning
---

## Direct

Work as the artifact designer's planning counterpart. Turn every non-prose anchor intent into
a buildable direction while leaving exact implementation and micro-layout open. Do not spawn a
designer or build the artifact in this stage.

## Required reading

- `.hukuhaka/reports/tmp-draft/spec.md`
- `references/spec-schema.md`
- `references/principles.md`
- `references/reference-index.md`

Do not read all of `references/craft/`. Form the design concept first, then select zero to
three files that solve named anchor or cross-cutting problems.

## Process

1. **Create the design concept without reference names.** Describe information density,
   reading rhythm, typographic voice, contrast, geometry, surface behavior, color semantics,
   and anchor grammar in two or three concrete sentences. Generate an alternative only when
   it changes structure, typographic voice, or anchor grammar; color swaps are not alternatives.

2. **Select references.** Use `reference-index.md` to choose zero to three craft files. For
   each selected source record the mechanism borrowed, its translation for this document,
   what is rejected, and clone risk. References supply judgment procedures, not a full design.

3. **Select each anchor form.** Choose chart, table, diagram, screenshot, code, checklist,
   quotation, or another form only after matching it to the reader question and evidence.
   Consider alternatives only when representation validity is genuinely unclear.

4. **Write each construction brief.** Cover all three meanings below. Keep separate fields
   when clarity requires them; a small anchor may combine them into one or two sentences.
   - `material`: the exact source slice, fields, code path and symbol, current line range,
     states, labels, or qualitative material the anchor may use;
   - `composition`: the dominant relationship, spatial or sequential arrangement, entry
     point, reading order, and intentional omissions;
   - `treatment`: static, animated, or interactive behavior; emphasis, annotation, and color
     roles; responsive, print, and accessibility fallback where applicable.

   Line numbers never stand alone as code identity. Pair them with a path and symbol. Motion
   must explain a supported relationship or state transition and preserve the same meaning in
   a static or reduced-motion fallback.

5. **Sketch only when it clarifies direction.** Add a compact ASCII sketch under composition
   when prose cannot communicate a load-bearing spatial relationship. Do not turn sketches
   into fixed coordinates, component kits, or mandatory wireframes.

6. **Run the designer-view self-critique.** For every non-prose anchor ask:
   - Can the material be resolved directly to the listed evidence?
   - Is the dominant relationship and takeaway unambiguous?
   - Can a designer execute the treatment without inventing meaning?
   - Are caveats and non-color/non-motion fallbacks visible?

   Revise any anchor that would force the builder to answer one of those questions.

7. **Update the draft spec.** Complete Anchors and Design Direction. Preserve the Stage 2
   structure; return to Stage 2 only when construction reveals a real evidence or structural
   contradiction.

## Output

```
ANCHORS: <A1 ... An with selected form and construction brief>
DESIGN CONCEPT: <reference-free concept>
REFERENCES: <zero to three selected sources with borrow/transform/reject>
SELF-CRITIQUE: <resolved construction gaps, or none>
```

## Failure modes

- Treating a chart or diagram name as a construction brief.
- Asking the artifact designer to choose source material or anchor meaning.
- Prescribing libraries, exact CSS tokens, fixed coordinates, or component implementations.
- Animation used as ornament or as the only carrier of meaning.
- Long code excerpts where a source-linked critical slice answers the question.
- Spawning a reviewer or builder during planning.
