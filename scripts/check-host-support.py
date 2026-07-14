#!/usr/bin/env python3
"""Validate the declared Claude Code/Codex component boundaries."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLANNER = ROOT / "marketplace" / "hukuhaka-report-planner"
CATALOG = ROOT / "components.json"
CLAUDE_MANIFEST = PLANNER / ".claude-plugin" / "plugin.json"
CODEX_MANIFEST = PLANNER / ".codex-plugin" / "plugin.json"
MARKETPLACE = ROOT / ".agents" / "plugins" / "marketplace.json"
SKILL = PLANNER / "skills" / "hukuhaka-report-planner" / "SKILL.md"


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

    for path in (CATALOG, CLAUDE_MANIFEST, CODEX_MANIFEST, MARKETPLACE, SKILL):
        require(path.is_file(), f"missing required dual-host file: {path.relative_to(ROOT)}", errors)
    if errors:
        return report(errors)

    claude = load_json(CLAUDE_MANIFEST)
    codex = load_json(CODEX_MANIFEST)
    catalog = load_json(CATALOG)
    marketplace = load_json(MARKETPLACE)
    skill = SKILL.read_text(encoding="utf-8")

    require(claude.get("name") == codex.get("name"), "Claude and Codex manifest names differ", errors)
    require(claude.get("version") == codex.get("version"), "Claude and Codex manifest versions differ", errors)
    require(codex.get("skills") == "./skills/", "Codex manifest must expose the shared ./skills/ tree", errors)

    catalog_check = subprocess.run(
        [sys.executable, str(ROOT / "scripts/component_catalog.py"), "--root", str(ROOT), "validate"],
        capture_output=True,
        text=True,
    )
    require(catalog_check.returncode == 0, catalog_check.stderr.strip() or "component catalog validation failed", errors)

    components = {component["name"]: component for component in catalog.get("components", [])}
    expected_codex = {
        name for name, component in components.items()
        if component.get("lifecycle") == "supported" and "codex" in component.get("hosts", {})
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

    require(not (ROOT / "skills" / "hukuhaka-team" / "SKILL.md").exists(), "removed hukuhaka-team skill still exists", errors)
    team_refs = list((ROOT / "eval").rglob("TEAM-*.json"))
    require(not team_refs, "removed TEAM eval scenarios still exist", errors)

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    require("| Deprecated | Claude Code only |" in readme_row(readme, "hukuhaka-project-mapper"),
            "README does not mark hukuhaka-project-mapper deprecated", errors)
    require("| Deprecated | Claude Code only |" in readme_row(readme, "hukuhaka-ltm"),
            "README does not mark hukuhaka-ltm deprecated", errors)
    require("| Supported | Claude Code only |" in readme_row(readme, "hukuhaka-codex"),
            "README does not mark hukuhaka-codex Claude-only", errors)

    if errors:
        return report(errors)
    print("host-support: report-planner dual-host contract and component lifecycle are consistent")
    return 0


def report(errors: list[str]) -> int:
    for error in errors:
        print(f"host-support: {error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
