"""Codex native marketplace install adapter."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from .common import (
    DriftError,
    FileTransaction,
    InstallerError,
    InstallerLock,
    StateError,
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

    def deploy(self) -> None:
        if not self.enabled:
            self.uninstall()
            return
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
        if self.override.exists():
            print(
                "Warning: {} shadows global AGENTS.md; managed guidance is inactive.".format(
                    self.override
                ),
                file=sys.stderr,
            )
        if self.dry_run:
            print("  [dry-run] merge agents-md into {}".format(self.target))
            return
        with InstallerLock(self.codex_home), FileTransaction(self.codex_home) as transaction:
            transaction.write_bytes(self.target, merged)
            transaction.write_json(self.manifest_path, next_manifest)
            transaction.commit()
        print("  [ok] agents-md -> {}".format(self.target))

    def uninstall(self) -> None:
        content = self._read_target()
        bounds = _bounds(content)
        manifest = self._manifest()
        if bounds is None and manifest is None:
            return
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
        merged = content[:start - len(prefix)] + content[end + len(suffix):]
        if self.dry_run:
            print("  [dry-run] remove agents-md from {}".format(self.target))
            return
        with InstallerLock(self.codex_home), FileTransaction(self.codex_home) as transaction:
            if merged:
                transaction.write_bytes(self.target, merged)
            else:
                transaction.remove(self.target)
            transaction.remove(self.manifest_path)
            transaction.commit()
        print("  [ok] removed agents-md from {}".format(self.target))


def run_json(command: Sequence[str], *, stage: str) -> Dict[str, Any]:
    try:
        result = subprocess.run(command, check=True, text=True, capture_output=True)
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


class CodexDeployment:
    def __init__(
        self,
        components: Sequence[str],
        source: str,
        marketplace_name: str,
        version: str,
        *,
        version_explicit: bool,
        local_source: bool,
        dry_run: bool,
    ) -> None:
        self.components = list(dict.fromkeys(item for item in components if item))
        self.source = source
        self.marketplace_name = marketplace_name
        self.version = version.lstrip("v")
        self.version_explicit = version_explicit
        self.local_source = local_source
        self.dry_run = dry_run

    def deploy(self) -> None:
        if not self.components:
            return
        if self.dry_run:
            print("Codex deploy:")
            print("  [dry-run] marketplace add {}".format(self.source))
            for component in self.components:
                print("  [dry-run] plugin add {}@{}".format(component, self.marketplace_name))
            return
        if shutil.which("codex") is None:
            raise InstallerError(
                "codex CLI is required for --host codex",
                host="codex",
                stage="preflight",
            )
        command = ["codex", "plugin", "marketplace", "add", self.source, "--json"]
        if self.version_explicit and not self.local_source:
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
                if isinstance(item, dict) and item.get("name") == self.marketplace_name
            ),
            None,
        )
        if info is None:
            raise InstallerError(
                "marketplace '{}' was not returned after add".format(self.marketplace_name),
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
                expected = Path(self.source).resolve(strict=True)
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
                        self.marketplace_name
                    ),
                    host="codex",
                    stage="marketplace-verify",
                )
        elif source_type == "local":
            raise InstallerError(
                "marketplace '{}' points at local source {}; remove or repoint it before using the public installer".format(
                    self.marketplace_name, source_value
                ),
                host="codex",
                stage="marketplace-verify",
            )

        if already_added and self.version_explicit and not self.local_source:
            root = Path(str(root_value))
            expected_ref = "v{}^{{commit}}".format(self.version)
            current = git_commit(root, "HEAD")
            expected = git_commit(root, expected_ref)
            if not current or not expected or current != expected:
                raise InstallerError(
                    "marketplace '{}' already exists at a different ref; remove or repoint it before installing v{}".format(
                        self.marketplace_name, self.version
                    ),
                    host="codex",
                    stage="version-pin-verify",
                    path=str(root),
                )
        if already_added and not self.local_source and not self.version_explicit:
            run_json(
                ("codex", "plugin", "marketplace", "upgrade", self.marketplace_name, "--json"),
                stage="marketplace-upgrade",
            )
        for component in self.components:
            run_json(
                ("codex", "plugin", "add", "{}@{}".format(component, self.marketplace_name), "--json"),
                stage="plugin-add",
            )
            print("  [ok] {}@{}".format(component, self.marketplace_name))
