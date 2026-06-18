---
role: figure/structure reference for the report plan (not injected anywhere — there is no build stage)
topic: strongest for clean analytic registers (audit, brief, dashboard, incident, status)
---

## Core principle — never the generic-AI look

Never default to the convergence aesthetic: Inter + gray text + purple gradients. Pick a deliberate font pairing that matches the register's identity, and load it explicitly (Google Fonts `@import` or bundled) — a font choice that silently falls back to the system stack is no choice at all.

## Weight + role mapping

| Role | Weight | Notes |
|---|---|---|
| Display (cover wordmark, page hero) | 700–800 | tight tracking (-0.02em at >48px) |
| Headline (section finding) | 600 | slight negative tracking at >24px |
| Body | 400 (or 350 for long passages) | line-height 1.45–1.55 |
| Eyebrows / chrome / metric units | mono 500–600 uppercase | tracked +0.04–0.08em |
| Code / file refs / tabular numerals | mono 400 | `font-variant-numeric: tabular-nums` on every metric |

## Register-specific pairing guidance

- **Clean analytic registers** (technical audit, executive brief, status, incident, dashboard): a deliberate grotesque + matching mono. Good choices: Geist + Geist Mono, IBM Plex Sans + IBM Plex Mono (more engineering character), Söhne + Söhne Mono (if licensed; sharper, suits IR/brief)
- **Editorial-academic / paper review**: serif display (Source Serif, Crimson Text) over a grotesque body — defend why serif fits the authority claim
- **IR-style earnings deck**: high-contrast serif display (Fraunces optical-sized, Tiempos) if the deck's gravity demands it
- **Academic poster**: dense humanist sans (IBM Plex Sans) often wins at small sizes in tight layouts
- **Long-form editorial / newsletter**: transitional serif body (Charter, Source Serif) when reading time is long

Pick one pairing per artifact and defend deviations in writing — pairings are decisions, not a menu to browse.

## Anti-defaults (always avoid)

- Inter as primary or fallback — the single most identifying AI-convergence font
- Bare system font stack (`-apple-system, BlinkMacSystemFont, ...`) — careless default; always pick
- Multiple display weights (300/400/500/700) on the same surface — 2 weights max per role
- Mono in body text — mono is for taxonomy / metrics / code, never narrative
- Mid-gray text to fake hierarchy — use weight instead

## Font-family chains (required)

Every `font-family` declaration MUST list curated alternates before the generic family, and MUST end in a generic family (`sans-serif`, `serif`, `monospace`) as last resort only.

Wrong (silent fail to system UI font): `font-family: 'Geist', -apple-system, BlinkMacSystemFont, sans-serif;`
Right: `font-family: 'Geist', 'IBM Plex Sans', 'Söhne', sans-serif;`

Validate offline / network-throttled / print-to-PDF — the rendered identity must still read as the chosen pairing's class, not as the OS UI font.
