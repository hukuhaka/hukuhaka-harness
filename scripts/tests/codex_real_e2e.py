#!/usr/bin/env python3
"""Real Codex CLI clean-room installer lifecycle.

The container supplies a pinned, unauthenticated Codex CLI. Every scenario gets
its own HOME and CODEX_HOME, so the test never reads or writes host Codex state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Iterable, Mapping, Optional, Sequence


SCOUT_BEGIN = "<!-- hukuhaka-evidence-scout:begin -->"
SCOUT_END = "<!-- hukuhaka-evidence-scout:end -->"


class E2EFailure(RuntimeError):
    pass


def run(
    command: Sequence[str],
    *,
    cwd: Path,
    environment: Mapping[str, str],
    expect_success: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=str(cwd),
        env=dict(environment),
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )
    if expect_success and result.returncode != 0:
        raise E2EFailure(
            "command failed ({}): {}\n{}\n{}".format(
                result.returncode,
                " ".join(command),
                result.stdout,
                result.stderr,
            )
        )
    if not expect_success and result.returncode == 0:
        raise E2EFailure("command unexpectedly succeeded: {}".format(" ".join(command)))
    return result


def environment(root: Path, *, path_prefix: Optional[Path] = None) -> Dict[str, str]:
    home = root / "home"
    codex_home = root / "codex-home"
    home.mkdir(parents=True, exist_ok=True)
    codex_home.mkdir(parents=True, exist_ok=True)
    values = os.environ.copy()
    values.update({"HOME": str(home), "CODEX_HOME": str(codex_home)})
    if path_prefix is not None:
        values["PATH"] = "{}{}{}".format(path_prefix, os.pathsep, values["PATH"])
    return values


def install_command(
    source: Path,
    version: str,
    action: str,
    *selection: str,
) -> Sequence[str]:
    return (
        "/bin/bash",
        str(source / "scripts" / "install.sh"),
        "--source-dir",
        str(source),
        "--version",
        version,
        "codex",
        action,
    ) + selection


def install(
    source: Path,
    version: str,
    root: Path,
    *,
    components: Optional[Sequence[str]] = None,
    action: str = "install",
    expect_success: bool = True,
    path_prefix: Optional[Path] = None,
) -> subprocess.CompletedProcess[str]:
    if action == "uninstall":
        selection = ("--yes",)
    elif components is None:
        selection = ("--recommended", "--yes")
    else:
        selection = ("--components", ",".join(components), "--yes")
    return run(
        install_command(source, version, action, *selection),
        cwd=source,
        environment=environment(root, path_prefix=path_prefix),
        expect_success=expect_success,
    )


def codex_home(root: Path) -> Path:
    return root / "codex-home"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(paths: Iterable[Path]) -> Dict[str, Optional[bytes]]:
    return {
        str(path): path.read_bytes() if path.is_file() else None
        for path in paths
    }


def doctor(root: Path, source: Path) -> None:
    result = subprocess.run(
        ("codex", "doctor", "--json"),
        cwd=str(source),
        env=environment(root),
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )
    try:
        report = json.loads(result.stdout)
        status = report["checks"]["config.load"]["status"]
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise E2EFailure("codex doctor returned an invalid report: {}".format(result.stdout)) from exc
    if status != "ok":
        raise E2EFailure("codex doctor config.load is {!r}".format(status))


def plugin_names(root: Path, source: Path) -> set[str]:
    result = run(
        ("codex", "plugin", "list", "--json"),
        cwd=source,
        environment=environment(root),
    )
    payload = json.loads(result.stdout)
    installed = payload.get("installed", [])
    return {
        str(item["name"])
        for item in installed
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }


def expected_plugins(source: Path) -> set[str]:
    catalog = json.loads((source / "components.json").read_text(encoding="utf-8"))
    return {
        str(item["name"])
        for item in catalog["components"]
        if item.get("kind") == "plugin"
        and "codex" in item.get("hosts", {})
        and item.get("default") is True
    }


def validate_install(source: Path, version: str, root: Path, *, plugins: bool) -> None:
    home = codex_home(root)
    agent = home / "agents" / "evidence-scout.toml"
    routing = home / "AGENTS.md"
    manifest_path = home / ".hukuhaka-evidence-scout-manifest.json"
    config = home / "config.toml"
    for path in (agent, routing, manifest_path, config):
        if not path.is_file():
            raise E2EFailure("missing installed artifact: {}".format(path))
    if agent.read_bytes() != (source / "agents" / "evidence-scout.toml").read_bytes():
        raise E2EFailure("installed evidence-scout differs from source")
    routing_text = routing.read_text(encoding="utf-8")
    if routing_text.count(SCOUT_BEGIN) != 1 or routing_text.count(SCOUT_END) != 1:
        raise E2EFailure("Evidence Scout routing markers are not unique")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schemaVersion") != 3 or manifest.get("version") != version:
        raise E2EFailure("Evidence Scout manifest is not the expected schema/version")
    if any("catalog" in key.lower() for key in manifest):
        raise E2EFailure("schema-v3 manifest still owns a model catalog")
    config_text = config.read_text(encoding="utf-8")
    for expected in ("multi_agent = true", "max_concurrent_threads_per_session = 4"):
        if expected not in config_text:
            raise E2EFailure("missing runtime setting: {}".format(expected))
    if "model_catalog_json" in config_text:
        raise E2EFailure("fresh install selected a model catalog")
    if (home / "models-luna-v2.json").exists():
        raise E2EFailure("fresh install created the obsolete Luna catalog")
    doctor(root, source)
    if plugins and plugin_names(root, source) != expected_plugins(source):
        raise E2EFailure("installed plugin set differs from recommended components")


def seed_legacy_v2(
    home: Path,
    *,
    catalog: bytes,
    pointer: Optional[str] = None,
    drift: bool = False,
) -> None:
    manifest_path = home / ".hukuhaka-evidence-scout-manifest.json"
    config_path = home / "config.toml"
    catalog_path = home / "models-luna-v2.json"
    catalog_path.write_bytes(catalog)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "schemaVersion": 2,
            "version": "1.1.10",
            "catalogSource": "models_cache.json",
            "catalogSourceHash": "legacy-source-hash",
            "catalogTarget": "models-luna-v2.json",
            "catalogHash": hashlib.sha256(catalog).hexdigest(),
        }
    )
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    target = pointer if pointer is not None else str(catalog_path)
    config_path.write_text(
        "model_catalog_json = {}\n{}".format(
            json.dumps(target),
            config_path.read_text(encoding="utf-8"),
        ),
        encoding="utf-8",
    )
    if drift:
        catalog_path.write_bytes(catalog + b" \n")


def bundled_catalog(root: Path, source: Path) -> bytes:
    result = run(
        ("codex", "debug", "models", "--bundled"),
        cwd=source,
        environment=environment(root),
    )
    payload = json.loads(result.stdout)
    if not isinstance(payload.get("models"), list) or not payload["models"]:
        raise E2EFailure("bundled Codex model catalog is empty")
    return result.stdout.encode("utf-8")


def scenario_fresh(source: Path, version: str, root: Path) -> None:
    install(source, version, root)
    validate_install(source, version, root, plugins=True)
    home = codex_home(root)
    managed = (
        home / "agents" / "evidence-scout.toml",
        home / "AGENTS.md",
        home / ".hukuhaka-evidence-scout-manifest.json",
        home / "config.toml",
    )
    before = snapshot(managed)
    install(source, version, root)
    if snapshot(managed) != before:
        raise E2EFailure("repeated install changed managed Evidence Scout files")
    install(source, version, root, action="uninstall")
    if plugin_names(root, source) & expected_plugins(source):
        raise E2EFailure("uninstall left managed plugins installed")
    if (home / "agents" / "evidence-scout.toml").exists():
        raise E2EFailure("uninstall left the Evidence Scout agent")
    if (home / ".hukuhaka-evidence-scout-manifest.json").exists():
        raise E2EFailure("uninstall left the Evidence Scout manifest")
    config_text = (home / "config.toml").read_text(encoding="utf-8")
    if "max_concurrent_threads_per_session = 4" not in config_text:
        raise E2EFailure("uninstall removed the retained runtime settings")
    install(source, version, root)
    validate_install(source, version, root, plugins=True)


def scenario_legacy(source: Path, version: str, root: Path, *, foreign: bool) -> None:
    install(source, version, root, components=("evidence-scout",))
    home = codex_home(root)
    catalog = bundled_catalog(root, source)
    foreign_pointer = str(home / "user-models.json") if foreign else None
    if foreign_pointer is not None:
        Path(foreign_pointer).write_bytes(catalog)
    seed_legacy_v2(home, catalog=catalog, pointer=foreign_pointer)
    install(source, version, root, components=("evidence-scout",))
    manifest = json.loads(
        (home / ".hukuhaka-evidence-scout-manifest.json").read_text(encoding="utf-8")
    )
    if manifest.get("schemaVersion") != 3 or any(
        "catalog" in key.lower() for key in manifest
    ):
        raise E2EFailure("legacy install did not migrate to schema v3")
    if (home / "models-luna-v2.json").exists():
        raise E2EFailure("legacy owned catalog was not removed")
    config = (home / "config.toml").read_text(encoding="utf-8")
    if foreign:
        if json.dumps(foreign_pointer) not in config:
            raise E2EFailure("foreign model catalog pointer was not preserved")
    elif "model_catalog_json" in config:
        raise E2EFailure("owned legacy model catalog pointer was not removed")
    doctor(root, source)


def scenario_drift(source: Path, version: str, root: Path) -> None:
    install(source, version, root, components=("evidence-scout",))
    home = codex_home(root)
    seed_legacy_v2(home, catalog=bundled_catalog(root, source), drift=True)
    observed = (
        home / "models-luna-v2.json",
        home / "config.toml",
        home / ".hukuhaka-evidence-scout-manifest.json",
        home / "agents" / "evidence-scout.toml",
        home / "AGENTS.md",
    )
    before = snapshot(observed)
    result = install(
        source,
        version,
        root,
        components=("evidence-scout",),
        expect_success=False,
    )
    if "managed evidence-scout files changed" not in (result.stdout + result.stderr):
        raise E2EFailure("drift failure did not explain the managed-file conflict")
    if snapshot(observed) != before:
        raise E2EFailure("failed drift migration changed the legacy installation")


def scenario_rollback(source: Path, version: str, root: Path) -> None:
    environment(root)
    home = codex_home(root)
    routing = home / "AGENTS.md"
    routing.write_text("# User guidance\n", encoding="utf-8")
    real_codex = shutil.which("codex")
    if real_codex is None:
        raise E2EFailure("codex CLI is unavailable")
    wrapper_dir = root / "fault-bin"
    wrapper_dir.mkdir(parents=True)
    wrapper = wrapper_dir / "codex"
    wrapper.write_text(
        "#!/bin/sh\n"
        "if [ \"${1:-}\" = doctor ]; then\n"
        "  printf '%s\\n' '{\"checks\":{\"config.load\":{\"status\":\"fail\",\"summary\":\"injected failure\"}}}'\n"
        "  exit 1\n"
        "fi\n"
        "exec "
        + shlex.quote(real_codex)
        + " \"$@\"\n",
        encoding="utf-8",
    )
    wrapper.chmod(0o755)
    result = install(
        source,
        version,
        root,
        components=("evidence-scout",),
        expect_success=False,
        path_prefix=wrapper_dir,
    )
    if "config validation failed" not in (result.stdout + result.stderr):
        raise E2EFailure("injected Doctor failure was not reported")
    if routing.read_text(encoding="utf-8") != "# User guidance\n":
        raise E2EFailure("rollback did not restore user AGENTS.md")
    for path in (
        home / "agents" / "evidence-scout.toml",
        home / ".hukuhaka-evidence-scout-manifest.json",
        home / "config.toml",
    ):
        if path.exists():
            raise E2EFailure("rollback left managed state: {}".format(path))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", required=True)
    parser.add_argument("--version")
    args = parser.parse_args()
    source = Path(args.source_dir).resolve()
    version = args.version or (source / "VERSION").read_text(encoding="utf-8").strip()
    cli_version = (source / "scripts" / "tests" / "codex-e2e-version.txt").read_text(
        encoding="utf-8"
    ).strip()
    actual = subprocess.run(
        ("codex", "--version"), text=True, capture_output=True, check=True
    ).stdout
    if cli_version not in actual:
        raise E2EFailure("Codex CLI version differs: {}".format(actual.strip()))

    with tempfile.TemporaryDirectory(prefix="hukuhaka-codex-real-e2e-") as temp_name:
        root = Path(temp_name)
        scenario_fresh(source, version, root / "fresh")
        scenario_legacy(source, version, root / "legacy-owned", foreign=False)
        scenario_legacy(source, version, root / "legacy-foreign", foreign=True)
        scenario_drift(source, version, root / "legacy-drift")
        scenario_rollback(source, version, root / "rollback")

    print("Codex real-CLI isolated E2E verified for v{} on CLI {}".format(version, cli_version))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
