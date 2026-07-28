"""Codex native marketplace install adapter."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from .common import (
    DriftError,
    FileTransaction,
    InstallerError,
    StateError,
    installer_state,
    load_json,
)


BEGIN = b"<!-- hukuhaka-harness:begin -->"
END = b"<!-- hukuhaka-harness:end -->"
GUIDANCE_MANIFEST = ".hukuhaka-guidance-manifest.json"


def resolve_codex_home(
    environ: Optional[Mapping[str, str]] = None,
    *,
    fallback_home: Optional[Path] = None,
) -> Path:
    values = os.environ if environ is None else environ
    configured = values.get("CODEX_HOME", "").strip()
    if configured:
        return Path(configured).expanduser()
    return (Path.home() if fallback_home is None else fallback_home) / ".codex"


def _hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _block(template: bytes) -> bytes:
    return BEGIN + b"\n" + template.rstrip(b"\r\n") + b"\n" + END


def _bounds(content: bytes) -> Optional[Tuple[int, int]]:
    if not content.count(BEGIN) and not content.count(END):
        return None
    if content.count(BEGIN) != 1 or content.count(END) != 1:
        raise StateError(
            "AGENTS.md contains duplicate or incomplete hukuhaka markers",
            host="codex",
            stage="guidance",
        )
    start = content.index(BEGIN)
    end_marker = content.index(END)
    if end_marker < start:
        raise StateError(
            "AGENTS.md managed markers are out of order",
            host="codex",
            stage="guidance",
        )
    return start, end_marker + len(END)


class CodexGuidanceDeployment:
    def __init__(
        self,
        source: Path,
        codex_home: Path,
        version: str,
        *,
        enabled: bool,
        dry_run: bool = False,
        force: bool = False,
    ) -> None:
        self.source = source
        self.codex_home = codex_home
        self.version = version
        self.enabled = enabled
        self.dry_run = dry_run
        self.force = force
        self.target = codex_home / "AGENTS.md"
        self.override = codex_home / "AGENTS.override.md"
        self.manifest_path = codex_home / GUIDANCE_MANIFEST

    def _read_target(self) -> bytes:
        if not self.target.exists() and not self.target.is_symlink():
            return b""
        if self.target.is_symlink() or not self.target.is_file():
            raise StateError(
                "Codex AGENTS.md must be a regular file",
                host="codex",
                stage="guidance",
                path=str(self.target),
            )
        content = self.target.read_bytes()
        try:
            content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise StateError(
                "Codex AGENTS.md must be UTF-8",
                host="codex",
                stage="guidance",
                path=str(self.target),
            ) from exc
        return content

    def _manifest(self) -> Optional[Dict[str, Any]]:
        if not self.manifest_path.exists():
            return None
        data = load_json(self.manifest_path, {})
        required = {
            "schemaVersion": int,
            "component": str,
            "version": str,
            "target": str,
            "managedHash": str,
            "prefix": str,
            "suffix": str,
        }
        if not isinstance(data, dict) or any(
            not isinstance(data.get(key), value_type) for key, value_type in required.items()
        ):
            raise StateError(
                "invalid Codex guidance manifest",
                host="codex",
                stage="guidance",
                path=str(self.manifest_path),
            )
        if (
            data["schemaVersion"] != 1
            or data["component"] != "agents-md"
            or data["target"] != "AGENTS.md"
            or data["prefix"] not in ("", "\n", "\n\n")
            or data["suffix"] not in ("", "\n")
        ):
            raise StateError(
                "unsupported Codex guidance manifest",
                host="codex",
                stage="guidance",
                path=str(self.manifest_path),
            )
        return data

    def _validate_current(
        self,
        content: bytes,
        bounds: Optional[Tuple[int, int]],
        manifest: Optional[Dict[str, Any]],
    ) -> None:
        if bounds is not None and manifest is None:
            raise StateError(
                "managed AGENTS.md block exists without its manifest",
                host="codex",
                stage="guidance",
                path=str(self.target),
            )
        if manifest is not None and bounds is None:
            raise DriftError(
                "Codex guidance manifest exists but its managed block is missing",
                host="codex",
                stage="guidance",
                path=str(self.target),
            )
        if bounds is not None and manifest is not None:
            start, end = bounds
            if _hash(content[start:end]) != manifest["managedHash"] and not self.force:
                raise DriftError(
                    "managed AGENTS.md block changed; use --force to replace it",
                    host="codex",
                    stage="guidance",
                    path=str(self.target),
                )

    def _warn_override(self) -> None:
        if self.override.exists():
            print(
                "Warning: {} shadows global AGENTS.md; managed guidance is inactive.".format(
                    self.override
                ),
                file=sys.stderr,
            )

    def _plan_deploy(self) -> Tuple[bytes, Dict[str, Any]]:
        """Read state, validate it, and compute the merge. Mutates nothing.

        Callers that write must run this inside installer_state(), after
        recover_pending(), so the state it reads is the state it writes over.
        """
        block = _block(self.source.read_bytes())
        content = self._read_target()
        bounds = _bounds(content)
        manifest = self._manifest()
        self._validate_current(content, bounds, manifest)

        if bounds is None:
            prefix = b"" if not content else (b"\n" if content.endswith(b"\n") else b"\n\n")
            suffix = b"\n"
            merged = content + prefix + block + suffix
        else:
            start, end = bounds
            prefix = str(manifest["prefix"]).encode()
            suffix = str(manifest["suffix"]).encode()
            merged = content[:start] + block + content[end:]

        next_manifest = {
            "schemaVersion": 1,
            "component": "agents-md",
            "version": self.version,
            "target": "AGENTS.md",
            "managedHash": _hash(block),
            "prefix": prefix.decode(),
            "suffix": suffix.decode(),
        }
        return merged, next_manifest

    def deploy(self) -> None:
        if not self.enabled:
            # Delegate before taking the lock: uninstall() acquires it itself and
            # flock is not reentrant across file descriptors.
            self.uninstall()
            return
        with installer_state(self.codex_home, dry_run=self.dry_run) as writable:
            merged, next_manifest = self._plan_deploy()
            self._warn_override()
            if not writable:
                print("  [dry-run] merge agents-md into {}".format(self.target))
                return
            with FileTransaction(self.codex_home) as transaction:
                transaction.write_bytes(self.target, merged)
                transaction.write_json(self.manifest_path, next_manifest)
                transaction.commit()
        print("  [ok] agents-md -> {}".format(self.target))

    def _plan_uninstall(self) -> Optional[bytes]:
        """Return the post-removal AGENTS.md bytes, or None when there is nothing
        to remove. Mutates nothing; same locking requirement as _plan_deploy."""
        content = self._read_target()
        bounds = _bounds(content)
        manifest = self._manifest()
        if bounds is None and manifest is None:
            return None
        self._validate_current(content, bounds, manifest)
        assert bounds is not None and manifest is not None
        start, end = bounds
        prefix = manifest["prefix"].encode()
        suffix = manifest["suffix"].encode()
        if content[max(0, start - len(prefix)):start] != prefix or content[end:end + len(suffix)] != suffix:
            if not self.force:
                raise DriftError(
                    "text surrounding the managed AGENTS.md block changed; use --force to remove it",
                    host="codex",
                    stage="guidance",
                    path=str(self.target),
                )
            prefix = b""
            suffix = b""
        return content[:start - len(prefix)] + content[end + len(suffix):]

    def uninstall(self) -> None:
        if self.dry_run:
            merged = self._plan_uninstall()
            if merged is not None:
                print("  [dry-run] remove agents-md from {}".format(self.target))
            return
        with installer_state(self.codex_home, dry_run=self.dry_run) as writable:
            # Recovery must happen before the no-op decision. A killed removal
            # can leave the manifest absent while the journal still owns the
            # pre-removal state.
            merged = self._plan_uninstall()
            if merged is None:
                return
            assert writable
            with FileTransaction(self.codex_home) as transaction:
                if merged:
                    transaction.write_bytes(self.target, merged)
                else:
                    transaction.remove(self.target)
                transaction.remove(self.manifest_path)
                transaction.commit()
        print("  [ok] removed agents-md from {}".format(self.target))


def run_json(command: Sequence[str], *, stage: str) -> Dict[str, Any]:
    try:
        result = subprocess.run(
            command,
            check=True,
            text=True,
            capture_output=True,
            timeout=30,
        )
    except FileNotFoundError as exc:
        raise InstallerError(
            "command not found: {}".format(command[0]),
            host="codex",
            stage=stage,
            operation="run-command",
        ) from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        raise InstallerError(
            "command failed ({}): {}".format(exc.returncode, detail or "no output"),
            host="codex",
            stage=stage,
            operation="run-command",
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise InstallerError(
            "command timed out after 30 seconds: {}".format(" ".join(command)),
            host="codex",
            stage=stage,
            operation="run-command",
        ) from exc
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise InstallerError(
            "command returned invalid JSON: {}".format(exc),
            host="codex",
            stage=stage,
            operation="parse-command-output",
        ) from exc
    if not isinstance(data, dict):
        raise InstallerError("command JSON root must be an object", host="codex", stage=stage)
    return data


def git_commit(root: Path, ref: str) -> Optional[str]:
    result = subprocess.run(
        ("git", "-C", str(root), "rev-parse", ref),
        text=True,
        capture_output=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


class CodexInstaller:
    """Own the complete Codex plugin and AGENTS.md lifecycle."""

    def __init__(
        self,
        repo_root: Path,
        catalog: Mapping[str, Any],
        version: str,
        *,
        local_source: bool,
        dry_run: bool = False,
        force: bool = False,
    ) -> None:
        self.repo_root = repo_root.resolve()
        self.catalog = catalog
        self.version = version.lstrip("v")
        self.local_source = local_source
        self.dry_run = dry_run
        self.force = force
        self.codex_home = resolve_codex_home()
        self.marketplace = str(
            catalog.get("marketplaces", {}).get("codex", "hukuhaka-harness")
        )
        self.aliases = {
            str(alias): str(component["name"])
            for component in catalog.get("components", [])
            for alias in component.get("aliases", [])
        }
        self.completed = []  # type: List[str]

    @property
    def plugin_names(self) -> Set[str]:
        return {
            str(component["name"])
            for component in self.catalog.get("components", [])
            if component.get("kind") == "plugin"
            and "codex" in component.get("hosts", {})
        }

    def _require_cli(self) -> None:
        if shutil.which("codex") is None and not self.dry_run:
            raise InstallerError(
                "codex CLI is required for Codex lifecycle operations",
                host="codex",
                stage="preflight",
            )

    def _plugins(self) -> List[Dict[str, Any]]:
        if shutil.which("codex") is None:
            return []
        data = run_json(("codex", "plugin", "list", "--json"), stage="read-state")
        return [
            plugin
            for plugin in data.get("installed", [])
            if isinstance(plugin, dict)
            and plugin.get("marketplaceName") == self.marketplace
            and plugin.get("name")
        ]

    def _deploy_plugins(self, components: Sequence[str]) -> None:
        components = list(dict.fromkeys(item for item in components if item))
        if not components:
            return
        source = (
            str(self.repo_root)
            if self.local_source
            else "hukuhaka/hukuhaka-harness"
        )
        if self.dry_run:
            print("Codex deploy:")
            print("  [dry-run] marketplace add {}".format(source))
            for component in components:
                print("  [dry-run] plugin add {}@{}".format(component, self.marketplace))
            return

        command = ["codex", "plugin", "marketplace", "add", source, "--json"]
        if not self.local_source:
            command.extend(("--ref", "v{}".format(self.version)))
        add_result = run_json(command, stage="marketplace-add")
        already_added = bool(add_result.get("alreadyAdded"))

        listing = run_json(
            ("codex", "plugin", "marketplace", "list", "--json"),
            stage="marketplace-list",
        )
        info = next(
            (
                item
                for item in listing.get("marketplaces", [])
                if isinstance(item, dict) and item.get("name") == self.marketplace
            ),
            None,
        )
        if info is None:
            raise InstallerError(
                "marketplace '{}' was not returned after add".format(self.marketplace),
                host="codex",
                stage="marketplace-verify",
            )
        source_info = info.get("marketplaceSource", {})
        source_type = source_info.get("sourceType", "") if isinstance(source_info, dict) else ""
        source_value = source_info.get("source", "") if isinstance(source_info, dict) else ""
        root_value = info.get("root", "")

        if self.local_source:
            try:
                actual = Path(str(source_value)).resolve(strict=True)
                expected = Path(source).resolve(strict=True)
            except OSError as exc:
                raise InstallerError(
                    "cannot resolve local marketplace source: {}".format(exc),
                    host="codex",
                    stage="marketplace-verify",
                    path=str(source_value),
                ) from exc
            if source_type != "local" or actual != expected:
                raise InstallerError(
                    "marketplace '{}' already points at a different source".format(
                        self.marketplace
                    ),
                    host="codex",
                    stage="marketplace-verify",
                )
        elif source_type == "local":
            raise InstallerError(
                "marketplace '{}' points at local source {}; remove or repoint it before using the public installer".format(
                    self.marketplace, source_value
                ),
                host="codex",
                stage="marketplace-verify",
            )

        if already_added and not self.local_source:
            root = Path(str(root_value))
            expected_ref = "v{}^{{commit}}".format(self.version)
            current = git_commit(root, "HEAD")
            expected = git_commit(root, expected_ref)
            if not current or not expected or current != expected:
                raise InstallerError(
                    "marketplace '{}' already exists at a different ref; remove or repoint it before installing v{}".format(
                        self.marketplace, self.version
                    ),
                    host="codex",
                    stage="version-pin-verify",
                    path=str(root),
                )

        for component in components:
            run_json(
                (
                    "codex",
                    "plugin",
                    "add",
                    "{}@{}".format(component, self.marketplace),
                    "--json",
                ),
                stage="plugin-add",
            )
            print("  [ok] {}@{}".format(component, self.marketplace))

    def current_components(self) -> Set[str]:
        names = {
            self.aliases.get(str(plugin["name"]), str(plugin["name"]))
            for plugin in self._plugins()
        }
        if (self.codex_home / GUIDANCE_MANIFEST).is_file():
            names.add("agents-md")
        return names

    def _remove_plugin(self, plugin: Mapping[str, Any], *, stage: str) -> None:
        plugin_id = str(plugin.get("pluginId", ""))
        if not plugin_id:
            raise InstallerError(
                "installed Codex plugin has no pluginId",
                host="codex",
                stage=stage,
            )
        if self.dry_run:
            print("  [dry-run] plugin remove {}".format(plugin_id))
        else:
            run_json(
                ("codex", "plugin", "remove", plugin_id, "--json"),
                stage=stage,
            )
        self.completed.append("removed {}".format(plugin_id))

    def _remove_marketplace(self) -> None:
        if self.dry_run:
            print("  [dry-run] marketplace remove {}".format(self.marketplace))
            return
        listing = run_json(
            ("codex", "plugin", "marketplace", "list", "--json"),
            stage="marketplace-list",
        )
        if not any(
            isinstance(item, dict) and item.get("name") == self.marketplace
            for item in listing.get("marketplaces", [])
        ):
            return
        run_json(
            ("codex", "plugin", "marketplace", "remove", self.marketplace, "--json"),
            stage="marketplace-remove",
        )
        self.completed.append("removed marketplace")

    def reset(self, *, include_template: bool) -> None:
        self._require_cli()
        print("Resetting Codex:")
        for plugin in self._plugins():
            self._remove_plugin(plugin, stage="reset")
        self._remove_marketplace()
        if include_template:
            CodexGuidanceDeployment(
                self.repo_root / "templates" / "AGENTS.md",
                self.codex_home,
                self.version,
                enabled=False,
                dry_run=self.dry_run,
                force=self.force,
            ).uninstall()
            self.completed.append("reset agents-md")

    def install(
        self,
        components: Sequence[str],
        *,
        reset: bool = False,
        include_template: bool = False,
    ) -> None:
        self._require_cli()
        desired = set(components)
        desired_plugins = sorted(desired & self.plugin_names)
        if reset:
            self.reset(include_template=include_template)

        self._deploy_plugins(desired_plugins)
        self.completed.extend("installed {}".format(name) for name in desired_plugins)

        # Add canonical plugins first. Only after they succeed is it safe to
        # remove omitted components and declared aliases.
        for plugin in self._plugins():
            name = str(plugin["name"])
            canonical = self.aliases.get(name, name)
            if canonical not in desired_plugins or name in self.aliases:
                self._remove_plugin(plugin, stage="desired-state-remove")

        CodexGuidanceDeployment(
            self.repo_root / "templates" / "AGENTS.md",
            self.codex_home,
            self.version,
            enabled="agents-md" in desired,
            dry_run=self.dry_run,
            force=self.force,
        ).deploy()
        self.completed.append(
            "installed agents-md" if "agents-md" in desired else "removed agents-md"
        )
        if not self.dry_run:
            self.verify(desired)

    def verify(self, desired: Set[str]) -> None:
        actual_plugins = {
            str(plugin["name"])
            for plugin in self._plugins()
            if str(plugin["name"]) in self.plugin_names
        }
        expected_plugins = desired & self.plugin_names
        guidance = (self.codex_home / GUIDANCE_MANIFEST).is_file()
        if actual_plugins != expected_plugins or guidance != ("agents-md" in desired):
            raise InstallerError(
                "Codex post-install state does not match the requested components",
                host="codex",
                stage="verify",
            )

    def uninstall(self) -> None:
        self._require_cli()
        for plugin in self._plugins():
            self._remove_plugin(plugin, stage="uninstall")
        CodexGuidanceDeployment(
            self.repo_root / "templates" / "AGENTS.md",
            self.codex_home,
            self.version,
            enabled=False,
            dry_run=self.dry_run,
            force=self.force,
        ).uninstall()
        self.completed.append("removed agents-md")
        if not self.dry_run and self.current_components():
            raise InstallerError(
                "Codex uninstall left managed components behind",
                host="codex",
                stage="verify",
            )
