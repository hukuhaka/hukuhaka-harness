# Changelog

## 0.4.0

- Renamed the upstream-derived `gpt-5-4-prompting` guidance to model-neutral `codex-prompting` for rescue, duel, and debate tasks.
- Made `codex-plan` the canonical plan/full contract with grounded seven-section plans, one correction turn, and per-step Claude verification.
- Scoped resumable plan threads separately from generic Codex tasks to prevent unrelated rescue context from contaminating plans.

## 0.3.0

- Added `/hukuhaka-codex:transfer` to import the current Claude Code transcript into a persistent Codex thread.
- Preserved the existing local review nudge and cross-session job retention while adopting the upstream transcript importer.

## 0.2.0

- Established independent hukuhaka-codex version and upstream tracking.
- Added stale-broker recycling after Codex CLI updates.
- Added bounded debate and opt-in proactive review/diagnosis controls.
- Adopted upstream v1.0.6 Git shell-expansion hardening.

## 0.1.0

- Initial hukuhaka-codex release, based on the official codex plugin v1.0.4.
