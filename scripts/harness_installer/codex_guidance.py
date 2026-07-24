"""Managed-block deployment for the global Codex AGENTS.md template."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .errors import DriftError, StateError
from .filesystem import FileTransaction, InstallerLock, load_json


BEGIN = b"<!-- hukuhaka-harness:begin -->"
END = b"<!-- hukuhaka-harness:end -->"
MANIFEST_NAME = ".hukuhaka-guidance-manifest.json"
SCHEMA_VERSION = 1


def _hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _block(template: bytes) -> bytes:
    return BEGIN + b"\n" + template.rstrip(b"\r\n") + b"\n" + END


def _bounds(content: bytes) -> Optional[Tuple[int, int]]:
    begin_count = content.count(BEGIN)
    end_count = content.count(END)
    if begin_count == 0 and end_count == 0:
        return None
    if begin_count != 1 or end_count != 1:
        raise StateError(
            "AGENTS.md contains duplicate or incomplete hukuhaka markers",
            host="codex",
            stage="guidance",
            operation="parse-managed-block",
        )
    start = content.index(BEGIN)
    end = content.index(END) + len(END)
    if start >= end or content.find(END) < start:
        raise StateError(
            "AGENTS.md managed markers are out of order",
            host="codex",
            stage="guidance",
            operation="parse-managed-block",
        )
    return start, end


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
        self.manifest_path = codex_home / MANIFEST_NAME

    def is_installed(self) -> bool:
        return self.manifest_path.is_file()

    def _read_target(self) -> bytes:
        if not self.target.exists() and not self.target.is_symlink():
            return b""
        if self.target.is_symlink() or not self.target.is_file():
            raise StateError(
                "Codex AGENTS.md must be a regular file",
                host="codex",
                stage="guidance",
                operation="read-target",
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
                operation="read-target",
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
                operation="read-manifest",
                path=str(self.manifest_path),
            )
        if (
            data["schemaVersion"] != SCHEMA_VERSION
            or data["component"] != "agents-md"
            or data["target"] != "AGENTS.md"
            or data["prefix"] not in ("", "\n", "\n\n")
            or data["suffix"] not in ("", "\n")
        ):
            raise StateError(
                "unsupported Codex guidance manifest",
                host="codex",
                stage="guidance",
                operation="read-manifest",
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
                operation="validate-state",
                path=str(self.target),
            )
        if manifest is not None and bounds is None:
            raise DriftError(
                "Codex guidance manifest exists but its managed block is missing",
                host="codex",
                stage="guidance",
                operation="validate-state",
                path=str(self.target),
            )
        if bounds is not None and manifest is not None:
            start, end = bounds
            if _hash(content[start:end]) != manifest["managedHash"] and not self.force:
                raise DriftError(
                    "managed AGENTS.md block changed; use --force to replace it",
                    host="codex",
                    stage="guidance",
                    operation="validate-drift",
                    path=str(self.target),
                )

    def _warn_override(self) -> None:
        if self.override.exists():
            print(
                "Warning: {} shadows global AGENTS.md; managed guidance is installed but inactive.".format(
                    self.override
                ),
                file=sys.stderr,
            )

    def deploy(self) -> None:
        if not self.enabled:
            self.uninstall()
            return
        template = self.source.read_bytes()
        block = _block(template)
        content = self._read_target()
        bounds = _bounds(content)
        manifest = self._manifest()
        self._validate_current(content, bounds, manifest)

        if bounds is None:
            if not content:
                prefix = b""
            elif content.endswith(b"\n"):
                prefix = b"\n"
            else:
                prefix = b"\n\n"
            suffix = b"\n"
            merged = content + prefix + block + suffix
        else:
            start, end = bounds
            prefix = str(manifest["prefix"]).encode("utf-8")
            suffix = str(manifest["suffix"]).encode("utf-8")
            merged = content[:start] + block + content[end:]

        next_manifest = {
            "schemaVersion": SCHEMA_VERSION,
            "component": "agents-md",
            "version": self.version,
            "target": "AGENTS.md",
            "managedHash": _hash(block),
            "prefix": prefix.decode("utf-8"),
            "suffix": suffix.decode("utf-8"),
        }
        self._warn_override()
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
        prefix = manifest["prefix"].encode("utf-8")
        suffix = manifest["suffix"].encode("utf-8")
        if content[max(0, start - len(prefix)):start] != prefix or content[end:end + len(suffix)] != suffix:
            if not self.force:
                raise DriftError(
                    "text surrounding the managed AGENTS.md block changed; use --force to remove it",
                    host="codex",
                    stage="guidance",
                    operation="validate-boundary",
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
