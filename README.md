# hukuhaka-harness

A small distribution of coding-agent workflows for Claude Code and Codex. Each
component declares its supported host explicitly; sharing a repository does not
imply that a Claude Code plugin is portable to Codex.

## Who this is for

- You use Claude Code, Codex, or both and want reusable workflows with honest host boundaries.
- You want evidence-backed document planning to constrain artifact construction.
- You need a Claude-to-Codex collaboration harness without pretending it is a native Codex plugin.

## What's in the bundle

| Component | Version | Status | Hosts | What it gives you |
|-----------|---------|--------|-------|-------------------|
| **hukuhaka-report-planner** | `0.5.0` | Supported | Claude Code, Codex | Researches visual-document requests and records a validated `spec.md`. Explicit plan requests stop there; artifact requests delegate construction and visual verification to one designer subagent. |
| **hukuhaka-engineering-plan** | `0.1.0` | Supported | Claude Code, Codex | Produces repository-grounded implementation plans with explicit contracts, counterexample checks, and requirement-to-verification mapping. |
| **hukuhaka-codex** | `0.4.0` | Supported | Claude Code only | Claude Code plugin that delegates planning, review, debate, and transfer work to the Codex runtime. It is not installed into Codex itself. |
| **CLAUDE.md template** | — | Supported | Claude Code only | Shared scoped-change and verification policy with Claude-specific `spec.md` sign-off and attribution-free commits, deployed to `~/.claude/CLAUDE.md`. |
| **AGENTS.md template** | — | Supported | Codex only | Codex policy for scoped change previews, evidence-backed verification, compact-resilient task state, and a safe local Git lifecycle, merged into `$CODEX_HOME/AGENTS.md`. |

## Install

The public installer supports Claude Code, Codex, or both. The default
interactive flow shows Claude Code and Codex as separate terminal sections.
Explicit non-interactive operations that omit `--host` still target Claude
Code for backward compatibility.

### Requirements and support

| Requirement | Support contract |
|-------------|------------------|
| Operating system | macOS or Linux |
| Python | Python 3.9+ available as `python3`; Python 2 is unsupported |
| Bootstrap | `bash` and `curl` for remote installation |
| Claude Code host | `claude` CLI |
| Codex host | `codex` CLI |
| Windows | Native Windows is unsupported; WSL is not yet part of the tested matrix |

The installer uses only the Python standard library. If `python3` is missing,
the bootstrap prints the appropriate package-manager command.

Claude Code deployment is transactional: registry JSON is validated before
files change, writes are atomic, interrupted runs are recovered on the next
install, and locally modified managed files require an explicit `--force`.

The Claude and Codex instruction templates are separate sources. Both
distinguish analysis from mutation authority, preserve pre-existing work, and
keep push and other external actions explicitly opt-in. The Claude template
additionally protects `spec.md` contracts and attribution-free commits. The
Codex installer merges only a marked managed block into
`$CODEX_HOME/AGENTS.md`, preserves user text outside that block, and removes
only the managed block on uninstall. `CODEX_HOME` defaults to `~/.codex`.

### Interactive install

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/hukuhaka/hukuhaka-harness/main/scripts/install.sh)"
```

The installer uses an arrow-key terminal selector on standard input/output:
Up/Down moves, Space selects, and Enter applies. It detects the `claude` and
`codex` CLIs, shows each available host separately, and disables a host whose
CLI is missing. Each host section selects its own components and can reset
managed plugins and skills before installing. The reset can optionally include
the managed `CLAUDE.md` or `AGENTS.md` template. Codex memory, `config.toml`,
and Claude settings unrelated to the harness are never reset. The final choices
are `Install / Exit`.

The interactive command uses `bash -c` so stdin remains attached to the
terminal. `curl ... | bash` remains supported for explicit non-interactive
flags, but cannot accept arrow-key input because the script itself occupies
stdin.

Without a TTY and without explicit selection flags, the installer keeps the
current components and adds supported defaults for the selected host. The
non-interactive default host remains Claude Code. Use `--add` for an incremental
addition or `--components` to declare the complete desired component set.

### Claude Code

Non-interactive variants retain Claude Code as the default host:

```bash
curl -fsSL .../install.sh | bash -s -- --all
curl -fsSL .../install.sh | bash -s -- --components hukuhaka-report-planner,hukuhaka-engineering-plan,hukuhaka-codex,claude-md
curl -fsSL .../install.sh | bash -s -- --uninstall
curl -fsSL .../install.sh | bash -s -- --all --reset-before-install
```

### Codex

Use the same installer when you want host-aware selection, updates, and
uninstall behavior:

```bash
curl -fsSL https://raw.githubusercontent.com/hukuhaka/hukuhaka-harness/main/scripts/install.sh \
  | bash -s -- --host codex --all
```

For scripted clean reinstalls, use `--reset-before-install`. Add
`--reset-templates` only when the installer-managed instruction template should
also be replaced. Modified managed files stop the reset unless `--force` is
explicitly supplied.

The equivalent native Codex commands are:

```bash
codex plugin marketplace add hukuhaka/hukuhaka-harness
codex plugin add hukuhaka-report-planner@hukuhaka-harness
codex plugin add hukuhaka-engineering-plan@hukuhaka-harness
```

The Codex marketplace intentionally exposes only the components with native
Codex packaging. Invoke the document planner as `$hukuhaka-report-planner` and
the engineering planner as `$engineering-plan`, or let Codex select them from
their descriptions. The `agents-md` template is installed by this repository's
host-aware installer rather than the native plugin marketplace.

### Both hosts

```bash
curl -fsSL https://raw.githubusercontent.com/hukuhaka/hukuhaka-harness/main/scripts/install.sh \
  | bash -s -- --host both --all
```

## Report planner workflow

The same skill tree is used by both hosts:

```text
Claude Code: /hukuhaka-report-planner:hukuhaka-report-planner
Codex:       $hukuhaka-report-planner
```

Both write `.hukuhaka/reports/<short-name>/spec.md`, a host-neutral compatibility
contract that either host can consume. Existing `.claude/reports/` plans remain a
read-only fallback. The shared workflow discovers the reader job and evidence, explores
the document structure and anchors, then locks a selective-reference design and
build contract. Explicit planning requests stop at the validated spec; immediate
artifact requests use it as a preflight and delegate construction plus visual
verification to one designer subagent.

## Engineering plan workflow

The same portable Skill is packaged for both hosts:

```text
Claude Code: /hukuhaka-engineering-plan:engineering-plan
Codex:       $engineering-plan
```

It inspects the repository before planning, defines observable behavior before
file changes, challenges important invariants with concrete counterexamples,
revises contradictions in the main plan, and ends with `Ready`,
`Ready with assumptions`, or `Blocked`.

## Design principles

- **Host support is explicit.** A component is published for a host only when its native package and validation exist.
- **One portable workflow core.** Dual-host components share skill content and keep host-specific manifests at the boundary.
- **Plan before build.** Report framing, figures, and structure are agreed before a separate builder creates the artifact.
- **Idempotent install.** Detect state → install/skip/remove the delta. Re-runs are safe.

## Dependencies

| | Required | Optional |
|--|----------|----------|
| **Base** | Python 3.9+ (`python3`), `bash`; `curl` for remote bootstrap | `git` |
| **Codex host** | `codex` | — |
| **Extras** | — | `brew` (rtk on macOS), `node`/`npx` (ccstatusline) |

The installer's preflight check enumerates these per selected component and offers to auto-install via the detected package manager.

## License

This repository is MIT-licensed except for `marketplace/hukuhaka-codex`, an
Apache-2.0 derivative of OpenAI's Codex plugin for Claude Code. See the root
[LICENSE](LICENSE) and the plugin's `LICENSE` and `NOTICE` files.
