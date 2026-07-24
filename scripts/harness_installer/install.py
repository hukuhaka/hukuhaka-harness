"""Host-aware hukuhaka-harness installer CLI."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from .claude import ClaudeDeployment
from .codex import CodexDeployment
from .codex_config import CodexConfigWizard
from .codex_guidance import CodexGuidanceDeployment
from .codex_paths import resolve_codex_home
from .errors import InstallerError, StateError
from .filesystem import load_json
from .state import Manifest


HOSTS = ("claude", "codex", "both")


def csv_items(value: str) -> List[str]:
    return list(dict.fromkeys(item for item in value.split(",") if item))


def csv_value(items: Iterable[str]) -> str:
    return ",".join(items)


class Installer:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.repo_root = args.repo_root.resolve()
        self.script_dir = self.repo_root / "scripts"
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
        self.host = args.host or self._choose_host()
        if self.host not in HOSTS:
            raise InstallerError("--host must be claude, codex, or both", stage="arguments")

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
        try:
            with open("/dev/tty", "r+"):
                return True
        except OSError:
            return False

    def _choose_host(self) -> str:
        if not self._interactive_component_request() or not self._tty_available():
            return "claude"
        with open("/dev/tty", "r+") as tty:
            while True:
                tty.write("\nInstall for:\n  1) Claude Code\n  2) Codex\n  3) Both\nSelect [1]: ")
                tty.flush()
                choice = tty.readline().strip()
                if choice in ("", "1"):
                    return "claude"
                if choice == "2":
                    return "codex"
                if choice == "3":
                    return "both"
                if choice.lower() == "q":
                    raise InstallerError("cancelled", stage="host-selection")
                tty.write("Enter 1, 2, or 3 (q to cancel).\n")

    def _interactive_component_request(self) -> bool:
        return not any(
            (
                self.args.all,
                self.args.components is not None,
                self.args.add,
                self.args.remove,
                self.args.uninstall,
                self.args.print_deps,
            )
        )

    def _selected_hosts(self) -> Tuple[str, ...]:
        return ("claude", "codex") if self.host == "both" else (self.host,)

    def _supports(self, component: Dict[str, Any], host: Optional[str] = None) -> bool:
        selected = (host,) if host else self._selected_hosts()
        return any(name in component.get("hosts", {}) for name in selected)

    def available_components(self) -> List[Dict[str, Any]]:
        return [component for component in self.catalog["components"] if self._supports(component)]

    def _description(self, component: Dict[str, Any]) -> str:
        if component.get("description"):
            return str(component["description"])
        for host in self._selected_hosts():
            manifest = component.get("hosts", {}).get(host, {}).get("manifest")
            if not manifest:
                continue
            data = load_json(self.repo_root / manifest, {})
            return str(data.get("description", ""))
        return ""

    def _current_claude_components(self) -> Tuple[bool, Set[str]]:
        manifest_path = Path.home() / ".claude" / ".hukuhaka-manifest.json"
        if not manifest_path.exists():
            return False, set()
        manifest = Manifest.load(manifest_path)
        if manifest.components:
            return True, set(manifest.components)
        return True, {
            name
            for name, component in self.component_map.items()
            if "claude" in component.get("hosts", {})
        }

    def _run_json(self, command: Sequence[str], *, stage: str) -> Dict[str, Any]:
        try:
            result = subprocess.run(command, check=True, text=True, capture_output=True)
        except FileNotFoundError as exc:
            raise InstallerError(
                "command not found: {}".format(command[0]),
                stage=stage,
                operation="run-command",
            ) from exc
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or "").strip()
            raise InstallerError(
                "command failed ({}): {}".format(exc.returncode, detail or "no output"),
                stage=stage,
                operation="run-command",
            ) from exc
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise InstallerError(
                "command returned invalid JSON: {}".format(exc),
                stage=stage,
                operation="parse-command-output",
            ) from exc
        if not isinstance(data, dict):
            raise InstallerError("command JSON root must be an object", stage=stage)
        return data

    def _current_codex_components(self) -> Tuple[bool, Set[str]]:
        names = set()  # type: Set[str]
        codex_home = resolve_codex_home()
        if (codex_home / ".hukuhaka-guidance-manifest.json").is_file():
            names.add("agents-md")
        if shutil.which("codex") is not None:
            data = self._run_json(("codex", "plugin", "list", "--json"), stage="read-codex-state")
            names.update(
                str(plugin["name"])
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
        ordered = list(dict.fromkeys(names))
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

    def _preflight(self, components: Sequence[str]) -> Tuple[int, Dict[str, Any], str]:
        command = [
            "bash",
            str(self.script_dir / "preflight.sh"),
            "--host",
            self.host,
            "--components",
            csv_value(components),
            "--src-dir",
            str(self.repo_root),
        ]
        result = subprocess.run(command, text=True, capture_output=True)
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise InstallerError(
                "preflight returned invalid JSON: {}. stderr: {}".format(
                    exc, result.stderr.strip() or "none"
                ),
                stage="preflight",
                operation="parse-preflight",
            ) from exc
        if not isinstance(data, dict):
            raise InstallerError("preflight JSON root must be an object", stage="preflight")
        return result.returncode, data, result.stderr

    def _interactive_select(
        self,
        current: Set[str],
        preflight_data: Optional[Dict[str, Any]],
    ) -> List[str]:
        if not self._tty_available():
            raise InstallerError(
                "interactive selection requires a TTY; use --components <list>",
                stage="component-selection",
            )
        with tempfile.TemporaryDirectory(prefix="hukuhaka-selector-") as temp_name:
            temp = Path(temp_name)
            discovery = temp / "components.tsv"
            preflight = temp / "preflight.json"
            lines = []
            for component in self.available_components():
                description = self._description(component).replace("\t", " ").replace("\n", " ")
                if component.get("lifecycle") == "deprecated":
                    description = "[deprecated] " + description
                default_on = component.get("default") is True and component.get("lifecycle") == "supported"
                lines.append(
                    "\t".join(
                        (
                            str(component["name"]),
                            str(component["kind"]),
                            description,
                            "true" if default_on else "false",
                        )
                    )
                )
            discovery.write_text("\n".join(lines) + "\n", encoding="utf-8")
            preflight_arg = ""
            if preflight_data is not None:
                preflight.write_text(json.dumps(preflight_data), encoding="utf-8")
                preflight_arg = str(preflight)
            command = [
                sys.executable,
                str(self.script_dir / "select_components.py"),
                str(discovery),
                csv_value(sorted(current)),
                preflight_arg,
                self.host,
            ]
            result = subprocess.run(command, text=True, capture_output=True)
            if result.returncode != 0:
                raise InstallerError(
                    result.stderr.strip() or "cancelled",
                    stage="component-selection",
                    operation="selector",
                )
            return [line for line in result.stdout.splitlines() if line]

    def choose_components(self) -> List[str]:
        current = self.current_components()
        available = self.available_components()
        preflight_data = None  # type: Optional[Dict[str, Any]]
        if not self.args.skip_preflight:
            _, preflight_data, _ = self._preflight([str(item["name"]) for item in available])
        if self.args.all or self.args.print_deps:
            selected = [
                str(component["name"])
                for component in available
                if component.get("default") is True and component.get("lifecycle") == "supported"
            ]
        elif self.args.components is not None:
            selected = self._validate_component_names(csv_items(self.args.components))
        elif self.args.add or self.args.remove:
            add = self._validate_component_names(csv_items(self.args.add)) if self.args.add else []
            remove = self._validate_component_names(csv_items(self.args.remove)) if self.args.remove else []
            selected_set = (current | set(add)) - set(remove)
            order = [str(component["name"]) for component in available]
            selected = [name for name in order if name in selected_set]
        elif not self._tty_available():
            defaults = {
                str(component["name"])
                for component in available
                if component.get("default") is True
                and component.get("lifecycle") == "supported"
            }
            selected_set = current | defaults
            order = [str(component["name"]) for component in available]
            selected = [name for name in order if name in selected_set]
            self.args.selector_used = False
            print(
                "No TTY detected; preserving current components and adding supported defaults.",
                file=sys.stderr,
            )
        else:
            selected = self._interactive_select(current, preflight_data)
        selected = self._validate_component_names(selected)
        if not selected:
            raise InstallerError(
                "empty selection rejected; use --uninstall to remove everything",
                stage="component-selection",
            )
        deprecated = [
            name
            for name in selected
            if self.component_map[name].get("lifecycle") == "deprecated"
        ]
        if deprecated:
            print(
                "Warning: deprecated component(s) selected: {}".format(csv_value(deprecated)),
                file=sys.stderr,
            )
            print(
                "         They remain installable for legacy Claude Code setups but receive critical fixes only.",
                file=sys.stderr,
            )
        return selected

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

    def _print_requirements(self, data: Dict[str, Any]) -> None:
        print("Requirements:")
        for requirement in data.get("requirements", []):
            found = bool(requirement.get("found"))
            required = bool(requirement.get("required"))
            symbol = "✓" if found else ("✗" if required else "⚠")
            if found:
                detail = str(requirement.get("path", ""))
                version = str(requirement.get("version", ""))
                if version:
                    detail += "  ({})".format(version[:60])
            elif required:
                detail = "MISSING — required"
            else:
                detail = "not found (optional — {})".format(
                    ", ".join(requirement.get("needed_by", []))
                )
            print("  {} {:<12} {}".format(symbol, requirement.get("name", "?"), detail))

    def _package_manager(self) -> Optional[str]:
        if platform.system() == "Darwin" and shutil.which("brew"):
            return "brew"
        if platform.system() == "Linux":
            for command, name in (
                ("apt-get", "apt"),
                ("dnf", "dnf"),
                ("pacman", "pacman"),
                ("zypper", "zypper"),
            ):
                if shutil.which(command):
                    return name
        return None

    def _install_command(self, manager: str, tool: str) -> List[str]:
        package = "newt" if tool == "whiptail" else ("python3" if tool == "python" else tool)
        commands = {
            "brew": ["brew", "install", package],
            "apt": ["sudo", "apt-get", "install", "-y", package],
            "dnf": ["sudo", "dnf", "install", "-y", package],
            "pacman": ["sudo", "pacman", "-S", "--noconfirm", package],
            "zypper": ["sudo", "zypper", "install", "-y", package],
        }
        return commands[manager]

    def _handle_missing_requirements(self, data: Dict[str, Any]) -> bool:
        missing = [
            item
            for item in data.get("requirements", [])
            if item.get("required") and not item.get("found")
        ]
        if not missing:
            return True
        print("\nSome required tools are missing: {}".format(" ".join(str(item["name"]) for item in missing)))
        manager = self._package_manager()
        system_tools = [item for item in missing if item.get("kind") == "system"]
        if not manager or not system_tools:
            print("Install the missing host tools manually, then re-run the installer.")
            return False
        commands = [self._install_command(manager, str(item["name"])) for item in system_tools]
        print("Detected package manager: {}\n\nInstall commands:".format(manager))
        for command in commands:
            print("  {}".format(" ".join(command)))
        if self.args.print_deps:
            return False
        if not self.args.auto_install_deps:
            print("\nRe-run with --auto-install-deps to execute these commands.")
            return False
        for command in commands:
            print("  > {}".format(" ".join(command)))
            subprocess.run(command, check=True)
        return True

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

    def _configure_codex(self) -> bool:
        if not self._tty_available():
            raise InstallerError(
                "Codex global configuration requires a TTY",
                stage="codex-config",
                operation="open-tty",
            )
        with open("/dev/tty", "r+") as tty:
            CodexConfigWizard(
                resolve_codex_home(),
                tty,
                dry_run=self.args.dry_run,
            ).run()
        return True

    def _uninstall_codex(self) -> bool:
        success = True
        if shutil.which("codex") is None:
            print(
                "Warning: codex CLI not found; plugin removal was skipped.",
                file=sys.stderr,
            )
        else:
            data = self._run_json(("codex", "plugin", "list", "--json"), stage="codex-uninstall")
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

    def uninstall(self) -> int:
        results = []
        if "claude" in self._selected_hosts():
            try:
                deployment = ClaudeDeployment(
                    self.repo_root,
                    Path.home(),
                    None,
                    dry_run=self.args.dry_run,
                    force=True,
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
        components = self.choose_components()
        claude_components, codex_components = self._print_plan(components)
        if not self.args.skip_preflight:
            code, data, _ = self._preflight(components)
            if not self.args.selector_used:
                self._print_requirements(data)
            if self.args.print_deps and code == 0:
                print("\nNo required dependencies are missing.")
                return 0
            if code != 0:
                if not self._handle_missing_requirements(data):
                    return 0 if self.args.print_deps else 1
                code, data, _ = self._preflight(components)
                if code != 0:
                    raise InstallerError("requirements still missing after install", stage="preflight")

        claude_status = None  # type: Optional[bool]
        codex_status = None  # type: Optional[bool]
        if "claude" in self._selected_hosts() and claude_components:
            claude_status = self._deploy_claude(claude_components)
        if "codex" in self._selected_hosts() and codex_components:
            codex_status = self._deploy_codex(codex_components)
            if codex_status and (self.args.configure_codex or self.args.selector_used):
                try:
                    codex_status = self._configure_codex()
                except InstallerError as exc:
                    print(exc.render(), file=sys.stderr)
                    codex_status = False

        if (
            "claude" in self._selected_hosts()
            and claude_status is True
            and not self.args.skip_extras
            and (self.script_dir / "install_helper.sh").is_file()
        ):
            command = ["bash", str(self.script_dir / "install_helper.sh")]
            if self.args.dry_run:
                command.append("--dry-run")
            if self.args.extras is not None:
                command.extend(("--components", self.args.extras))
            subprocess.run(command, check=True)

        print("\nHost results:")
        if "claude" in self._selected_hosts():
            value = "no compatible components" if claude_status is None else ("complete" if claude_status else "failed")
            print("  Claude Code: {}".format(value))
        if "codex" in self._selected_hosts():
            value = "no compatible components" if codex_status is None else ("complete" if codex_status else "failed")
            print("  Codex:       {}".format(value))
        if claude_status is False or codex_status is False:
            print("Installation incomplete: one or more host deployments failed.", file=sys.stderr)
            return 1
        print("")
        if self.args.dry_run:
            print("Dry run complete. No files were modified.")
        elif self.host == "claude":
            print("Done! Restart Claude Code to load the plugins.")
        elif self.host == "codex":
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
    parser.add_argument("--selector-used", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--host", choices=HOSTS)
    parser.add_argument("--version")
    parser.add_argument("--source-dir", help=argparse.SUPPRESS)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--components")
    parser.add_argument("--add", default="")
    parser.add_argument("--remove", default="")
    parser.add_argument("--uninstall", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-preflight", action="store_true")
    parser.add_argument("--auto-install-deps", action="store_true")
    parser.add_argument("--print-deps", action="store_true")
    parser.add_argument("--skip-extras", action="store_true")
    parser.add_argument("--extras")
    parser.add_argument(
        "--configure-codex",
        action="store_true",
        help="interactively configure recommended user-level Codex settings",
    )
    parser.add_argument("--force", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    args.version_explicit = bool(args.version_explicit or args.version)
    args.selector_used = not any(
        (args.all, args.components is not None, args.add, args.remove, args.uninstall, args.print_deps)
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
