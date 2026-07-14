---
stage: 0
purpose: discover the document job, reading behavior, form, audience, success test, source material, and evidence gaps
prereq: user issued a visual-document planning or build request
deliverable: .hukuhaka/reports/tmp-draft/spec.md created with Document Model and an initial Evidence block
verification_gate: ask only when missing information blocks a defensible plan
---

## Discover

Turn the request into a document model before choosing a structure or visual form. Do not
open craft references in this stage.

## Process

1. **Determine invocation mode.** An explicit planning request is `plan`; an artifact request
   is `build-preflight`. Only an explicit request to skip planning bypasses the skill.

2. **Inspect the available material lightly.** Locate supplied files, data, code, prior
   findings, and authoritative external sources. Reuse current project documentation when it
   is relevant, but do not treat generated or stale documentation as verified evidence.

3. **Derive the Document Model.** Record:
   - `job`: `decide | explain | reference | monitor | persuade | teach | record`;
   - `reading behavior`: `linear | scan | random-access | live`;
   - `form`: web document, deck, dashboard, print/PDF, poster, or another explicit medium;
   - `audience`: reader, context, and expected prior knowledge;
   - `success test`: an observable reader outcome;
   - `prose level`: `brief | balanced | full`.

4. **Start the Evidence block.** List the material already available and the important gaps.
   Use stable IDs (`S1`, `S2`) for sources. A source may be a supplied file, repository path,
   dataset, user brief, or verified URL. Mark unverified claims as gaps, not facts.

5. **Decide whether to ask.** Ask one concise question only if the user must choose a scope,
   job, form, evidence boundary, or success test before planning can continue. A known evidence
   gap is not by itself a reason to stop: record it and design a conditional recommendation,
   measurement gate, or fallback. Otherwise make the assumption explicit and continue.

6. **Write** `.hukuhaka/reports/tmp-draft/spec.md` with `## Document Model` and the initial
   `## Evidence` block from `references/spec-schema.md`.

## Required reading

- `references/spec-schema.md` — Document Model and Evidence block shapes

## Output (commit before Stage 1)

```
DOCUMENT MODEL: <job> · <reading behavior> · <form>
AUDIENCE: <reader and context>
SUCCESS TEST: <observable outcome>
EVIDENCE: <source IDs and gaps>
SPEC: .hukuhaka/reports/tmp-draft/spec.md created
```

## Failure modes

- Turning discovery into a long questionnaire.
- Treating `report`, `deck`, or `dashboard` as the reader's job.
- Guessing evidence from memory or generated docs.
- Choosing a design style before understanding the document model.
- Skipping the draft write; Stage 1 re-reads it.
