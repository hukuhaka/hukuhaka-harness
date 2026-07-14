---
role: optional design-direction reference
use_when: density, grouping, reading rhythm, responsive behavior, or print margins are unresolved
do_not_use_when: exact layout values are not needed at planning time
style_risk: fixed spacing scales and page recipes make different forms share one rhythm
---

## Planning questions

- What must be visible in one scan, viewport, slide, or printed page?
- Which units should read as groups, and which need a strong break?
- Where does density help comparison, and where does it obstruct comprehension?
- What changes across target widths or print dimensions?
- Which anchors require stable aspect ratios, minimum widths, or overflow behavior?

The builder may derive a compact scale from the chosen medium and concept. The planner guides
relative rhythm and grouping, not exact pixel or millimeter tokens.

## Scan rhythm (density variation per page)

A scan-oriented artifact usually needs visible grouping and changes in emphasis. A lookup
surface may instead need deliberately consistent density. Derive rhythm from reading behavior;
do not require a hero metric or a breathable band on every page.

## Anti-defaults and failure modes

- Section gap = paragraph gap — sections dissolve into prose
- Margin-collapse not understood — vertical gaps double-count or disappear under flex/grid
- Edge-to-edge content on wide viewports — long lines unreadable; cap measure (see `craft/typography.md`)
