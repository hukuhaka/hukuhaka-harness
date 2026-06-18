---
role: figure/structure reference for the report plan (not injected anywhere — there is no build stage)
topic: technical-audit / forensic-incident / reference-handbook registers, where code is evidence
---

## When code belongs

- **Audit**: regularly — code is the primary evidence
- **Incident**: configuration excerpts, log lines, query strings, stack traces
- **Brief / IR-deck / Poster**: rarely — only if the snippet IS the finding
- **Dashboard**: configuration blocks only

If the snippet exceeds 15 lines, it likely belongs in an appendix or external link. The body should show the diff or the critical 3-5 lines.

## Typography

- Family: the report's mono face at body size or 1-2px smaller
- Weight: 400 for normal code; 500 for highlighted lines
- Line-height: 1.4-1.5 (denser than body prose)
- Tabular-nums on any inline metrics within code

## Syntax highlighting

If used, must be **subdued**: keywords in body ink weight 600, NOT colored; strings in a single muted accent; comments dimmed italic; numbers + booleans in body ink, no color change. Plain (no highlighting) is often better — typography carries the structure.

## Line numbers

Optional — only if prose explicitly references them ("see line 42"). If included: mono, dimmed, right-aligned, clearly gapped from the code. Never include unreferenced — pure chrome.

## Background + padding

- Background: subtle warm tint, NOT pure white
- Padding: generous and uniform; slightly tighter for inline-feel blocks
- Border: hairline 1px OR no border. Never both background AND heavy border
- Border-radius: 0 or 2-3px. Larger reads as generic card

## Inline code

Same mono family at 0.9x body size; very subtle tint background OR no background + body ink at weight 500. Padding 0 1-2px. Never bordered.

## Highlighting within a block

- Highlighted line: 2-3px left border in the register accent, NO background change (it competes with syntax)
- Highlighted token (rare): mono weight 600, no color change
- Diff: `+` added = green left border; `-` removed = red left border; the +/- symbols mono dimmed at 0.7x opacity

## Caption / filename

Every code block needs a small mono caption above showing filename or context (`src/handler.ts`, `config.yaml:42`). A code block without context leaves the reader hunting.

## Don'ts

- VSCode dark theme code blocks on a light report — register collision
- Rainbow syntax highlighting (purple keywords, orange strings, green comments)
- Heavy drop-shadow on code block — generic blog look
- Light-gray monospace on light-gray bg — illegible
- Inline code with rounded pill + accent bg — over-decorated
- "Copy" button overlay — interaction chrome, irrelevant in scan-mode report
- 20+ line code blocks in body — break into 3-5 line excerpts with prose between
- Long lines that wrap — adjust measure or use horizontal scroll with caption marker
- Syntax highlighting that distracts from the finding — strip the syntax
