# Provenance and upstream status

`hukuhaka-codex` is a modified distribution of OpenAI's **codex** plugin for
Claude Code (Apache-2.0). See `NOTICE` for the modification statement.

## Version coordinates

- Local plugin version: `0.4.1`
- Fully incorporated upstream baseline: `v1.0.4`
  (`807e03ac9d5aa23bc395fdec8c3767500a86b3cf`), adapted for the local namespace
- Last audited upstream release: `v1.0.6`
  (`db52e28f4d9ded852ab3942cea316258ae4ef346`)
- Upstream repository: <https://github.com/openai/codex-plugin-cc>

The baseline and last-audited coordinates are different by design. Auditing a
release does not mean every upstream change was incorporated.

## Current divergence summary

- Namespace references use `/hukuhaka-codex:*` and
  `hukuhaka-codex:codex-rescue`.
- Local commands: `plan`, `review-loop`, `duel`, `debate`, and `full`.
- Local skill: `codex-plan`; the upstream `gpt-5-4-prompting` guidance is
  adapted as model-neutral `codex-prompting`.
- Local hook/runtime behavior: bounded proactive rescue, report-only review,
  Stop-continuation loop prevention, five-minute Bash failure detection, and
  stale-broker recycling.
- Selectively adopted after v1.0.4: app-server attestation capability, startup
  stderr propagation, the v1.0.5 external-agent session importer, and v1.0.6
  Git shell-expansion hardening.
- `/hukuhaka-codex:transfer` is a standalone handoff. It is not automatically
  invoked by `duel`, `debate`, or `full`, which retain independent-solving
  semantics.
- `plan` and `full` use the local canonical `codex-plan` contract and a
  workflow-scoped runtime thread. General prompting guidance no longer owns
  plan behavior.

Detailed component decisions and compatibility evidence are maintained in the
private source repository under `docs/hukuhaka-codex/`. Those internal records
are intentionally not included in the public release mirror.
