"""Codex user-directory resolution shared by installer surfaces."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping, Optional


def resolve_codex_home(
    environ: Optional[Mapping[str, str]] = None,
    *,
    fallback_home: Optional[Path] = None,
) -> Path:
    values = os.environ if environ is None else environ
    configured = values.get("CODEX_HOME", "").strip()
    if configured:
        return Path(configured).expanduser()
    home = Path.home() if fallback_home is None else fallback_home
    return home / ".codex"
