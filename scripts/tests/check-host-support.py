#!/usr/bin/env python3
"""Validate the declared Claude Code/Codex component boundaries."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PLANNER = ROOT / "marketplace" / "hukuhaka-report-planner"
WORKLOG = ROOT / "marketplace" / "hukuhaka-worklog"
CATALOG = ROOT / "components.json"
CLAUDE_MANIFEST = PLANNER / ".claude-plugin" / "plugin.json"
CODEX_MANIFEST = PLANNER / ".codex-plugin" / "plugin.json"
WORKLOG_CLAUDE_MANIFEST = WORKLOG / ".claude-plugin" / "plugin.json"
WORKLOG_CODEX_MANIFEST = WORKLOG / ".codex-plugin" / "plugin.json"
MARKETPLACE = ROOT / ".agents" / "plugins" / "marketplace.json"
SKILL = PLANNER / "skills" / "hukuhaka-report-planner" / "SKILL.md"
WORKLOG_SKILL = WORKLOG / "skills" / "worklog" / "SKILL.md"
WORKLOG_OPENAI = WORKLOG / "skills" / "worklog" / "agents" / "openai.yaml"
WORKLOG_SCRIPT = WORKLOG / "skills" / "worklog" / "scripts" / "worklog.py"
WORKLOG_HOOKS = WORKLOG / "hooks" / "claude-codex-hooks.json"
HOST_SUPPORT = ROOT / "docs" / "host-support.md"
DESIGNER_SKILL = PLANNER / "skills" / "artifact-designer" / "SKILL.md"
DESIGNER_AGENT = PLANNER / "agents" / "artifact-designer.md"
BUILD_HANDOFF = PLANNER / "skills" / "hukuhaka-report-planner" / "references" / "build-handoff.md"
CLAUDE_TEMPLATE = ROOT / "templates" / "CLAUDE.md"
AGENTS_TEMPLATE = ROOT / "templates" / "AGENTS.md"


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def readme_row(readme: str, name: str) -> str:
    return next((line for line in readme.splitlines() if line.startswith(f"| **{name}** |")), "")


def main() -> int:
    errors: list[str] = []

    for path in (
        CATALOG,
        CLAUDE_MANIFEST,
        CODEX_MANIFEST,
        WORKLOG_CLAUDE_MANIFEST,
        WORKLOG_CODEX_MANIFEST,
        MARKETPLACE,
        SKILL,
        WORKLOG_SKILL,
        WORKLOG_OPENAI,
        WORKLOG_SCRIPT,
        WORKLOG_HOOKS,
        DESIGNER_SKILL,
        DESIGNER_AGENT,
        BUILD_HANDOFF,
        CLAUDE_TEMPLATE,
        AGENTS_TEMPLATE,
    ):
        require(path.is_file(), f"missing required dual-host file: {path.relative_to(ROOT)}", errors)
    if errors:
        return report(errors)

    claude = load_json(CLAUDE_MANIFEST)
    codex = load_json(CODEX_MANIFEST)
    worklog_claude = load_json(WORKLOG_CLAUDE_MANIFEST)
    worklog_codex = load_json(WORKLOG_CODEX_MANIFEST)
    catalog = load_json(CATALOG)
    marketplace = load_json(MARKETPLACE)
    skill = SKILL.read_text(encoding="utf-8")
    worklog_skill = WORKLOG_SKILL.read_text(encoding="utf-8")
    worklog_openai = WORKLOG_OPENAI.read_text(encoding="utf-8")
    worklog_script = WORKLOG_SCRIPT.read_text(encoding="utf-8")
    worklog_hooks = load_json(WORKLOG_HOOKS)
    host_support = HOST_SUPPORT.read_text(encoding="utf-8") if HOST_SUPPORT.is_file() else ""
    designer_skill = DESIGNER_SKILL.read_text(encoding="utf-8")
    designer_agent = DESIGNER_AGENT.read_text(encoding="utf-8")
    build_handoff = BUILD_HANDOFF.read_text(encoding="utf-8")
    claude_template = CLAUDE_TEMPLATE.read_text(encoding="utf-8")
    agents_template = AGENTS_TEMPLATE.read_text(encoding="utf-8")

    require(claude.get("name") == codex.get("name"), "Claude and Codex manifest names differ", errors)
    require(claude.get("version") == codex.get("version"), "Claude and Codex manifest versions differ", errors)
    require(claude.get("skills") == "./skills/", "Claude manifest must expose the shared ./skills/ tree", errors)
    require("agents" not in claude,
            "Claude manifest must rely on default agents/ discovery for current CLI compatibility", errors)
    require(codex.get("skills") == "./skills/", "Codex manifest must expose the shared ./skills/ tree", errors)
    require("agents" not in codex, "Codex manifest must not claim unsupported packaged agents", errors)
    require(worklog_claude.get("name") == worklog_codex.get("name"),
            "worklog Claude and Codex manifest names differ", errors)
    require(worklog_claude.get("version") == worklog_codex.get("version"),
            "worklog Claude and Codex manifest versions differ", errors)
    require(worklog_claude.get("skills") == "./skills/",
            "worklog Claude manifest must expose the shared ./skills/ tree", errors)
    require(worklog_codex.get("skills") == "./skills/",
            "worklog Codex manifest must expose the shared ./skills/ tree", errors)
    require(worklog_claude.get("version") == "0.2.2",
            "worklog plugin version must be 0.2.2", errors)
    require(worklog_claude.get("hooks") == "./hooks/claude-codex-hooks.json",
            "worklog Claude manifest must expose the mechanical hook", errors)
    require(worklog_codex.get("hooks") == "./hooks/claude-codex-hooks.json",
            "worklog Codex manifest must expose the mechanical hook", errors)

    catalog_check = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/tests/check-component-catalog.py"),
            "--root",
            str(ROOT),
        ],
        capture_output=True,
        text=True,
    )
    require(catalog_check.returncode == 0, catalog_check.stderr.strip() or "component catalog validation failed", errors)

    components = {component["name"]: component for component in catalog.get("components", [])}
    expected_codex = {
        name for name, component in components.items()
        if component.get("kind") == "plugin"
        and component.get("lifecycle") == "supported"
        and "codex" in component.get("hosts", {})
    }
    entries = marketplace.get("plugins", [])
    exposed_codex = {entry.get("name") for entry in entries}
    require(exposed_codex == expected_codex, "Codex marketplace entries differ from component catalog", errors)
    for entry in entries:
        name = entry.get("name")
        source = entry.get("source", {})
        require(source.get("source") == "local", "Codex marketplace source must be local", errors)
        source_path = source.get("path")
        expected_path = f"./marketplace/{name}"
        require(source_path == expected_path, f"Codex marketplace path does not target {name}", errors)
        if isinstance(source_path, str):
            require((ROOT / source_path).resolve() == (ROOT / "marketplace" / str(name)).resolve(),
                    f"Codex marketplace path does not resolve to {name}", errors)

    frontmatter = re.match(r"^---\n(.*?)\n---", skill, re.DOTALL)
    require(frontmatter is not None, "report-planner skill has no frontmatter", errors)
    if frontmatter:
        header = frontmatter.group(1)
        require(re.search(r"^name:\s*hukuhaka-report-planner\s*$", header, re.MULTILINE) is not None,
                "report-planner skill name is not portable", errors)
        claude_only_keys = ("allowed-tools:", "disable-model-invocation:", "argument-hint:")
        for key in claude_only_keys:
            require(key not in header, f"report-planner frontmatter contains Claude-only key: {key[:-1]}", errors)

    require("${CLAUDE_PLUGIN_ROOT}" not in skill, "report-planner skill contains a Claude-only plugin-root variable", errors)
    require("!`" not in skill, "report-planner skill contains Claude-only shell interpolation", errors)
    require(".hukuhaka/reports/<short-name>/" in skill, "host-neutral report output path contract is missing", errors)
    require(".claude/reports/<short-name>/spec.md" in skill, "legacy report read fallback is missing", errors)
    require("Legacy paths are read-only" in skill, "legacy report path is not explicitly read-only", errors)
    require("Never dual-write" in skill, "dual-write prohibition is missing", errors)
    require("artifact-designer" in skill, "report-planner does not route build-preflight to artifact-designer", errors)
    require("name: artifact-designer" in designer_skill, "portable artifact-designer skill is malformed", errors)
    require("Do not edit `spec.md`" in designer_skill, "designer can rewrite the finalized spec", errors)
    require("skills:\n  - artifact-designer" in designer_agent,
            "Claude designer agent does not preload the portable skill", errors)
    require("Claude Code" in build_handoff and "Codex" in build_handoff,
            "build handoff does not define both host adapters", errors)
    require("write-capable worker" in build_handoff,
            "Codex build handoff does not define its worker adapter", errors)
    require("do not build in the parent" in build_handoff.lower(),
            "build handoff permits same-context construction", errors)

    worklog_frontmatter = re.match(r"^---\n(.*?)\n---", worklog_skill, re.DOTALL)
    require(worklog_frontmatter is not None, "worklog skill has no frontmatter", errors)
    worklog_skill_name = None
    if worklog_frontmatter:
        header = worklog_frontmatter.group(1)
        name_match = re.search(r"^name:\s*([a-z0-9-]+)\s*$", header, re.MULTILINE)
        require(name_match is not None, "worklog skill name is not portable", errors)
        worklog_skill_name = name_match.group(1) if name_match else None
        require(worklog_skill_name == "worklog",
                "worklog skill name is not portable", errors)
        for key in ("allowed-tools:", "disable-model-invocation:", "argument-hint:"):
            require(key not in header,
                    f"worklog frontmatter contains Claude-only key: {key[:-1]}", errors)
    require("${CLAUDE_PLUGIN_ROOT}" not in worklog_skill,
            "worklog skill contains a Claude-only plugin-root variable", errors)
    require("!`" not in worklog_skill,
            "worklog skill contains Claude-only shell interpolation", errors)
    require("references/writing-guide.md" not in worklog_skill,
            "worklog skill still depends on the removed writing guide", errors)
    require("Do not use for mechanical setup, status, or archive commands" in worklog_skill,
            "worklog lifecycle trigger still claims mechanical commands", errors)
    require(".hukuhaka/work.md" in worklog_skill,
            "worklog host-neutral current-work path is missing", errors)
    require(".hukuhaka/changelog.md" in worklog_skill,
            "worklog host-neutral history path is missing", errors)
    require("Never read, migrate, or write a legacy `backlog.md`" in worklog_skill,
            "worklog legacy backlog exclusion is missing", errors)
    require("write the changelog first" in worklog_skill,
            "worklog completion ordering is missing", errors)
    worklog_plugin_name = worklog_codex.get("name")
    if isinstance(worklog_plugin_name, str) and worklog_skill_name:
        canonical = f"${worklog_plugin_name}:{worklog_skill_name}"
        require(f'PLUGIN_NAME = "{worklog_plugin_name}"' in worklog_script,
                "worklog runtime plugin identity differs from its manifest", errors)
        require(f'SKILL_NAME = "{worklog_skill_name}"' in worklog_script,
                "worklog runtime Skill identity differs from its frontmatter", errors)
        require(canonical in worklog_openai,
                "worklog OpenAI metadata does not use the canonical identity", errors)
        require(canonical in str(worklog_codex.get("interface", {}).get("defaultPrompt", "")),
                "worklog Codex manifest does not use the canonical identity", errors)
        if host_support:
            require(canonical in host_support,
                    "host-support docs do not use the canonical worklog identity", errors)
    for contract in (
        '"CLAUDE.md" if host == "claude" else "AGENTS.md"',
        "hukuhaka-worklog:begin",
        "Archive destinations are written first",
        "def run_hook(",
        '"PLUGIN_DATA" in environment',
        '"decision": "block"',
    ):
        require(contract in worklog_script,
                f"worklog mechanical contract is missing: {contract}", errors)
    hook_groups = worklog_hooks.get("hooks", {})
    require(set(hook_groups) == {"UserPromptSubmit"},
            "worklog must register only a UserPromptSubmit hook", errors)
    hook_entries = hook_groups.get("UserPromptSubmit", [])
    require(len(hook_entries) == 1,
            "worklog must register exactly one UserPromptSubmit group", errors)
    if len(hook_entries) == 1:
        handlers = hook_entries[0].get("hooks", [])
        require(len(handlers) == 1,
                "worklog must register exactly one command handler", errors)
        if len(handlers) == 1:
            require(
                handlers[0].get("command")
                == 'python3 "${CLAUDE_PLUGIN_ROOT}/skills/worklog/scripts/worklog.py" hook',
                "worklog hook must invoke the bundled mechanical adapter directly",
                errors,
            )

    template_rules = (
        "For plans spanning multiple components or changing a contract",
        "The user’s latest explicit request defines the active scope",
        "After compaction or handoff, reconcile it with the user’s latest request",
        "Preserve pre-existing and unrelated user work",
        "Stage files or hunks explicitly",
    )
    for name, template in (("CLAUDE.md", claude_template), ("AGENTS.md", agents_template)):
        for rule in template_rules:
            require(rule in template, f"{name} template lacks required guidance: {rule}", errors)
        require("engineering-plan" not in template, f"{name} template names the optional Skill", errors)

    attribution_rule = "No Co-authored-by or co-worker attributions in commit messages."
    require("Do not change `spec.md` contracts without explicit sign-off." in claude_template,
            "CLAUDE.md template lacks the spec contract boundary", errors)
    require(attribution_rule in claude_template,
            "CLAUDE.md template lacks the attribution rule", errors)
    require(attribution_rule not in agents_template,
            "AGENTS.md template contains the Claude-only attribution rule", errors)

    require(not (ROOT / "skills" / "hukuhaka-team" / "SKILL.md").exists(), "removed hukuhaka-team skill still exists", errors)
    team_refs = list((ROOT / "eval").rglob("TEAM-*.json"))
    require(not team_refs, "removed TEAM eval scenarios still exist", errors)

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    if isinstance(worklog_codex.get("name"), str) and worklog_skill_name:
        canonical = f"${worklog_codex['name']}:{worklog_skill_name}"
        require(canonical in readme,
                "README does not use the canonical worklog identity", errors)
        require("Compatibility alias: `$worklog" in readme,
                "README does not document the worklog compatibility alias", errors)
    for removed_name in ("hukuhaka-project-mapper", "hukuhaka-ltm"):
        require(removed_name not in components,
                f"removed component remains in catalog: {removed_name}", errors)
        require(not (ROOT / "marketplace" / removed_name).exists(),
                f"removed component tree remains: marketplace/{removed_name}", errors)
        require(not readme_row(readme, removed_name),
                f"README still exposes removed component: {removed_name}", errors)
    require("| Supported | Claude Code only |" in readme_row(readme, "hukuhaka-codex"),
            "README does not mark hukuhaka-codex Claude-only", errors)
    require("| Supported | Claude Code, Codex |" in readme_row(readme, "hukuhaka-worklog"),
            "README does not mark hukuhaka-worklog dual-host", errors)

    if errors:
        return report(errors)
    print("host-support: dual-host plugin contracts and component lifecycle are consistent")
    return 0


def report(errors: list[str]) -> int:
    for error in errors:
        print(f"host-support: {error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
