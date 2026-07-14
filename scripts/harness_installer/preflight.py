"""Structured dependency scanner for selected harness components."""

from __future__ import annotations

import argparse
import ast
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple


ALWAYS_STDLIB = {"__future__", "__main__"}
FALLBACK_STDLIB = {
    "abc", "argparse", "ast", "asyncio", "base64", "binascii", "bisect",
    "builtins", "calendar", "collections", "concurrent", "configparser",
    "contextlib", "copy", "csv", "ctypes", "dataclasses", "datetime", "decimal",
    "difflib", "enum", "errno", "fcntl", "fnmatch", "functools", "gc",
    "getopt", "getpass", "glob", "gzip", "hashlib", "heapq", "html", "http",
    "importlib", "inspect", "io", "ipaddress", "itertools", "json", "logging",
    "math", "mimetypes", "multiprocessing", "operator", "os", "pathlib",
    "pickle", "platform", "pprint", "queue", "random", "re", "select",
    "selectors", "shlex", "shutil", "signal", "socket", "sqlite3", "ssl",
    "stat", "string", "struct", "subprocess", "sys", "tarfile", "tempfile",
    "termios", "textwrap", "threading", "time", "traceback", "tty", "typing",
    "unicodedata", "unittest", "urllib", "uuid", "warnings", "weakref", "xml",
    "zipfile", "zlib",
} | ALWAYS_STDLIB


def stdlib_modules() -> Set[str]:
    names = getattr(sys, "stdlib_module_names", None)
    return (set(names) | ALWAYS_STDLIB) if names is not None else FALLBACK_STDLIB


def python_imports(path: Path) -> Set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError):
        return set()
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module.split(".")[0])
    return modules


def shebang(path: Path) -> str:
    try:
        first = path.open("rb").readline()
    except OSError:
        return ""
    if not first.startswith(b"#!"):
        return ""
    return first[2:].decode("utf-8", "replace").strip()


class Requirements:
    def __init__(self) -> None:
        self.values = {}  # type: Dict[Tuple[str, str], Dict[str, Any]]

    def add(self, name: str, kind: str, required: bool, needed_by: str) -> None:
        key = (name, kind)
        if key not in self.values:
            self.values[key] = {
                "name": name,
                "kind": kind,
                "required": required,
                "needed_by": [needed_by],
            }
            return
        entry = self.values[key]
        entry["required"] = bool(entry["required"] or required)
        if needed_by not in entry["needed_by"]:
            entry["needed_by"].append(needed_by)


def component_path(root: Path, name: str) -> Optional[Path]:
    for candidate in (root / "marketplace" / name, root / "skills" / name):
        if candidate.is_dir():
            return candidate
    return None


def collect_requirements(root: Path, host: str, components: Sequence[str]) -> Requirements:
    requirements = Requirements()
    requirements.add("python3", "system", True, "installer runtime")
    requirements.add("bash", "system", True, "host adapters")
    if host in ("codex", "both"):
        requirements.add("codex", "manual", True, "Codex plugin lifecycle")
    requirements.add("git", "system", False, "version-pinned marketplace verification")
    standard = stdlib_modules()
    for name in components:
        path = component_path(root, name)
        if path is None:
            continue
        local_modules = {candidate.stem for candidate in path.rglob("*.py")}
        for candidate in path.rglob("*"):
            if not candidate.is_file():
                continue
            if candidate.suffix == ".py":
                requirements.add("python3", "system", True, name)
                for module in sorted(python_imports(candidate)):
                    if module not in standard and module not in local_modules:
                        requirements.add(module, "python", False, name)
            elif candidate.suffix == ".sh":
                shell = "bash" if "bash" in shebang(candidate) else "sh"
                requirements.add(shell, "system", True, name)
    return requirements


def check_command(name: str) -> Tuple[bool, Optional[str], Optional[str]]:
    path = shutil.which(name)
    if not path:
        return False, None, None
    version = None
    for flag in ("--version", "-V", "-v"):
        try:
            result = subprocess.run(
                (name, flag), capture_output=True, timeout=2, text=True, check=False
            )
        except (OSError, subprocess.SubprocessError):
            continue
        output = (result.stdout or result.stderr).strip().splitlines()
        if output:
            version = output[0][:120]
            break
    return True, path, version


def check_python_module(name: str) -> bool:
    try:
        result = subprocess.run(
            (sys.executable, "-c", "import {}".format(name)),
            capture_output=True,
            timeout=4,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def build_report(requirements: Requirements) -> Dict[str, Any]:
    results = []
    for (name, kind), info in requirements.values.items():
        entry = dict(info)
        if kind in ("system", "manual"):
            found, path, version = check_command(name)
            entry["found"] = found
            if found:
                entry["path"] = path
                if version:
                    entry["version"] = version
        else:
            entry["found"] = check_python_module(name)
        results.append(entry)

    def order(item: Dict[str, Any]) -> Tuple[int, str]:
        if item["required"] and not item["found"]:
            return (0, str(item["name"]))
        if not item["required"] and not item["found"]:
            return (1, str(item["name"]))
        return (2, str(item["name"]))

    results.sort(key=order)
    missing_required = sum(1 for item in results if item["required"] and not item["found"])
    missing_optional = sum(1 for item in results if not item["required"] and not item["found"])
    return {
        "summary": {
            "missing_required": missing_required,
            "missing_optional": missing_optional,
            "ok": sum(1 for item in results if item["found"]),
        },
        "requirements": results,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check hukuhaka-harness dependencies")
    parser.add_argument("--host", choices=("claude", "codex", "both"), required=True)
    parser.add_argument("--components", default="")
    parser.add_argument("--src-dir", type=Path, required=True)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.src_dir.resolve()
    if not root.is_dir():
        print("Error: --src-dir must point to an extracted source tree", file=sys.stderr)
        return 2
    requirements = collect_requirements(
        root, args.host, [item for item in args.components.split(",") if item]
    )
    report = build_report(requirements)
    print(json.dumps(report, indent=2))
    return 1 if report["summary"]["missing_required"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
