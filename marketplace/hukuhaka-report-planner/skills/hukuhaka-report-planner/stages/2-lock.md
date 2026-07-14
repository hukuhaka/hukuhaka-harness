---
stage: 2
purpose: lock the evidence-backed document plan, build contract, and acceptance tests
prereq: Stage 1 completed Evidence, Structure, Anchors, and Design Direction blocks
deliverable: validated .hukuhaka/reports/<short-name>/spec.md
verification_gate: scripts/validate-spec.sh passes
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

3. **Check anchor validity.** Every non-prose anchor must have supporting evidence, a selected
   form that can represent it, an expected takeaway, and any material caveat. Repetition is
   acceptable when the same comparison grammar is genuinely required.

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

7. **Finalize and validate.** Rename `.hukuhaka/reports/tmp-draft/` to
   `.hukuhaka/reports/<short-name>/`, write the complete schema, and run:

   ```bash
   bash "<resolved-skill-directory>/scripts/validate-spec.sh" \
     .hukuhaka/reports/<short-name>/spec.md
   ```

   Resolve `<resolved-skill-directory>` from the loaded `SKILL.md` location; do not look for
   the script in the user's project. Fix structural failures before handoff.

8. **Handoff by invocation mode.**
   - `plan`: report the validated spec path and stop.
   - `build-preflight`: continue building in the same task. Read the final spec first, preserve
     `locked`, stay within `guided`, and exercise freedom only in `open`. Run the recorded
     acceptance tests against the finished artifact.

## Failure modes

- Converting `guided` preferences into exact CSS tokens or fixed components.
- Leaving core decisions in `open` and forcing the builder to reinterpret them.
- Treating validator success as semantic or visual proof.
- Building before the final spec passes validation.
