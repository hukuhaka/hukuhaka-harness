"""Host-aware hukuhaka-harness install CLI."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from .claude import ClaudeDeployment
from .codex import (
    CodexDeployment,
    CodexGuidanceDeployment,
    resolve_codex_home,
    run_json as run_codex_json,
)
from .common import InstallerError, Manifest, StateError, load_json
from .terminal import (
    HostInstallPlan,
    choose_components,
    csv_value,
    prompt_install_plan,
)


HOSTS = ("claude", "codex", "both")


class Installer:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.repo_root = args.repo_root.resolve()
        self.catalog = load_json(self.repo_root / "components.json", {})
        if not isinstance(self.catalog, dict) or not isinstance(self.catalog.get("components"), list):
            raise StateError(
                "component catalog must contain a components array",
                operation="read-catalog",
                path=str(self.repo_root / "components.json"),
            )
        self.component_map = {
            str(component["name"]): component for component in self.catalog["components"]
        }
        self.version = args.resolved_version or self._source_version()
        args.selector_used = bool(args.selector_used and self._tty_available())
        self.host = args.host or ("both" if args.selector_used else "claude")
        if self.host not in HOSTS:
            raise InstallerError("--host must be claude, codex, or both", stage="arguments")
        self.aliases = self._component_aliases()

    def _source_version(self) -> str:
        path = self.repo_root / "VERSION"
        try:
            value = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise StateError("cannot read source VERSION: {}".format(exc), path=str(path)) from exc
        if not value:
            raise StateError("source VERSION is empty", path=str(path))
        return value

    def _tty_available(self) -> bool:
        return bool(sys.stdin.isatty() and sys.stdout.isatty())

    def _component_aliases(self) -> Dict[str, str]:
        aliases = {}
        for component in self.catalog["components"]:
            canonical = str(component["name"])
            for alias in component.get("aliases", []):
                aliases[str(alias)] = canonical
        return aliases

    def _canonical(self, name: str) -> str:
        return self.aliases.get(name, name)

    def _host_version(self, host: str) -> str:
        command = shutil.which(host)
        if not command:
            return ""
        result = subprocess.run(
            (command, "--version"),
            text=True,
            capture_output=True,
            check=False,
        )
        return (result.stdout or result.stderr).strip().splitlines()[0][:80]

    def _selected_hosts(self) -> Tuple[str, ...]:
        return ("claude", "codex") if self.host == "both" else (self.host,)

    def _supports(self, component: Dict[str, Any], host: Optional[str] = None) -> bool:
        selected = (host,) if host else self._selected_hosts()
        return any(name in component.get("hosts", {}) for name in selected)

    def available_components(self) -> List[Dict[str, Any]]:
        return [component for component in self.catalog["components"] if self._supports(component)]

    def _current_claude_components(self) -> Tuple[bool, Set[str]]:
        manifest_path = Path.home() / ".claude" / ".hukuhaka-manifest.json"
        if not manifest_path.exists():
            return False, set()
        manifest = Manifest.load(manifest_path)
        if manifest.components:
            return True, {self._canonical(name) for name in manifest.components}
        return True, {
            name
            for name, component in self.component_map.items()
            if "claude" in component.get("hosts", {})
        }

    def _current_codex_components(self) -> Tuple[bool, Set[str]]:
        names = set()  # type: Set[str]
        codex_home = resolve_codex_home()
        if (codex_home / ".hukuhaka-guidance-manifest.json").is_file():
            names.add("agents-md")
        if shutil.which("codex") is not None:
            data = run_codex_json(
                ("codex", "plugin", "list", "--json"),
                stage="read-codex-state",
            )
            names.update(
                self._canonical(str(plugin["name"]))
                for plugin in data.get("installed", [])
                if isinstance(plugin, dict)
                and plugin.get("marketplaceName") == self.catalog.get("marketplaces", {}).get("codex")
                and plugin.get("name")
            )
        return bool(names), names

    def current_components(self) -> Set[str]:
        found = False
        current = set()  # type: Set[str]
        if "claude" in self._selected_hosts():
            has_state, names = self._current_claude_components()
            found = found or has_state
            current.update(names)
        if "codex" in self._selected_hosts():
            has_state, names = self._current_codex_components()
            found = found or has_state
            current.update(names)
        if not found:
            current = {
                str(component["name"])
                for component in self.available_components()
                if component.get("default") is True and component.get("lifecycle") == "supported"
            }
        return current

    def _validate_component_names(self, names: Iterable[str]) -> List[str]:
        available = {str(component["name"]) for component in self.available_components()}
        ordered = list(dict.fromkeys(self._canonical(name) for name in names))
        unknown = [name for name in ordered if name not in available]
        if unknown:
            raise InstallerError(
                "unknown component '{}'. Available: {}".format(
                    unknown[0], " ".join(sorted(available))
                ),
                stage="component-selection",
                operation="validate-components",
            )
        return ordered

    def _host_components(self, host: str) -> List[Dict[str, Any]]:
        return [
            component
            for component in self.catalog["components"]
            if host in component.get("hosts", {})
        ]

    def _host_current(self, host: str) -> Set[str]:
        found, current = (
            self._current_claude_components()
            if host == "claude"
            else self._current_codex_components()
        )
        if found:
            return current
        return {
            str(component["name"])
            for component in self._host_components(host)
            if component.get("default") is True
            and component.get("lifecycle") == "supported"
        }

    def _interactive_plans(self) -> List[HostInstallPlan]:
        if not self._tty_available():
            return []
        sections = []
        for host, label in (("claude", "Claude Code"), ("codex", "Codex")):
            if host not in self._selected_hosts():
                continue
            sections.append(
                {
                    "host": host,
                    "label": label,
                    "available": shutil.which(host) is not None,
                    "version": self._host_version(host),
                    "components": self._host_components(host),
                    "selected": self._host_current(host),
                }
            )
        return prompt_install_plan(sys.stdin, sys.stdout, sections=sections)

    def choose_components(self) -> List[str]:
        needs_current = not (self.args.all or self.args.components is not None)
        return choose_components(
            args=self.args,
            available=self.available_components(),
            current=self.current_components() if needs_current else set(),
            validate_names=self._validate_component_names,
            component_map=self.component_map,
        )

    def filter_host(self, components: Sequence[str], host: str) -> List[str]:
        return [name for name in components if host in self.component_map[name].get("hosts", {})]

    def _print_plan(self, components: Sequence[str]) -> Tuple[List[str], List[str]]:
        claude = self.filter_host(components, "claude")
        codex = self.filter_host(components, "codex")
        print("")
        print("Components: {}".format(csv_value(components)))
        print("Installation plan:")
        if "claude" in self._selected_hosts():
            print("  Claude Code: {}".format(csv_value(claude) or "none"))
        if "codex" in self._selected_hosts():
            print("  Codex:       {}".format(csv_value(codex) or "none"))
        print("")
        return claude, codex

    def _deploy_claude(self, components: Sequence[str]) -> bool:
        try:
            deployment = ClaudeDeployment(
                self.repo_root,
                Path.home(),
                components,
                dry_run=self.args.dry_run,
                force=self.args.force,
            )
            deployment.deploy()
            return True
        except InstallerError as exc:
            print(exc.render(), file=sys.stderr)
            return False

    def _deploy_codex(self, components: Sequence[str]) -> bool:
        try:
            plugin_components = [
                name for name in components if self.component_map[name].get("kind") == "plugin"
            ]
            if plugin_components:
                self._migrate_codex_aliases(plugin_components)
                source = (
                    str(self.repo_root)
                    if self.args.local_source
                    else "hukuhaka/hukuhaka-harness"
                )
                CodexDeployment(
                    plugin_components,
                    source,
                    str(self.catalog.get("marketplaces", {}).get("codex", "hukuhaka-harness")),
                    self.version,
                    version_explicit=self.args.version_explicit,
                    local_source=self.args.local_source,
                    dry_run=self.args.dry_run,
                ).deploy()
            CodexGuidanceDeployment(
                self.repo_root / "templates" / "AGENTS.md",
                resolve_codex_home(),
                self.version,
                enabled="agents-md" in components,
                dry_run=self.args.dry_run,
                force=self.args.force,
            ).deploy()
            return True
        except InstallerError as exc:
            print(exc.render(), file=sys.stderr)
            return False

    def _migrate_codex_aliases(self, components: Sequence[str]) -> None:
        if self.args.dry_run or not self.aliases:
            return
        data = run_codex_json(
            ("codex", "plugin", "list", "--json"),
            stage="codex-migrate",
        )
        marketplace = self.catalog.get("marketplaces", {}).get("codex")
        for plugin in data.get("installed", []):
            if (
                isinstance(plugin, dict)
                and plugin.get("marketplaceName") == marketplace
                and self.aliases.get(str(plugin.get("name", ""))) in components
                and plugin.get("pluginId")
            ):
                plugin_id = str(plugin["pluginId"])
                subprocess.run(
                    ("codex", "plugin", "remove", plugin_id, "--json"),
                    check=True,
                    stdout=subprocess.DEVNULL,
                )
                print(
                    "  [migrate] {} -> {}".format(
                        plugin.get("name"), self.aliases[str(plugin["name"])]
                    )
                )

    def _uninstall_codex(self) -> bool:
        success = True
        if shutil.which("codex") is None:
            print(
                "Warning: codex CLI not found; plugin removal was skipped.",
                file=sys.stderr,
            )
        else:
            data = run_codex_json(
                ("codex", "plugin", "list", "--json"),
                stage="codex-uninstall",
            )
            marketplace = self.catalog.get("marketplaces", {}).get("codex")
            ids = [
                str(plugin["pluginId"])
                for plugin in data.get("installed", [])
                if isinstance(plugin, dict)
                and plugin.get("marketplaceName") == marketplace
                and plugin.get("pluginId")
            ]
            for plugin_id in ids:
                command = ["codex", "plugin", "remove", plugin_id, "--json"]
                if not self.args.dry_run:
                    subprocess.run(command, check=True, stdout=subprocess.DEVNULL)
                print("  [ok] removed {}".format(plugin_id))
            if ids:
                print(
                    "Codex: removed {} plugin(s); marketplace registration preserved.".format(
                        len(ids)
                    )
                )
            else:
                print("Codex: no installed hukuhaka-harness plugins.")
        try:
            CodexGuidanceDeployment(
                self.repo_root / "templates" / "AGENTS.md",
                resolve_codex_home(),
                self.version,
                enabled=False,
                dry_run=self.args.dry_run,
                force=self.args.force,
            ).uninstall()
        except InstallerError as exc:
            print(exc.render(), file=sys.stderr)
            success = False
        return success

    def _reset_before_install(self, host: str, *, reset_templates: bool) -> bool:
        try:
            if host == "claude":
                ClaudeDeployment(
                    self.repo_root,
                    Path.home(),
                    [],
                    dry_run=self.args.dry_run,
                    force=self.args.force,
                ).reset_for_install(reset_template=reset_templates)
                return True

            if self.args.dry_run:
                print("Resetting Codex:")
                print("  [dry-run] remove hukuhaka-harness plugins and marketplace")
            else:
                data = run_codex_json(
                    ("codex", "plugin", "list", "--json"),
                    stage="codex-reset",
                )
                marketplace = self.catalog.get("marketplaces", {}).get("codex")
                for plugin in data.get("installed", []):
                    if (
                        isinstance(plugin, dict)
                        and plugin.get("marketplaceName") == marketplace
                        and plugin.get("pluginId")
                    ):
                        subprocess.run(
                            (
                                "codex",
                                "plugin",
                                "remove",
                                str(plugin["pluginId"]),
                                "--json",
                            ),
                            check=True,
                            stdout=subprocess.DEVNULL,
                        )
                marketplaces = run_codex_json(
                    ("codex", "plugin", "marketplace", "list", "--json"),
                    stage="codex-reset",
                )
                if any(
                    isinstance(item, dict) and item.get("name") == marketplace
                    for item in marketplaces.get("marketplaces", [])
                ):
                    subprocess.run(
                        (
                            "codex",
                            "plugin",
                            "marketplace",
                            "remove",
                            str(marketplace),
                            "--json",
                        ),
                        check=True,
                        stdout=subprocess.DEVNULL,
                    )
                print("  [ok] managed plugins and marketplace reset")
            if reset_templates:
                CodexGuidanceDeployment(
                    self.repo_root / "templates" / "AGENTS.md",
                    resolve_codex_home(),
                    self.version,
                    enabled=False,
                    dry_run=self.args.dry_run,
                    force=self.args.force,
                ).uninstall()
            return True
        except (InstallerError, subprocess.CalledProcessError) as exc:
            print(
                "installer [host={} stage=reset]: {}".format(host, exc),
                file=sys.stderr,
            )
            return False

    def uninstall(self) -> int:
        results = []
        if "claude" in self._selected_hosts():
            try:
                deployment = ClaudeDeployment(
                    self.repo_root,
                    Path.home(),
                    None,
                    dry_run=self.args.dry_run,
                    force=self.args.force,
                )
                deployment.uninstall(confirm=False)
                results.append(True)
            except InstallerError as exc:
                print(exc.render(), file=sys.stderr)
                results.append(False)
        if "codex" in self._selected_hosts():
            try:
                results.append(self._uninstall_codex())
            except (InstallerError, subprocess.CalledProcessError) as exc:
                print("installer [host=codex stage=uninstall]: {}".format(exc), file=sys.stderr)
                results.append(False)
        return 0 if all(results) else 1

    def run(self) -> int:
        if self.args.uninstall:
            return self.uninstall()
        if self.args.selector_used:
            plans = self._interactive_plans()
            if not plans:
                print("Exit. No changes were made.")
                return 0
        else:
            components = self.choose_components()
            claude_components, codex_components = self._print_plan(components)
            by_host = {
                "claude": claude_components,
                "codex": codex_components,
            }
            plans = [
                HostInstallPlan(
                    host=host,
                    components=by_host[host],
                    reset_before_install=self.args.reset_before_install,
                    reset_templates=self.args.reset_templates,
                )
                for host in self._selected_hosts()
                if by_host[host]
            ]

        for plan in plans:
            if shutil.which(plan.host) is None and not self.args.dry_run:
                raise InstallerError(
                    "{} CLI is required for this host".format(plan.host),
                    host=plan.host,
                    stage="preflight",
                )

        results = {}  # type: Dict[str, bool]
        for plan in plans:
            if plan.reset_before_install and not self._reset_before_install(
                plan.host,
                reset_templates=plan.reset_templates,
            ):
                results[plan.host] = False
                continue
            if plan.host == "claude":
                results[plan.host] = self._deploy_claude(plan.components)
            else:
                results[plan.host] = self._deploy_codex(plan.components)

        print("\nHost results:")
        for plan in plans:
            prefix = "  Claude Code: " if plan.host == "claude" else "  Codex:       "
            print(prefix + ("complete" if results[plan.host] else "failed"))
        if not all(results.values()):
            print("Installation incomplete: one or more host deployments failed.", file=sys.stderr)
            return 1
        print("")
        if self.args.dry_run:
            print("Dry run complete. No files were modified.")
        elif set(results) == {"claude"}:
            print("Done! Restart Claude Code to load the plugins.")
        elif set(results) == {"codex"}:
            print("Done! Start a new Codex task to load the plugins.")
        else:
            print("Done! Restart Claude Code and start a new Codex task to load the plugins.")
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Install hukuhaka-harness")
    parser.add_argument("--repo-root", type=Path, required=True, help=argparse.SUPPRESS)
    parser.add_argument("--resolved-version", help=argparse.SUPPRESS)
    parser.add_argument("--version-explicit", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--local-source", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--host", choices=HOSTS)
    parser.add_argument("--version")
    parser.add_argument("--source-dir", help=argparse.SUPPRESS)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--components")
    parser.add_argument("--add", default="")
    parser.add_argument("--remove", default="")
    parser.add_argument("--uninstall", action="store_true")
    parser.add_argument(
        "--reset-before-install",
        action="store_true",
        help="remove managed plugins/skills and marketplace state before installing",
    )
    parser.add_argument(
        "--reset-templates",
        action="store_true",
        help="also reset the managed CLAUDE.md or AGENTS.md template",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.reset_templates and not args.reset_before_install:
        print(
            "installer [stage=arguments]: --reset-templates requires --reset-before-install",
            file=sys.stderr,
        )
        return 2
    args.version_explicit = bool(args.version_explicit or args.version)
    args.selector_used = not any(
        (
            args.all,
            args.components is not None,
            args.add,
            args.remove,
            args.uninstall,
            args.reset_before_install,
        )
    )
    try:
        return Installer(args).run()
    except InstallerError as exc:
        print(exc.render(), file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        detail = ""
        if getattr(exc, "stderr", None):
            detail = ": {}".format(str(exc.stderr).strip())
        print(
            "installer [stage=external-command operation={}]: command failed with status {}{}".format(
                exc.cmd[0] if isinstance(exc.cmd, (list, tuple)) else exc.cmd,
                exc.returncode,
                detail,
            ),
            file=sys.stderr,
        )
        return 1
    except Exception as exc:
        print(
            "installer [stage=unexpected operation={}]: {}".format(type(exc).__name__, exc),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
