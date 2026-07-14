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
| **hukuhaka-report-planner** | `0.4.0` | Supported | Claude Code, Codex | Researches visual-document requests, derives reader-focused structure and anchors, and records a validated build contract in `spec.md`. Explicit plan requests stop there; artifact requests continue from the contract. |
| **hukuhaka-codex** | `0.4.0` | Supported | Claude Code only | Claude Code plugin that delegates planning, review, debate, and transfer work to the Codex runtime. It is not installed into Codex itself. |
| **hukuhaka-project-mapper** | `1.1.2` | Deprecated | Claude Code only | Legacy `.claude/` codebase-documentation generator. Available by explicit install; critical fixes only. |
| **hukuhaka-ltm** | `0.5.0` | Deprecated | Claude Code only | Legacy three-tier long-term memory plugin. Available by explicit install; critical fixes only. |
| **CLAUDE.md template** | — | Supported | Claude Code only | Spec-first router for `~/.claude/CLAUDE.md`. |

Optional third-party extras (rtk, ccstatusline, agent-teams flag) ride along with the installer.

## Install

The public installer supports Claude Code, Codex, or both. The default
interactive flow asks for the target host before component selection. Explicit
non-interactive operations that omit `--host` still target Claude Code for
backward compatibility.

### Requirements and support

| Requirement | Support contract |
|-------------|------------------|
| Operating system | macOS or Linux |
| Python | Python 3.9+ available as `python3`; Python 2 is unsupported |
| Bootstrap | `bash` and `curl` for remote installation |
| Codex host | `codex` CLI |
| Windows | Native Windows is unsupported; WSL is not yet part of the tested matrix |

The installer uses only the Python standard library. If `python3` is missing,
the bootstrap prints the appropriate package-manager command; it executes that
command only when `--auto-install-deps` is explicitly supplied.

Claude Code deployment is transactional: registry JSON is validated before
files change, writes are atomic, interrupted runs are recovered on the next
install, and locally modified managed files require an explicit `--force`.
Optional extras are kept outside the core manifest and are never removed by a
core uninstall.

### Interactive install

```bash
curl -fsSL https://raw.githubusercontent.com/hukuhaka/hukuhaka-harness/main/scripts/install.sh | bash
```

The installer is interactive by default (host selector → component selector → dependency preflight → optional extras). Choose Claude Code, Codex, or both. Fresh installs and `--all` select supported components only. Deprecated components remain visible but default off; existing selections are preserved on re-run.

### Claude Code

Non-interactive variants retain Claude Code as the default host:

```bash
curl -fsSL .../install.sh | bash -s -- --all
curl -fsSL .../install.sh | bash -s -- --components hukuhaka-report-planner,hukuhaka-codex,claude-md
curl -fsSL .../install.sh | bash -s -- --components hukuhaka-project-mapper
curl -fsSL .../install.sh | bash -s -- --uninstall
```

The explicit `hukuhaka-project-mapper` example is a legacy install and prints a
deprecation warning.

### Codex

Use the same installer when you want host-aware selection, updates, and
uninstall behavior:

```bash
curl -fsSL https://raw.githubusercontent.com/hukuhaka/hukuhaka-harness/main/scripts/install.sh \
  | bash -s -- --host codex --all
```

The equivalent native Codex commands are:

```bash
codex plugin marketplace add hukuhaka/hukuhaka-harness
codex plugin add hukuhaka-report-planner@hukuhaka-harness
```

The Codex marketplace intentionally exposes only the components with native
Codex packaging. Invoke the planner explicitly as `$hukuhaka-report-planner`,
or let Codex select it from its description.

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
artifact requests use it as a preflight and continue building.

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
