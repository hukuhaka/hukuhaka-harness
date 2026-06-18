---
stage: 0
purpose: turn a natural-language request into a light, confirmed Frame (purpose / audience / prose level / design direction; form optional) — the shaping inputs the plan is built on
prereq: user issued a report-shaped request
deliverable: .claude/reports/tmp-draft/spec.md created with ONLY the Frame block
verification_gate: user confirms/edits the Frame in one exchange
---

## What this stage does

The entry is a sentence — "이 실험 결과 report로 만들고 싶어", "write up the Q1 benchmark",
"이 프로젝트 구조 정리해줘". Stage 0 does the framing the user never types: a **brief look at
the material, then a proposed Frame for confirmation**. This is light — one short exchange,
not a gated interrogation. The deeper read and the figure/section proposal are Stage 1.

The Frame is four lines (plus optional `form`). It is deliberately small: no mode, no
register, no axis table. Just enough shaping that the Stage-1 plan is grounded, and the
user's two biggest levers — **prose level** (how much explanatory text) and **design
direction** (the taste/look) — are captured before any structure is proposed.

## Process

1. **Detect intent + material.** From the request, identify what the report is about and
   what material backs it (experiment results, code, data, findings). If too thin to frame
   (no identifiable subject), ask ONE clarifying question — otherwise proceed.

2. **Brief look.** Glance at the material enough to frame it — reuse existing `.claude/`
   docs (`map.md`, `design.md`, `README`) when present; otherwise a light look at the
   relevant files/data. Orient, don't audit — Stage 1 does the deep read.

3. **Propose the Frame**, each line a recommendation (alternatives only where genuinely open):
   - **purpose** — what the report is for (보고용 발표 / 개인 정리 / 공유 문서 / go-no-go 논의 …).
   - **audience** — who reads it, in what context, for what decision or lookup.
   - **prose level** — `brief` (figure 중심, 설명 최소 — "나만 볼거라 간략하게") or `full`
     (설명 산문 포함 — "보고용"). Infer from purpose + audience; surface for confirm.
   - **design direction** — one line of visual intent: palette temperature, canvas, accent
     strategy, optionally a reference look (e.g. `cool-neutral, pure-white canvas, single
     electric-blue accent` or `warm editorial, cream paper`). The taste lever. If the user
     has previously rejected a look (e.g. warm/yellowish), never re-propose it.
   - **form** (optional) — web doc / deck / print PDF. Omit if undecided; it can be set later.

4. **GATE** — show the Frame, ask: "이대로 갈까요, 아니면 한 줄씩 고쳐주세요." One exchange;
   iterate only if the user corrects.

5. **Write** `.claude/reports/tmp-draft/spec.md` with ONLY the `## Frame` block per
   `references/spec-schema.md`. spec.md is born here. The directory is `tmp-draft`; Stage 1
   renames it from the subject.

## Required reading

- `references/spec-schema.md` — the Frame block shape (this stage produces it)

## Output (commit before Stage 1)

```
FRAME confirmed:
  purpose:          <one line>
  audience:         <one line>
  prose level:      <brief | full>
  design direction: <one line>
  form:             <web doc | deck | print>   (optional)
SPEC: .claude/reports/tmp-draft/spec.md created (Frame block only)
```

## Failure modes

- **Over-framing** — turning the four lines into a long questionnaire. Stage 0 is one light
  exchange; the substance (figures, sections) is Stage 1.
- **Skipping the look and guessing** — the Frame must be grounded in a glance at the material.
- **Proposing a design direction the user has rejected** — taste rejections persist across
  reports; check the conversation and recorded feedback.
- **Defaulting prose level to `full`** because it is "a report" — half the real uses are
  personal/quick where `brief` is correct. Ask via purpose+audience.
- Proposing sections or figures here — that is Stage 1. Stage 0 only fixes the shaping inputs.
- Skipping the disk write — Stage 1 re-reads `tmp-draft/spec.md`; without it the chain breaks.
