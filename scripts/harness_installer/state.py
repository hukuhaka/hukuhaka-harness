"""Claude installation manifest model and migration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from . import MANIFEST_SCHEMA
from .errors import StateError
from .filesystem import load_json


@dataclass
class Manifest:
    version: str = ""
    components: List[str] = field(default_factory=list)
    files: List[str] = field(default_factory=list)
    hashes: Dict[str, str] = field(default_factory=dict)
    schema_version: int = MANIFEST_SCHEMA
    timestamp: str = ""

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
            schema_version=schema,
            timestamp=str(data.get("timestamp", "")),
        )

    def as_dict(self) -> Dict[str, Any]:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return {
            "schemaVersion": MANIFEST_SCHEMA,
            "version": self.version,
            "timestamp": timestamp,
            "components": sorted(set(self.components)),
            "files": sorted(set(self.files)),
            "hashes": dict(sorted(self.hashes.items())),
        }

    @property
    def exists(self) -> bool:
        return bool(self.version or self.components or self.files)
