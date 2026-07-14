"""Codex native marketplace deployment adapter."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .errors import InstallerError


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deploy Codex plugins")
    parser.add_argument("--components", default="")
    parser.add_argument("--marketplace-source", default="hukuhaka/hukuhaka-harness")
    parser.add_argument("--marketplace-name", default="hukuhaka-harness")
    parser.add_argument("--version", default="")
    parser.add_argument("--version-explicit", action="store_true")
    parser.add_argument("--local-source", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        CodexDeployment(
            [item for item in args.components.split(",") if item],
            args.marketplace_source,
            args.marketplace_name,
            args.version,
            version_explicit=args.version_explicit,
            local_source=args.local_source,
            dry_run=args.dry_run,
        ).deploy()
        return 0
    except InstallerError as exc:
        print(exc.render(), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
