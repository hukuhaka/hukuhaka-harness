# spec.md schema — document build contract

This skill produces one planning artifact at

```
.hukuhaka/reports/<short-name>/spec.md
```

An explicit plan request stops here. An immediate artifact request uses this validated file
as a preflight contract and continues to build.

`<short-name>` is derived in Stage 2 from the subject: lowercase kebab-case, at most 24
characters. Stage 0 creates `.hukuhaka/reports/tmp-draft/spec.md`; Stage 2 renames the
directory and validates the complete file.

`.claude/reports/<short-name>/spec.md` is a read-only compatibility fallback for plans
created before `0.4.0`. New and updated specs are written only to `.hukuhaka/reports/`;
the planner does not dual-write, delete, or silently migrate legacy files.

## spec.md — full template

```markdown
# <title> — document plan — <YYYY-MM-DD>

## Document Model

- job: <decide | explain | reference | monitor | persuade | teach | record>
- reading behavior: <linear | scan | random-access | live>
- form: <web document | deck | dashboard | print/PDF | poster | ...>
- audience: <reader, context, and expected prior knowledge>
- success test: <observable reader outcome>
- prose level: <brief | balanced | full>

## Evidence

- established: <verified facts that shape the plan>
- source S1: <path, dataset, user brief, or verified URL> — supports: <claims/units/anchors>
- source S2: <...>
- conflict: <conflicting evidence, or none>
- gap: <missing or unverified evidence, or none>
- freshness: <date-sensitive boundary, or not applicable>

## Structure

- trunk: <central claim, decision, sequence, taxonomy, comparison, timeline, map, or loop>
- U1 <unit title>
  - reader question: <question this unit answers>
  - reader outcome: <what the reader knows, decides, finds, or does>
  - evidence: <S1, S2, or explicit inference>
  - anchor: <A1 | prose>
- U2 <unit title>
  - reader question: <...>
  - reader outcome: <...>
  - evidence: <...>
  - anchor: <A2 | prose>

## Anchors

### A1 <anchor name>

- reader question: <question answered>
- evidence: <S1, fields/range, or explicit qualitative material>
- selected form: <chart | table | diagram | screenshot | code | checklist | quote | ...>
- takeaway: <what the reader should see>
- caveat: <uncertainty or validity condition, or none>

<!-- If every unit is intentionally prose-only, replace A1 with: -->
<!-- - none: <why prose is the clearest form> -->

## Design Direction

- concept: <reference-name-free description of density, rhythm, voice, geometry, color semantics, and anchor treatment>
- selected references: <zero to three paths, or none>
- borrow: <mechanisms adopted>
- transform: <how they change for this document>
- reject: <mechanisms intentionally excluded>
- clone risk: <how visual convergence will be avoided>

## Build Contract

- locked: <facts, source boundaries, reader job, structure, anchor meaning, accessibility>
- guided: <density, type roles, color roles, rhythm, surface and anchor grammar>
- open: <exact composition, decorative geometry, micro-layout, implementation details>

## Acceptance Tests

- [ ] <Document Model success test>
- [ ] Evidence fidelity: factual claims and anchors resolve to listed sources.
- [ ] Structure scan: the trunk and unit sequence are recoverable from headings and anchors.
- [ ] Anchor validity: every non-prose anchor answers its reader question without overstating evidence.
```

## Rules

- The complete spec contains all seven level-two blocks in the order above.
- Every unit has a reader question, reader outcome, evidence, and an anchor or `prose`.
- Every non-prose anchor has evidence, selected form, takeaway, and caveat.
- A prose-only document uses `- none:` in Anchors and explains why.
- Design Direction starts without reference names, then records zero to three selected
  references and the borrow/transform/reject decisions.
- Build Contract guides visual language without specifying CSS tokens or fixed components.
- `validate-spec.sh` is required before handoff. It checks structure, not semantic or visual
  quality; recorded acceptance tests still have to be run against the finished artifact.
