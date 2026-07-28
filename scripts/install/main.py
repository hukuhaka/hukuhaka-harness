"""Host-aware hukuhaka-harness installer."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from .claude import ClaudeDeployment
from .codex import CodexInstaller
from .codex_config import (
    RECOMMENDED_SETTINGS,
    CodexConfigEditor,
    ConfigPlan,
    prompt_settings,
)
from .common import InstallerError, StateError, load_json
from .terminal import HostInstallPlan, csv_items, csv_value, prompt_install_plan


HOST_LABELS = {"claude": "Claude Code", "codex": "Codex"}


@dataclass(frozen=True)
class HostResult:
    host: str
    status: str
    detail: str = ""


class Installer:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.repo_root = args.repo_root.resolve()
        self.catalog = load_json(self.repo_root / "components.json", {})
        if not isinstance(self.catalog, dict) or not isinstance(
            self.catalog.get("components"), list
        ):
            raise StateError(
                "component catalog must contain a components array",
                operation="read-catalog",
                path=str(self.repo_root / "components.json"),
            )
        self.component_map = {
            str(component["name"]): component
            for component in self.catalog["components"]
        }
        self.aliases = {
            str(alias): str(component["name"])
            for component in self.catalog["components"]
            for alias in component.get("aliases", [])
        }
        self.version = args.resolved_version or self._source_version()

    def _source_version(self) -> str:
        path = self.repo_root / "VERSION"
        try:
            version = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise StateError(
                "cannot read source VERSION: {}".format(exc),
                operation="read-version",
                path=str(path),
            ) from exc
        if not version:
            raise StateError("source VERSION is empty", path=str(path))
        return version

    @staticmethod
    def _tty_available() -> bool:
        return bool(sys.stdin.isatty() and sys.stdout.isatty())

    @staticmethod
    def _host_version(host: str) -> str:
        command = shutil.which(host)
        if not command:
            return ""
        result = subprocess.run(
            (command, "--version"),
            text=True,
            capture_output=True,
            check=False,
            timeout=10,
        )
        return (result.stdout or result.stderr).strip().splitlines()[0][:80]

    def _components(self, host: str) -> List[Dict[str, Any]]:
        return [
            component
            for component in self.catalog["components"]
            if host in component.get("hosts", {})
        ]

    def _recommended(self, host: str) -> List[str]:
        return [
            str(component["name"])
            for component in self._components(host)
            if component.get("default") is True
            and component.get("lifecycle") == "supported"
        ]

    def _validate_components(self, host: str, names: Iterable[str]) -> List[str]:
        available = {
            str(component["name"]) for component in self._components(host)
        }
        ordered = list(dict.fromkeys(self.aliases.get(name, name) for name in names))
        unknown = [name for name in ordered if name not in available]
        if unknown:
            raise InstallerError(
                "unknown {} component '{}'. Available: {}".format(
                    HOST_LABELS[host], unknown[0], " ".join(sorted(available))
                ),
                host=host,
                stage="component-selection",
            )
        if not ordered:
            raise InstallerError(
                "empty component selection is not allowed; use uninstall instead",
                host=host,
                stage="component-selection",
            )
        deprecated = [
            name
            for name in ordered
            if self.component_map[name].get("lifecycle") == "deprecated"
        ]
        if deprecated:
            print(
                "Warning: deprecated component(s) selected: {}".format(
                    csv_value(deprecated)
                ),
                file=sys.stderr,
            )
        return ordered

    def _claude(self, components: Optional[Sequence[str]] = None) -> ClaudeDeployment:
        return ClaudeDeployment(
            self.repo_root,
            Path.home(),
            components,
            dry_run=bool(getattr(self.args, "dry_run", False)),
            force=bool(getattr(self.args, "force", False)),
        )

    def _codex(self) -> CodexInstaller:
        return CodexInstaller(
            self.repo_root,
            self.catalog,
            self.version,
            local_source=bool(self.args.local_source),
            dry_run=bool(getattr(self.args, "dry_run", False)),
            force=bool(getattr(self.args, "force", False)),
        )

    def _current(self, host: str) -> Set[str]:
        if host == "claude":
            return self._claude([]).current_components()
        return self._codex().current_components()

    def _print_detection(self, detected: Mapping[str, bool]) -> None:
        print("Hukuhaka Installer")
        print("")
        print("Detecting supported hosts...")
        print("")
        for host in ("claude", "codex"):
            prefix = "✓" if detected[host] else "-"
            suffix = "detected" if detected[host] else "not found"
            print("{} {} {}".format(prefix, HOST_LABELS[host], suffix))
        print("")

    def _print_plan(
        self,
        plans: Sequence[HostInstallPlan],
        current: Mapping[str, Set[str]],
        config_plan: Optional[ConfigPlan],
    ) -> None:
        print("Installation plan")
        print("")
        for plan in plans:
            desired = set(plan.components)
            before = current.get(plan.host, set())
            print(HOST_LABELS[plan.host])
            print(
                "  Install/update: {}".format(
                    csv_value(plan.components) or "none"
                )
            )
            print(
                "  Remove:         {}".format(
                    csv_value(sorted(before - desired)) or "none"
                )
            )
            print("  Reset:          {}".format("yes" if plan.reset else "no"))
            if plan.include_template:
                print("  Reset template: yes")
            if plan.configure_codex:
                print("  Global config:  update")
            print("")
        if config_plan is not None:
            if config_plan.changed:
                print(config_plan.diff(), end="")
            else:
                print("Global Codex config already matches the selected values.")
            print("")

    def _confirm(self) -> bool:
        if bool(getattr(self.args, "dry_run", False)):
            return True
        if bool(getattr(self.args, "yes", False)):
            return True
        if not self._tty_available():
            raise InstallerError(
                "confirmation requires a terminal or --yes",
                stage="confirmation",
            )
        return input("Proceed? [y/N] ").strip().lower() == "y"

    def _apply_host(
        self, plan: HostInstallPlan, before: Optional[Set[str]] = None
    ) -> HostResult:
        if not plan.reset and not plan.components and not before:
            return HostResult(plan.host, "noop")
        if plan.host == "claude":
            try:
                self._claude(plan.components).deploy(
                    reset=plan.reset,
                    reset_template=plan.include_template,
                )
                return HostResult("claude", "success")
            except InstallerError as exc:
                return HostResult("claude", "failed", exc.render())

        installer = self._codex()
        try:
            installer.install(
                plan.components,
                reset=plan.reset,
                include_template=plan.include_template,
            )
            return HostResult("codex", "success")
        except InstallerError as exc:
            status = "partial" if installer.completed else "failed"
            return HostResult("codex", status, exc.render())

    @staticmethod
    def _combine_codex_result(
        component_result: HostResult,
        *,
        config_requested: bool,
        config_changed: bool,
        config_applied: bool,
        config_errors: Sequence[str],
    ) -> HostResult:
        if not config_requested:
            return component_result

        details = list(config_errors)
        if component_result.detail:
            details.append(component_result.detail)

        if config_errors:
            status = (
                "failed"
                if component_result.status == "failed" and not config_applied
                else "partial"
            )
        elif component_result.status in ("failed", "partial"):
            status = "partial"
        elif component_result.status == "noop" and config_changed:
            status = "success"
        else:
            status = component_result.status

        return HostResult("codex", status, "\n    ".join(details))

    @staticmethod
    def _print_results(results: Sequence[HostResult], *, dry_run: bool) -> int:
        print("")
        print("Host results:")
        for result in results:
            print("  {:12} {}".format(HOST_LABELS[result.host] + ":", result.status))
            if result.detail:
                print("    {}".format(result.detail))
        if all(result.status in ("success", "noop") for result in results):
            print("")
            print(
                "Dry run complete. No files were modified."
                if dry_run
                else "Installation complete."
            )
            return 0
        print(
            "Installation incomplete: one or more host operations failed.",
            file=sys.stderr,
        )
        return 1

    def interactive(self) -> int:
        if not self._tty_available():
            print(
                "installer: interactive installation requires a terminal; "
                "use a host subcommand with --yes",
                file=sys.stderr,
            )
            return 2
        detected = {
            host: shutil.which(host) is not None for host in ("claude", "codex")
        }
        self._print_detection(detected)
        if not any(detected.values()):
            print(
                "No supported host was detected. Install Claude Code or Codex first.",
                file=sys.stderr,
            )
            return 1

        sections = []
        current = {}  # type: Dict[str, Set[str]]
        for host in ("claude", "codex"):
            if not detected[host]:
                continue
            installed = self._current(host)
            current[host] = installed
            sections.append(
                {
                    "host": host,
                    "label": HOST_LABELS[host],
                    "version": self._host_version(host),
                    "components": self._components(host),
                    "selected": installed or set(self._recommended(host)),
                }
            )

        plans = prompt_install_plan(sys.stdin, sys.stdout, sections=sections)
        if not plans:
            print("Exit. No changes were made.")
            return 0

        config_editor = None  # type: Optional[CodexConfigEditor]
        config_plan = None  # type: Optional[ConfigPlan]
        if any(plan.configure_codex for plan in plans):
            config_editor = CodexConfigEditor(
                self._codex().codex_home,
                dry_run=bool(getattr(self.args, "dry_run", False)),
            )
            settings = prompt_settings(config_editor.inspect())
            config_plan = config_editor.plan(settings)

        self._print_plan(plans, current, config_plan)
        if not self._confirm():
            print("Exit. No changes were made.")
            return 0

        results = []
        for plan in plans:
            config_errors = []  # type: List[str]
            config_ready = False
            config_applied = False
            if plan.host == "codex" and plan.configure_codex:
                assert config_editor is not None and config_plan is not None
                try:
                    config_applied = bool(
                        config_editor.apply(config_plan, show_diff=False)
                    )
                    config_ready = True
                except InstallerError as exc:
                    config_applied = exc.operation == "rollback-config"
                    config_errors.append(exc.render())

            result = self._apply_host(plan, current.get(plan.host))

            if (
                plan.host == "codex"
                and plan.configure_codex
                and config_ready
                and config_editor is not None
                and config_plan is not None
            ):
                try:
                    config_editor.verify(config_plan)
                except InstallerError as exc:
                    config_errors.append(exc.render())

            result = self._combine_codex_result(
                result,
                config_requested=plan.host == "codex" and plan.configure_codex,
                config_changed=bool(
                    config_plan is not None and config_plan.changed
                ),
                config_applied=config_applied,
                config_errors=config_errors,
            )
            results.append(result)
        return self._print_results(
            results, dry_run=bool(getattr(self.args, "dry_run", False))
        )

    def _automation_components(self, host: str) -> List[str]:
        if self.args.recommended:
            return self._recommended(host)
        return self._validate_components(host, csv_items(self.args.components))

    def automation(self) -> int:
        host = self.args.host
        if shutil.which(host) is None:
            print(
                "installer [host={} stage=detect]: {} CLI was not found".format(
                    host, host
                ),
                file=sys.stderr,
            )
            return 1

        if self.args.action == "configure":
            editor = CodexConfigEditor(
                self._codex().codex_home,
                dry_run=self.args.dry_run,
            )
            if self.args.recommended:
                settings = RECOMMENDED_SETTINGS
            else:
                if not self._tty_available():
                    print(
                        "installer: codex configure requires a terminal or "
                        "--recommended",
                        file=sys.stderr,
                    )
                    return 2
                settings = prompt_settings(editor.inspect())
            plan = editor.plan(settings)
            if plan.changed:
                print(plan.diff(), end="")
            else:
                print("Global Codex config already matches the selected values.")
            if not self._confirm():
                print("Exit. No changes were made.")
                return 0
            editor.apply(plan, show_diff=False)
            return 0

        if self.args.action == "uninstall":
            current = self._current(host)
            print("{} uninstall: {}".format(HOST_LABELS[host], csv_value(sorted(current)) or "none"))
            if not self._confirm():
                print("Exit. No changes were made.")
                return 0
            if not current:
                return self._print_results(
                    [HostResult(host, "noop")], dry_run=self.args.dry_run
                )
            if host == "claude":
                try:
                    self._claude(None).uninstall(confirm=False)
                    result = HostResult(host, "success")
                except InstallerError as exc:
                    result = HostResult(host, "failed", exc.render())
            else:
                adapter = self._codex()
                try:
                    adapter.uninstall()
                    result = HostResult(host, "success")
                except InstallerError as exc:
                    result = HostResult(
                        host,
                        "partial" if adapter.completed else "failed",
                        exc.render(),
                    )
            return self._print_results([result], dry_run=self.args.dry_run)

        components = self._automation_components(host)
        current = {host: self._current(host)}
        plan = HostInstallPlan(
            host=host,
            components=components,
            reset=self.args.action == "reset",
            include_template=bool(getattr(self.args, "include_template", False)),
        )
        self._print_plan([plan], current, None)
        if not self._confirm():
            print("Exit. No changes were made.")
            return 0
        result = self._apply_host(plan, current[host])
        return self._print_results([result], dry_run=self.args.dry_run)

    def run(self) -> int:
        if self.args.host is None:
            return self.interactive()
        return self.automation()


def _add_mutation_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--yes", action="store_true", help="skip confirmation")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")


def _add_bootstrap_passthrough(parser: argparse.ArgumentParser) -> None:
    # install.sh resolves these before Python starts, but keeps the original
    # arguments intact. Accept both before and after the host action so the
    # bootstrap contract does not depend on argparse subparser placement.
    parser.add_argument(
        "--version", default=argparse.SUPPRESS, help=argparse.SUPPRESS
    )
    parser.add_argument(
        "--source-dir", default=argparse.SUPPRESS, help=argparse.SUPPRESS
    )


def _add_selection(parser: argparse.ArgumentParser) -> None:
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument(
        "--recommended",
        action="store_true",
        help="use supported components whose catalog default is true",
    )
    selection.add_argument(
        "--components",
        help="complete comma-separated desired component set",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Install hukuhaka-harness")
    parser.add_argument("--repo-root", type=Path, required=True, help=argparse.SUPPRESS)
    parser.add_argument("--resolved-version", help=argparse.SUPPRESS)
    parser.add_argument("--local-source", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--version", help=argparse.SUPPRESS)
    parser.add_argument("--source-dir", help=argparse.SUPPRESS)
    hosts = parser.add_subparsers(dest="host")
    for host in ("claude", "codex"):
        host_parser = hosts.add_parser(host)
        actions = host_parser.add_subparsers(dest="action", required=True)
        for action in ("install", "reset"):
            action_parser = actions.add_parser(action)
            _add_selection(action_parser)
            if action == "reset":
                action_parser.add_argument("--include-template", action="store_true")
            _add_mutation_flags(action_parser)
            _add_bootstrap_passthrough(action_parser)
        uninstall = actions.add_parser("uninstall")
        _add_mutation_flags(uninstall)
        _add_bootstrap_passthrough(uninstall)
        if host == "codex":
            configure = actions.add_parser("configure")
            configure.add_argument("--recommended", action="store_true")
            configure.add_argument("--yes", action="store_true")
            configure.add_argument("--dry-run", action="store_true")
            _add_bootstrap_passthrough(configure)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return Installer(args).run()
    except InstallerError as exc:
        print(exc.render(), file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        detail = (getattr(exc, "stderr", None) or "").strip()
        print(
            "installer [stage=external-command]: command failed with status {}{}".format(
                exc.returncode, ": " + detail if detail else ""
            ),
            file=sys.stderr,
        )
        return 1
    except Exception as exc:
        print(
            "installer [stage=unexpected operation={}]: {}".format(
                type(exc).__name__, exc
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
