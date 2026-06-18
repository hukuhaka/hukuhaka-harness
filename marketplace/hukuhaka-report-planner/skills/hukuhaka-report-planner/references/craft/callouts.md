---
role: figure/structure reference for the report plan (not injected anywhere — there is no build stage)
topic: sidebars, margin notes, highlight boxes, pull-quotes
---

## When to use

A callout is for content **adjacent** to the main flow that should not be a body paragraph. Use sparingly — every callout costs scan attention.

Use for: definition or footnote-style detail; warning, caveat, or scope limit on a finding; quote from source material that anchors a claim; recommendation or next-step under a finding.

Do NOT use for: a transitional sentence (rewrite as a body bullet); multiple paragraphs (that is a section, not a callout); decoration (callouts are content — if it doesn't add, drop it).

## Sidebar (vertical block, gutter or in-flow)

- Width: 180-260px in left/right margin, OR full-content width if in-flow
- Background: subtle paper tint OR no background + 2px left rule in accent
- Header: mono uppercase eyebrow label (`NOTE`, `CAVEAT`, `SOURCE`), tracked +0.04em
- Body: same size as body text, or 1-2px smaller
- Never combine heavy border + heavy background + accent header simultaneously — pick one or two

## Margin note (Tufte-style)

Small callout in the page margin, near the body sentence it annotates.

- Width: 140-200px
- Type: serif italic body or mono small — visually distinct from body
- No background — only spacing isolates
- Best on wide-margin layouts (audit, brief). Useless on dashboard/poster

## Highlight box (in-flow, severity-tinted)

In-flow box for a finding or warning that must not be skipped.

- Background: very subtle tint of the relevant semantic color (warning red-tint, success green-tint)
- Left border: 3-4px in the full semantic color
- Header: mono eyebrow + finding text in body weight 600
- Padding: generous, consistent with section spacing
- One per page max — overuse turns them into chrome

## Pull-quote (editorial registers only)

Research-recap / customer-facing editorial registers. Almost never in audit/dashboard/incident.

- Type: serif italic display size (24-32px), slightly dimmed ink
- Width: 75% of content measure, indented
- No quote marks — typography carries the quotation

## Don'ts

- Yellow `#fef9c3` background with grey border — generic Tailwind warning look
- Emoji icon header — kills authority, especially in audit/IR registers
- Callout with marketing-tagline body ("Did you know...") — wrong register
- Box-shadow on the callout — chart-junk
- Multiple callouts in a row — they cancel each other; consolidate or restructure
- Heavy 2-3px border on all 4 sides — generic admonition look
- Every section has a callout — they become chrome, not content
- Callout repeats body content — delete the callout or delete the body
- Decorative use (a "Quick Stats" callout that's actually a small table) — make it a real table or remove
- Wrong semantic color (success tint on a warning) — semantics exhausted
- Margin note on narrow layouts (dashboard) — nowhere to live, collides with content
