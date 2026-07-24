---
name: hukuhaka-report-planner
description: "Plan or preflight an evidence-based visual document before it is built. Use for reports, memos, decks, dashboards, handbooks, explainers, postmortems, posters, and similar artifacts when the agent must research the material, identify the reader's job, design the information structure and anchors, synthesize selective references without cloning them, and record a build contract in spec.md. An explicit planning request stops at the validated spec; an immediate artifact request delegates construction from that contract. Skip only when the user explicitly asks to bypass planning or wants ordinary prose, API reference, marketing copy, or a changelog."
---

This skill turns a vague visual-document request into an evidence-backed build contract.
It plans reports and also memos, handbooks, dashboards, explainers, decks, posters, and
other artifacts whose structure depends on the reader's job.

It does not restore the retired gated builder. Semantic decisions are locked, design
decisions are guided, and exact composition remains open.

## Workflow

Open each stage file before executing it; do not work from memory.

| # | File | Purpose | Verification gate |
|---|---|---|---|
| 0 | `stages/0-frame.md` | **Discover** the document job, reading behavior, form, audience, success test, material, and evidence gaps | Ask only when a missing decision blocks useful planning |
| 1 | `stages/1-plan.md` | **Explore** the evidence, structural trunk, units, anchors, and reference-free design concept; then select references | Ask only when materially different directions remain |
| 2 | `stages/2-lock.md` | **Lock** the final spec, build contract, and acceptance tests; validate and hand off | Final spec passes `scripts/validate-spec.sh` |

## Invocation modes

- **Plan mode:** when the user explicitly asks for a plan, write and validate `spec.md`,
  report its path, and stop.
- **Build-preflight mode:** when the user asks for the artifact itself, run all three stages,
  then delegate construction to one `artifact-designer` subagent using
  `references/build-handoff.md`.
- **Bypass:** skip the planner only when the user explicitly asks to bypass planning.

## Output

```
.hukuhaka/reports/<short-name>/
  └── spec.md          ← evidence-backed document and build contract
```

See `references/spec-schema.md` for the exact shape. `.hukuhaka/reports/` is the single
host-neutral write location shared by Claude Code and Codex.

## Path resolution

- Write new drafts and final specs only under `.hukuhaka/reports/`.
- When opening an existing plan, prefer `.hukuhaka/reports/<short-name>/spec.md`.
- If no new-path plan exists, read `.claude/reports/<short-name>/spec.md` as a legacy fallback.
- Legacy paths are read-only. Never dual-write, delete, or silently rewrite a legacy plan.
- When the user explicitly continues a legacy plan, preserve the old file and write the next
  revision under `.hukuhaka/reports/`.

## Core rules

- Start from the **reader's job**, not from a report template.
- Verify named entities and claims against source. Mark inference and unresolved gaps.
- Define the structural **trunk** before listing units.
- Use **anchors**, not mandatory figures. An anchor may be a chart, table, diagram,
  screenshot, code example, checklist, quotation, or prose explanation.
- Every anchor must answer a reader question and be supported by evidence. A unit may be
  prose-only when prose is the clearest form.
- Form a reference-name-free design concept before reading optional craft references.
- Read `references/principles.md` and `references/reference-index.md`; select no more than
  three optional references. Never read the whole reference directory by default.
- Match gates, proposals, and handoff text to the user's conversation language. Bundled
  references and examples are English source material, not a required response language.
- Record what the plan borrows, transforms, and rejects. A reference supplies a mechanism,
  never the whole design.
- When the user explicitly supplies a `DESIGN.md`, record its path as a selected design source;
  do not auto-load one merely because it exists in the project.
- Keep planning and construction in separate contexts. In build-preflight mode, the parent
  validates the spec and delegates one build; it does not construct the artifact itself.
- Do not create pinned tokens, fixed components, modes, registers, or per-page gates.
- Keep exact layout, decorative geometry, and micro-composition in the `open` budget.
- Keep contract depth proportional to the artifact. For a small memo, prefer two to four
  units, zero to three non-prose anchors, and four to six acceptance tests. Use one concise
  sentence per field and source IDs instead of repeating the same facts across blocks.

## References

- `references/spec-schema.md` — final `spec.md` contract
- `references/principles.md` — mandatory, style-neutral quality principles
- `references/reference-index.md` — routing table for optional craft files
- `references/directions.md` — optional vocabulary for design-direction mechanisms; open
  only after forming a reference-name-free concept
- `references/build-handoff.md` — portable designer payload and host adapters
- `references/craft/*.md` — optional problem-specific knowledge; select zero to three
- `scripts/validate-spec.sh [<spec.md>]` — required final structural check

Resolve bundled reference and script paths relative to this `SKILL.md` file. Do not assume
that the user's project root contains the planner's `scripts/` or `references/` directories.
