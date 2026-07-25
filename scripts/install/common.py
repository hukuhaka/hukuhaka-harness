"""Shared errors, state, and atomic filesystem primitives."""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import shutil
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

MANIFEST_SCHEMA = 2


class InstallerError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        host: Optional[str] = None,
        stage: Optional[str] = None,
        operation: Optional[str] = None,
        path: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.host = host
        self.stage = stage
        self.operation = operation
        self.path = path

    def render(self) -> str:
        context = []
        for name in ("host", "stage", "operation", "path"):
            value = getattr(self, name)
            if value:
                context.append("{}={}".format(name, value))
        return "installer{}: {}".format(
            " [{}]".format(" ".join(context)) if context else "",
            self,
        )


class StateError(InstallerError):
    pass


class DriftError(InstallerError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise StateError(
            "invalid JSON: {}".format(exc),
            operation="read-json",
            path=str(path),
        ) from exc


def atomic_write_bytes(path: Path, content: bytes, mode: Optional[int] = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".{}-".format(path.name), dir=str(path.parent))
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if mode is not None:
            os.chmod(str(temp), mode)
        os.replace(str(temp), str(path))
        directory_fd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temp.exists():
            temp.unlink()


def atomic_write_json(path: Path, data: Any) -> None:
    content = (json.dumps(data, indent=2, ensure_ascii=True) + "\n").encode("utf-8")
    atomic_write_bytes(path, content)


def remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(str(path))


class InstallerLock:
    def __init__(self, root: Path) -> None:
        self.path = root / ".hukuhaka-installer.lock"
        self.handle = None  # type: Optional[Any]

    def __enter__(self) -> "InstallerLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("a+")
        try:
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            self.handle.close()
            raise InstallerError(
                "another hukuhaka installer is already running",
                operation="acquire-lock",
                path=str(self.path),
            ) from exc
        self.handle.seek(0)
        self.handle.truncate()
        self.handle.write(str(os.getpid()))
        self.handle.flush()
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        if self.handle is not None:
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            self.handle.close()


class FileTransaction:
    """Snapshot-before-write transaction with crash recovery."""

    def __init__(self, state_root: Path) -> None:
        self.state_root = state_root
        self.transactions_root = state_root / ".hukuhaka-transactions"
        self.root = self.transactions_root / uuid.uuid4().hex
        self.backups = self.root / "backups"
        self.journal_path = self.root / "journal.json"
        self.entries = []  # type: List[Dict[str, Any]]
        self.seen = set()  # type: Set[str]
        self.committed = False

    @staticmethod
    def recover_pending(state_root: Path) -> int:
        transactions_root = state_root / ".hukuhaka-transactions"
        if not transactions_root.is_dir():
            return 0
        recovered = 0
        for root in sorted(transactions_root.iterdir()):
            journal_path = root / "journal.json"
            if not journal_path.is_file():
                shutil.rmtree(str(root), ignore_errors=True)
                continue
            journal = load_json(journal_path, {})
            if journal.get("state") == "committed":
                shutil.rmtree(str(root), ignore_errors=True)
                continue
            FileTransaction._restore_entries(root, journal.get("entries", []))
            shutil.rmtree(str(root), ignore_errors=True)
            recovered += 1
        return recovered

    @staticmethod
    def _restore_entries(root: Path, entries: List[Dict[str, Any]]) -> None:
        state_root = Path(os.path.abspath(str(root.parent.parent)))
        backup_root = Path(os.path.abspath(str(root / "backups")))
        validated = []
        for entry in reversed(entries):
            target = Path(os.path.abspath(str(entry["target"])))
            if target != state_root and state_root not in target.parents:
                raise StateError(
                    "transaction target escapes installer state root",
                    operation="recover-transaction",
                    path=str(target),
                )
            backup = None
            if entry["existed"]:
                backup = Path(os.path.abspath(str(root / str(entry["backup"]))))
                if backup != backup_root and backup_root not in backup.parents:
                    raise StateError(
                        "transaction backup escapes transaction root",
                        operation="recover-transaction",
                        path=str(backup),
                    )
                if not backup.exists() and not backup.is_symlink():
                    raise StateError(
                        "transaction backup is missing",
                        operation="recover-transaction",
                        path=str(backup),
                    )
            validated.append((target, backup))

        for target, backup in validated:
            remove_path(target)
            if backup is not None:
                target.parent.mkdir(parents=True, exist_ok=True)
                if backup.is_dir():
                    shutil.copytree(str(backup), str(target), symlinks=True)
                else:
                    shutil.copy2(str(backup), str(target), follow_symlinks=False)

    def __enter__(self) -> "FileTransaction":
        self.backups.mkdir(parents=True)
        self._write_journal("pending")
        return self

    def _write_journal(self, state: str) -> None:
        atomic_write_json(self.journal_path, {"state": state, "entries": self.entries})

    def snapshot(self, target: Path) -> None:
        key = str(target.absolute())
        if key in self.seen:
            return
        existed = target.exists() or target.is_symlink()
        backup_rel = "backups/{:06d}".format(len(self.entries))
        entry = {"target": key, "existed": existed, "backup": backup_rel}
        if existed:
            backup = self.root / backup_rel
            backup.parent.mkdir(parents=True, exist_ok=True)
            if target.is_dir() and not target.is_symlink():
                shutil.copytree(str(target), str(backup), symlinks=True)
            else:
                shutil.copy2(str(target), str(backup), follow_symlinks=False)
        self.entries.append(entry)
        self._write_journal("pending")
        self.seen.add(key)

    def write_bytes(self, target: Path, content: bytes, mode: Optional[int] = None) -> None:
        self.snapshot(target)
        atomic_write_bytes(target, content, mode)

    def write_json(self, target: Path, data: Any) -> None:
        self.snapshot(target)
        atomic_write_json(target, data)

    def copy_file(self, source: Path, target: Path) -> None:
        self.snapshot(target)
        mode = source.stat().st_mode & 0o777
        self.write_bytes(target, source.read_bytes(), mode)

    def remove(self, target: Path) -> bool:
        if not target.exists() and not target.is_symlink():
            return False
        self.snapshot(target)
        remove_path(target)
        return True

    def commit(self) -> None:
        self._write_journal("committed")
        self.committed = True

    def rollback(self) -> None:
        self._restore_entries(self.root, self.entries)

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        try:
            if exc_type is not None and not self.committed:
                self.rollback()
        finally:
            shutil.rmtree(str(self.root), ignore_errors=True)
            with contextlib.suppress(OSError):
                self.transactions_root.rmdir()


@dataclass
class Manifest:
    version: str = ""
    components: List[str] = field(default_factory=list)
    files: List[str] = field(default_factory=list)
    hashes: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "Manifest":
        if not path.exists():
            return cls()
        data = load_json(path, {})
        if not isinstance(data, dict):
            raise StateError("manifest root must be an object", operation="read-manifest", path=str(path))
        schema = data.get("schemaVersion", 1)
        if schema not in (1, MANIFEST_SCHEMA):
            raise StateError(
                "unsupported manifest schema {}".format(schema),
                operation="migrate-manifest",
                path=str(path),
            )
        components = data.get("components", [])
        files = data.get("files", [])
        hashes = data.get("hashes", {})
        if not isinstance(components, list) or not isinstance(files, list):
            raise StateError(
                "manifest components and files must be arrays",
                operation="read-manifest",
                path=str(path),
            )
        if not isinstance(hashes, dict):
            raise StateError(
                "manifest hashes must be an object",
                operation="read-manifest",
                path=str(path),
            )
        return cls(
            version=str(data.get("version", "")),
            components=sorted(str(item) for item in components if item),
            files=sorted(str(item) for item in files if item),
            hashes={str(key): str(value) for key, value in hashes.items()},
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "schemaVersion": MANIFEST_SCHEMA,
            "version": self.version,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "components": sorted(set(self.components)),
            "files": sorted(set(self.files)),
            "hashes": dict(sorted(self.hashes.items())),
        }
