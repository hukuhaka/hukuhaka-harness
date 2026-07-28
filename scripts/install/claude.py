"""Transactional Claude Code install adapter."""

from __future__ import annotations

import filecmp
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from .common import (
    DriftError,
    FileTransaction,
    InstallerError,
    Manifest,
    StateError,
    installer_state,
    load_json,
    remove_path,
    safe_join,
    sha256_file,
)


@dataclass(frozen=True)
class SourceFile:
    source: Path
    relative: str


@dataclass
class DeploymentPlan:
    files: List[SourceFile]
    stale_files: List[str]
    components: List[str]
    selected_plugins: List[str]
    dropped_plugins: List[str]
    ghost_plugins: List[str]
    marketplace_data: Dict[str, Any]
    agent_teams: bool


class ClaudeDeployment:
    def __init__(
        self,
        repo_root: Path,
        home: Path,
        components: Optional[Sequence[str]],
        *,
        dry_run: bool = False,
        force: bool = False,
    ) -> None:
        self.repo_root = repo_root.resolve()
        self.home = home.resolve()
        self.claude_dir = self.home / ".claude"
        self.manifest_path = self.claude_dir / ".hukuhaka-manifest.json"
        self.marketplace_dir = self.repo_root / "marketplace"
        self.skills_dir = self.repo_root / "skills"
        self.template_path = self.repo_root / "templates" / "CLAUDE.md"
        self.catalog_path = self.repo_root / "components.json"
        self.version_path = self.repo_root / "VERSION"
        self.dry_run = dry_run
        self.force = force
        self.requested_components = None if components is None else list(dict.fromkeys(components))
        self.catalog = self._load_catalog()
        self.marketplace_name = str(self.catalog.get("marketplaces", {}).get("claude", "hukuhaka-plugin"))
        self.marketplace_root = self.claude_dir / "plugins" / self.marketplace_name
        self.marketplace_manifest_rel = "plugins/{}/.claude-plugin/marketplace.json".format(
            self.marketplace_name
        )
        self.marketplace_manifest_path = self.claude_dir / self.marketplace_manifest_rel
        self.version = self._read_version()

    def _load_catalog(self) -> Dict[str, Any]:
        catalog = load_json(self.catalog_path, {})
        if not isinstance(catalog, dict) or not isinstance(catalog.get("components"), list):
            raise StateError(
                "component catalog must contain a components array",
                operation="read-catalog",
                path=str(self.catalog_path),
            )
        return catalog

    def _read_version(self) -> str:
        try:
            version = self.version_path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise StateError(
                "cannot read project version: {}".format(exc),
                operation="read-version",
                path=str(self.version_path),
            ) from exc
        if not version:
            raise StateError("project version is empty", operation="read-version", path=str(self.version_path))
        return version

    @property
    def component_map(self) -> Dict[str, Dict[str, Any]]:
        return {str(item["name"]): item for item in self.catalog["components"]}

    @property
    def all_plugin_names(self) -> List[str]:
        names = []
        for path in sorted(self.marketplace_dir.glob("*/.claude-plugin/plugin.json")):
            names.append(path.parent.parent.name)
        return names

    def selected_components(self) -> List[str]:
        if self.requested_components is None:
            selected = [
                name
                for name, component in self.component_map.items()
                if "claude" in component.get("hosts", {})
            ]
        else:
            selected = self.requested_components
        unknown = [
            name
            for name in selected
            if name not in self.component_map
            or "claude" not in self.component_map[name].get("hosts", {})
        ]
        if unknown:
            raise InstallerError(
                "unknown or unsupported Claude component(s): {}".format(", ".join(unknown)),
                host="claude",
                stage="plan",
                operation="validate-components",
            )
        return selected

    def _claude_path(self, relative: str, *, operation: str) -> Path:
        """Resolve a relative path that came from state we do not control.

        The manifest and the plugin registry are both attacker-editable files.
        Going through safe_join() keeps the root implicit, so a call site cannot
        join the wrong one or forget the check.
        """
        return safe_join(self.claude_dir, relative, operation=operation)

    def _collect_tree(self, source_root: Path, destination_prefix: str) -> List[SourceFile]:
        result = []
        if not source_root.is_dir():
            return result
        for source in sorted(path for path in source_root.rglob("*") if path.is_file()):
            relative = source.relative_to(source_root).as_posix()
            result.append(SourceFile(source, "{}/{}".format(destination_prefix, relative)))
        return result

    def _plugin_metadata(self, plugin_name: str) -> Dict[str, Any]:
        path = self.marketplace_dir / plugin_name / ".claude-plugin" / "plugin.json"
        data = load_json(path, {})
        if not isinstance(data, dict) or data.get("name") != plugin_name:
            raise StateError(
                "invalid plugin manifest for {}".format(plugin_name),
                operation="read-plugin-manifest",
                path=str(path),
            )
        return data

    def _marketplace_data(self, plugins: Sequence[str]) -> Dict[str, Any]:
        entries = []
        for plugin_name in plugins:
            metadata = self._plugin_metadata(plugin_name)
            entries.append(
                {
                    "name": plugin_name,
                    "description": str(metadata.get("description", "")),
                    "version": str(metadata.get("version", "unknown")),
                    "author": {"name": "hukuhaka"},
                    "source": "./{}".format(plugin_name),
                }
            )
        return {
            "name": self.marketplace_name,
            "description": "hukuhaka plugin marketplace",
            "owner": {"name": "hukuhaka"},
            "plugins": entries,
        }

    def _registry_ghosts(self, plugin_names: Set[str]) -> Set[str]:
        installed_path = self.claude_dir / "plugins" / "installed_plugins.json"
        installed = load_json(installed_path, {"plugins": {}})
        if not isinstance(installed, dict) or not isinstance(installed.get("plugins", {}), dict):
            raise StateError(
                "installed plugin registry must contain an object named plugins",
                operation="read-registry",
                path=str(installed_path),
            )
        suffix = "@{}".format(self.marketplace_name)
        ghosts = {
            key[: -len(suffix)]
            for key in installed.get("plugins", {})
            if isinstance(key, str) and key.endswith(suffix) and key[: -len(suffix)] not in plugin_names
        }
        if self.marketplace_root.is_dir():
            for path in self.marketplace_root.iterdir():
                if path.is_dir() and path.name != ".claude-plugin" and path.name not in plugin_names:
                    ghosts.add(path.name)
        # Registry keys are attacker-editable and reach transaction.remove() in
        # deploy(). Validate here so a poisoned key fails during planning --
        # before the transaction opens, and on the dry-run path too.
        for name in sorted(ghosts):
            self._claude_path(
                "plugins/{}/{}".format(self.marketplace_name, name),
                operation="resolve-ghost-plugin",
            )
        return ghosts

    def build_plan(self, manifest: Manifest) -> DeploymentPlan:
        selected = self.selected_components()
        selected_set = set(selected)
        plugin_names = set(self.all_plugin_names)
        selected_plugins = sorted(plugin_names & selected_set)
        files = []  # type: List[SourceFile]
        for plugin_name in selected_plugins:
            files.extend(
                self._collect_tree(
                    self.marketplace_dir / plugin_name,
                    "plugins/{}/{}".format(self.marketplace_name, plugin_name),
                )
            )
        if self.skills_dir.is_dir():
            for skill_dir in sorted(path for path in self.skills_dir.iterdir() if path.is_dir()):
                if skill_dir.name in selected_set:
                    files.extend(self._collect_tree(skill_dir, "skills/{}".format(skill_dir.name)))
        if "claude-md" in selected_set:
            if not self.template_path.is_file():
                raise StateError(
                    "selected template does not exist",
                    operation="collect-files",
                    path=str(self.template_path),
                )
            files.append(SourceFile(self.template_path, "CLAUDE.md"))
        new_relatives = {item.relative for item in files}
        new_relatives.add(self.marketplace_manifest_rel)
        stale = sorted(set(manifest.files) - new_relatives)
        # _check_drift() cannot be the gate: it returns early under --force and
        # for a manifest with no hashes. Validating here covers both, and fails
        # before any file has been copied.
        for relative in stale:
            self._claude_path(relative, operation="plan-stale-file")
        dropped = sorted(
            name for name in manifest.components if name in plugin_names and name not in selected_set
        )
        ghosts = sorted(self._registry_ghosts(plugin_names))
        return DeploymentPlan(
            files=sorted(files, key=lambda item: item.relative),
            stale_files=stale,
            components=sorted(selected),
            selected_plugins=selected_plugins,
            dropped_plugins=dropped,
            ghost_plugins=ghosts,
            marketplace_data=self._marketplace_data(selected_plugins),
            agent_teams="agent-teams" in selected_set,
        )

    def _check_drift(self, manifest: Manifest, plan: DeploymentPlan) -> None:
        if self.force or not manifest.hashes:
            return
        source_by_relative = {item.relative: item.source for item in plan.files}
        changed = []
        touched = set(plan.stale_files) | set(source_by_relative)
        for relative in sorted(touched):
            recorded = manifest.hashes.get(relative)
            target = self._claude_path(relative, operation="check-managed-file-drift")
            if not recorded or not target.is_file():
                continue
            current = sha256_file(target)
            if current == recorded:
                continue
            source = source_by_relative.get(relative)
            if source is not None and sha256_file(source) == current:
                continue
            changed.append(relative)
        if changed:
            raise DriftError(
                "managed files were modified: {}. Re-run with --force to replace them".format(
                    ", ".join(changed)
                ),
                host="claude",
                stage="plan",
                operation="check-managed-file-drift",
                path=str(self.claude_dir),
            )

    def _load_registries(self) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        settings_path = self.claude_dir / "settings.json"
        installed_path = self.claude_dir / "plugins" / "installed_plugins.json"
        known_path = self.claude_dir / "plugins" / "known_marketplaces.json"
        settings = load_json(settings_path, {})
        installed = load_json(installed_path, {"version": 2, "plugins": {}})
        known = load_json(known_path, {})
        for name, data, path in (
            ("settings", settings, settings_path),
            ("installed plugins", installed, installed_path),
            ("known marketplaces", known, known_path),
        ):
            if not isinstance(data, dict):
                raise StateError(
                    "{} registry must be a JSON object".format(name),
                    operation="read-registry",
                    path=str(path),
                )
        if not isinstance(installed.setdefault("plugins", {}), dict):
            raise StateError(
                "installed plugin registry field 'plugins' must be an object",
                operation="read-registry",
                path=str(installed_path),
            )
        return settings, installed, known

    def _update_registries(
        self,
        settings: Dict[str, Any],
        installed: Dict[str, Any],
        known: Dict[str, Any],
        plan: DeploymentPlan,
    ) -> None:
        enabled = settings.setdefault("enabledPlugins", {})
        marketplaces = settings.setdefault("extraKnownMarketplaces", {})
        if not isinstance(enabled, dict) or not isinstance(marketplaces, dict):
            raise StateError("Claude settings plugin fields must be objects", operation="update-registry")
        plugins = installed.setdefault("plugins", {})
        suffix = "@{}".format(self.marketplace_name)
        removed = set(plan.dropped_plugins) | set(plan.ghost_plugins)
        for plugin_name in removed:
            key = plugin_name + suffix
            enabled.pop(key, None)
            plugins.pop(key, None)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        for plugin_name in plan.selected_plugins:
            key = plugin_name + suffix
            enabled[key] = True
            metadata = self._plugin_metadata(plugin_name)
            existing = plugins.get(key)
            entry = {
                "scope": "user",
                "installPath": str(self.marketplace_root / plugin_name),
                "version": str(metadata.get("version", "unknown")),
                "installedAt": now,
                "lastUpdated": now,
            }
            if isinstance(existing, list) and existing and isinstance(existing[0], dict):
                entry["installedAt"] = existing[0].get("installedAt", now)
                existing[0].update(entry)
            else:
                plugins[key] = [entry]
        marketplaces[self.marketplace_name] = {
            "source": {"source": "directory", "path": str(self.marketplace_root)}
        }
        known[self.marketplace_name] = {
            "source": {"source": "directory", "path": str(self.marketplace_root)},
            "installLocation": str(self.marketplace_root),
            "lastUpdated": now,
        }

    def _write_registries(
        self,
        transaction: FileTransaction,
        settings: Dict[str, Any],
        installed: Dict[str, Any],
        known: Dict[str, Any],
        *,
        existing_only: bool = False,
    ) -> None:
        registries = (
            (self.claude_dir / "settings.json", settings),
            (self.claude_dir / "plugins" / "installed_plugins.json", installed),
            (self.claude_dir / "plugins" / "known_marketplaces.json", known),
        )
        for path, data in registries:
            if not existing_only or path.exists():
                transaction.write_json(path, data)

    def _apply_agent_teams(self, settings: Dict[str, Any], enabled: bool) -> None:
        env = settings.setdefault("env", {})
        if not isinstance(env, dict):
            raise StateError("Claude settings env field must be an object", operation="configure-agent-teams")
        if enabled:
            env["CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"] = "1"
        else:
            env.pop("CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS", None)
            if not env:
                settings.pop("env", None)

    def _print_header(self, manifest: Manifest, plan: DeploymentPlan) -> None:
        plugins = " ".join(plan.selected_plugins) if plan.selected_plugins else "none"
        if manifest.version and manifest.version != self.version:
            print("hukuhaka-harness v{} → v{} (plugins: {})".format(manifest.version, self.version, plugins))
        elif manifest.version:
            print("hukuhaka-harness v{} (reinstall — plugins: {})".format(self.version, plugins))
        else:
            print("hukuhaka-harness v{} (fresh install — plugins: {})".format(self.version, plugins))
        print("")

    def current_components(self) -> Set[str]:
        return set(Manifest.load(self.manifest_path).components)

    def verify(self, expected: Sequence[str]) -> None:
        manifest = Manifest.load(self.manifest_path)
        if set(manifest.components) != set(expected):
            raise InstallerError(
                "Claude post-install manifest does not match the requested components",
                host="claude",
                stage="verify",
            )
        missing = [
            relative
            for relative in manifest.files
            if not self._claude_path(relative, operation="verify-managed-file").is_file()
        ]
        changed = [
            relative
            for relative, digest in manifest.hashes.items()
            if self._claude_path(relative, operation="verify-managed-file").is_file()
            and sha256_file(
                self._claude_path(relative, operation="verify-managed-file")
            )
            != digest
        ]
        if missing or changed:
            raise InstallerError(
                "Claude managed files failed verification: {}".format(
                    ", ".join(sorted(set(missing + changed)))
                ),
                host="claude",
                stage="verify",
            )

    def deploy(
        self,
        *,
        reset: bool = False,
        reset_template: bool = False,
    ) -> None:
        with installer_state(self.claude_dir, dry_run=self.dry_run) as writable:
            manifest = Manifest.load(self.manifest_path)
            plan = self.build_plan(manifest)
            self._check_drift(manifest, plan)
            settings, installed, known = self._load_registries()
            self._update_registries(settings, installed, known, plan)
            self._apply_agent_teams(settings, plan.agent_teams)
            self._print_header(manifest, plan)
            print("Deploying:")
            if "hukuhaka-codex" in plan.components:
                print(
                    "  license: hukuhaka-codex is an Apache-2.0 derivative of "
                    "openai/codex-plugin-cc (see plugin LICENSE and NOTICE)"
                )
            if not writable:
                for item in plan.files:
                    print("  [dry-run] {}".format(item.relative))
                print("  [dry-run] {}".format(self.marketplace_manifest_rel))
                for relative in plan.stale_files:
                    print("  [dry-run] rm {}".format(relative))
                if reset:
                    print("  [dry-run] reset managed plugins/skills")
                    if reset_template:
                        print("  [dry-run] reset managed CLAUDE.md")
                print("  {} files".format(len(plan.files)))
                print("  [dry-run] would update Claude registries and manifest")
                print("")
                print("Dry run complete. No files were modified.")
                return
            added = updated = unchanged = removed = 0
            with FileTransaction(self.claude_dir) as transaction:
                if reset:
                    transaction.remove(self.marketplace_root)
                    transaction.remove(
                        self.claude_dir / "plugins" / "cache" / self.marketplace_name
                    )
                    managed_skills = {
                        relative.split("/", 2)[1]
                        for relative in manifest.files
                        if relative.startswith("skills/")
                        and len(relative.split("/", 2)) > 1
                    }
                    for name in sorted(managed_skills):
                        transaction.remove(
                            self._claude_path(
                                "skills/{}".format(name),
                                operation="reset-managed-skill",
                            )
                        )
                    if reset_template:
                        transaction.remove(self.claude_dir / "CLAUDE.md")
                for item in plan.files:
                    target = self.claude_dir / item.relative
                    if not target.exists():
                        added += 1
                        transaction.copy_file(item.source, target)
                    elif not filecmp.cmp(str(item.source), str(target), shallow=False):
                        updated += 1
                        transaction.copy_file(item.source, target)
                    else:
                        unchanged += 1
                marketplace_bytes = (
                    json.dumps(plan.marketplace_data, indent=2, ensure_ascii=True) + "\n"
                ).encode("utf-8")
                if not self.marketplace_manifest_path.exists():
                    added += 1
                    transaction.write_bytes(self.marketplace_manifest_path, marketplace_bytes)
                elif self.marketplace_manifest_path.read_bytes() != marketplace_bytes:
                    updated += 1
                    transaction.write_bytes(self.marketplace_manifest_path, marketplace_bytes)
                else:
                    unchanged += 1

                for relative in plan.stale_files:
                    if transaction.remove(
                        self._claude_path(relative, operation="remove-stale-file")
                    ):
                        removed += 1
                legacy = self.claude_dir / "plugins" / "hukuhaka-project-mapper"
                transaction.remove(legacy)
                for plugin_name in sorted(set(plan.dropped_plugins) | set(plan.ghost_plugins)):
                    transaction.remove(
                        self._claude_path(
                            "plugins/{}/{}".format(self.marketplace_name, plugin_name),
                            operation="remove-ghost-plugin",
                        )
                    )
                    transaction.remove(
                        self._claude_path(
                            "plugins/cache/{}/{}".format(self.marketplace_name, plugin_name),
                            operation="remove-ghost-plugin",
                        )
                    )

                transaction.remove(
                    self.claude_dir / "plugins" / "cache" / self.marketplace_name
                )
                self._write_registries(transaction, settings, installed, known)
                all_files = sorted([item.relative for item in plan.files] + [self.marketplace_manifest_rel])
                hashes = {
                    relative: sha256_file(self.claude_dir / relative)
                    for relative in all_files
                    if (self.claude_dir / relative).is_file()
                }
                next_manifest = Manifest(
                    version=self.version,
                    components=plan.components,
                    files=all_files,
                    hashes=hashes,
                )
                transaction.write_json(self.manifest_path, next_manifest.as_dict())
                transaction.commit()

            cache = self.claude_dir / "plugins" / "cache" / self.marketplace_name
            if not cache.exists():
                print("  [ok] cache invalidated")
            for root in (self.claude_dir / "plugins", self.claude_dir / "skills"):
                if root.is_dir():
                    for directory in sorted(
                        (path for path in root.rglob("*") if path.is_dir()),
                        key=lambda path: len(path.parts),
                        reverse=True,
                    ):
                        try:
                            directory.rmdir()
                        except OSError:
                            pass
            summary = []
            if added:
                summary.append("{} added".format(added))
            if updated:
                summary.append("{} updated".format(updated))
            if removed:
                summary.append("{} removed".format(removed))
            if unchanged:
                summary.append("{} unchanged".format(unchanged))
            print("  {}".format(", ".join(summary) if summary else "no file changes"))
            print("  [ok] marketplace.json ({} plugin(s))".format(len(plan.selected_plugins)))
            print("")
            print("Deploy complete. v{}".format(self.version))
        if not self.dry_run:
            self.verify(self.selected_components())

    def reset_for_install(self, *, reset_template: bool = False) -> None:
        """Remove installer-owned plugins/skills before a clean reinstall."""
        with installer_state(self.claude_dir, dry_run=self.dry_run) as writable:
            manifest = Manifest.load(self.manifest_path)
            if not manifest.components and not manifest.files:
                print("Claude Code: no managed installation to reset.")
                return
            remove_files = {
                relative
                for relative in manifest.files
                if relative.startswith("plugins/{}/".format(self.marketplace_name))
                or relative.startswith("skills/")
                or relative == self.marketplace_manifest_rel
                or (reset_template and relative == "CLAUDE.md")
            }
            # The startswith() filter above is not containment --
            # "plugins/<mp>/../../../x" satisfies it. Resolve every entry now,
            # before the drift check (which --force skips) and before the
            # dry-run listing, so nothing is announced that will not happen.
            remove_targets = {
                relative: self._claude_path(relative, operation="reset-managed-file")
                for relative in sorted(remove_files)
            }
            if not self.force:
                changed = []
                for relative in sorted(remove_files):
                    target = remove_targets[relative]
                    recorded = manifest.hashes.get(relative)
                    if recorded and target.is_file() and sha256_file(target) != recorded:
                        changed.append(relative)
                if changed:
                    raise DriftError(
                        "managed files were modified: {}. Re-run with --force to reset them".format(
                            ", ".join(changed)
                        ),
                        host="claude",
                        stage="reset",
                        operation="check-managed-file-drift",
                        path=str(self.claude_dir),
                    )

            settings, installed, known = self._load_registries()
            suffix = "@{}".format(self.marketplace_name)
            enabled = settings.get("enabledPlugins", {})
            if isinstance(enabled, dict):
                for key in list(enabled):
                    if key.endswith(suffix):
                        del enabled[key]
                if not enabled:
                    settings.pop("enabledPlugins", None)
            marketplaces = settings.get("extraKnownMarketplaces", {})
            if isinstance(marketplaces, dict):
                marketplaces.pop(self.marketplace_name, None)
                if not marketplaces:
                    settings.pop("extraKnownMarketplaces", None)
            plugins = installed.get("plugins", {})
            if isinstance(plugins, dict):
                for key in list(plugins):
                    if key.endswith(suffix):
                        del plugins[key]
            known.pop(self.marketplace_name, None)

            removed_components = set()
            for name in manifest.components:
                component = self.component_map.get(name)
                if component is None:
                    component = next(
                        (
                            item
                            for item in self.catalog["components"]
                            if name in item.get("aliases", [])
                        ),
                        None,
                    )
                kind = component.get("kind") if component else "plugin"
                if kind in ("plugin", "skill") or (reset_template and kind == "template"):
                    removed_components.add(name)

            print("Resetting Claude Code:")
            if not writable:
                for relative in sorted(remove_files):
                    print("  [dry-run] rm {}".format(relative))
                return
            with FileTransaction(self.claude_dir) as transaction:
                for relative in sorted(remove_files):
                    transaction.remove(remove_targets[relative])
                transaction.remove(self.marketplace_root)
                transaction.remove(
                    self.claude_dir / "plugins" / "cache" / self.marketplace_name
                )
                self._write_registries(
                    transaction,
                    settings,
                    installed,
                    known,
                    existing_only=True,
                )
                remaining_files = sorted(set(manifest.files) - remove_files)
                remaining_components = sorted(
                    set(manifest.components) - removed_components
                )
                if remaining_files or remaining_components:
                    next_manifest = Manifest(
                        version=manifest.version,
                        components=remaining_components,
                        files=remaining_files,
                        hashes={
                            relative: digest
                            for relative, digest in manifest.hashes.items()
                            if relative in remaining_files
                        },
                    )
                    transaction.write_json(self.manifest_path, next_manifest.as_dict())
                else:
                    transaction.remove(self.manifest_path)
                transaction.commit()
            print("  [ok] managed plugins/skills reset")

    def uninstall(self, confirm: bool = True) -> None:
        if confirm and not self.force and not self.dry_run:
            print("This will remove all hukuhaka-harness files from {}.".format(self.claude_dir))
            answer = input("Continue? [y/N] ")
            if answer.lower() != "y":
                raise InstallerError("aborted", host="claude", stage="uninstall")
        with installer_state(self.claude_dir, dry_run=self.dry_run) as writable:
            manifest = Manifest.load(self.manifest_path)
            if not manifest.components and not manifest.files:
                print("No manifest found — nothing to uninstall.")
                return
            settings, installed, known = self._load_registries()
            suffix = "@{}".format(self.marketplace_name)
            enabled = settings.get("enabledPlugins", {})
            if isinstance(enabled, dict):
                for key in list(enabled):
                    if key.endswith(suffix):
                        del enabled[key]
                if not enabled:
                    settings.pop("enabledPlugins", None)
            marketplaces = settings.get("extraKnownMarketplaces", {})
            if isinstance(marketplaces, dict):
                marketplaces.pop(self.marketplace_name, None)
                if not marketplaces:
                    settings.pop("extraKnownMarketplaces", None)
            env = settings.get("env", {})
            if isinstance(env, dict):
                env.pop("CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS", None)
                if not env:
                    settings.pop("env", None)
            plugins = installed.get("plugins", {})
            if isinstance(plugins, dict):
                for key in list(plugins):
                    if key.endswith(suffix):
                        del plugins[key]
            known.pop(self.marketplace_name, None)
            # uninstall applies no prefix filter at all, so every manifest entry
            # is a deletion target. Resolve them all before anything is printed.
            targets = [
                (relative, self._claude_path(relative, operation="uninstall-managed-file"))
                for relative in manifest.files
            ]
            print("Uninstalling:")
            if not writable:
                for relative, target in targets:
                    if target.exists():
                        print("  [dry-run] rm {}".format(relative))
                print("Dry run — no files modified.")
                return
            count = 0
            with FileTransaction(self.claude_dir) as transaction:
                for relative, target in targets:
                    if transaction.remove(target):
                        print("  [ok] rm {}".format(relative))
                        count += 1
                transaction.remove(self.marketplace_root)
                transaction.remove(self.claude_dir / "plugins" / "cache" / self.marketplace_name)
                self._write_registries(
                    transaction,
                    settings,
                    installed,
                    known,
                    existing_only=True,
                )
                transaction.remove(self.manifest_path)
                transaction.commit()
            for root in (self.claude_dir / "plugins", self.claude_dir / "skills"):
                if root.is_dir():
                    for directory in sorted(
                        (path for path in root.rglob("*") if path.is_dir()),
                        key=lambda path: len(path.parts),
                        reverse=True,
                    ):
                        try:
                            directory.rmdir()
                        except OSError:
                            pass
            print("")
            print("Uninstalled {} files.".format(count))
