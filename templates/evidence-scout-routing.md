## Evidence scout routing

- Use `evidence-scout` for bounded, independent, read-only repository exploration when delegation reduces the primary context. Run one per genuinely independent scope, use as many as are useful within the concurrency ceiling, and group questions that share sources.
- Use deterministic tools directly for a small lookup. Spawn scouts with `fork_turns="none"` and send only `question`, `roots`, optional `base`, `scope`, `coverage`, and optional `constraints`.
- Keep scope decisions, ambiguity, writes, Git and external actions, and final verification in the primary agent. Reconcile returned packets and request expansion only for named evidence IDs that can change the answer.
