"""Safe global Codex config.toml editor."""

from __future__ import annotations

import difflib
import json
import os
import re
import shutil
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Sequence, Tuple

from .common import InstallerError, StateError, atomic_write_bytes


Key = Tuple[str, ...]

RECOMMENDED_SETTINGS = {
    ("personality",): '"pragmatic"',
    ("model_reasoning_effort",): '"medium"',
    ("model_reasoning_summary",): '"concise"',
    ("model_verbosity",): '"low"',
    ("agents", "enabled"): "true",
    ("agents", "max_concurrent_threads_per_session"): "4",
    ("features", "multi_agent"): "true",
    (
        "tui",
        "status_line",
    ): '["model-with-reasoning", "context-remaining", "used-tokens", '
    '"five-hour-limit", "weekly-limit", "git-branch", "current-dir"]',
    ("tui", "notifications"): '["agent-turn-complete", "approval-requested"]',
    ("tui", "notification_condition"): '"unfocused"',
    ("features", "prevent_idle_sleep"): "true",
}  # type: Dict[Key, str]

# Installing the named evidence scout must make that component runnable without
# also changing the user's primary model or the defaults for unrelated agents.
EVIDENCE_SCOUT_SETTINGS = {
    ("features", "multi_agent"): "true",
    ("agents", "enabled"): "true",
    ("agents", "max_concurrent_threads_per_session"): "4",
}  # type: Dict[Key, str]

# The evidence-scout installer also manages this dynamic top-level key. Its
# value depends on CODEX_HOME, so it cannot live in RECOMMENDED_SETTINGS.
EVIDENCE_SCOUT_DYNAMIC_KEYS = {("model_catalog_json",)}


def _managed_keys() -> set[Key]:
    return set(RECOMMENDED_SETTINGS) | EVIDENCE_SCOUT_DYNAMIC_KEYS

_SECTION_RE = re.compile(r"^\s*\[([A-Za-z0-9_.-]+)\]\s*(?:#.*)?$")
_ASSIGNMENT_RE = re.compile(
    r"^(?P<indent>\s*)(?P<key>[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*)\s*="
)


@dataclass(frozen=True)
class ConfigPlan:
    path: Path
    original: bytes
    proposed: bytes
    existed: bool
    mode: int

    @property
    def changed(self) -> bool:
        return self.original != self.proposed

    def diff(self) -> str:
        before = self.original.decode("utf-8").splitlines(keepends=True)
        after = self.proposed.decode("utf-8").splitlines(keepends=True)
        return "".join(
            difflib.unified_diff(
                before,
                after,
                fromfile=str(self.path),
                tofile=str(self.path) + " (proposed)",
            )
        )


@dataclass(frozen=True)
class _Assignment:
    path: Key
    start: int
    end: int
    indent: str
    key_text: str
    value: str


def _balance(value: str) -> int:
    """Return unmatched []/{} depth while ignoring strings and comments."""
    depth = 0
    quote = ""
    escaped = False
    for character in value:
        if escaped:
            escaped = False
            continue
        if quote:
            if character == "\\" and quote == '"':
                escaped = True
            elif character == quote:
                quote = ""
            continue
        if character in ('"', "'"):
            quote = character
        elif character == "#":
            break
        elif character in "[{":
            depth += 1
        elif character in "]}":
            depth -= 1
    return depth


def _comment_offset(line: str) -> int:
    quote = ""
    escaped = False
    for index, character in enumerate(line):
        if escaped:
            escaped = False
            continue
        if quote:
            if character == "\\" and quote == '"':
                escaped = True
            elif character == quote:
                quote = ""
            continue
        if character in ('"', "'"):
            quote = character
        elif character == "#":
            return index
    return -1


def _trailing_comment(line: str) -> str:
    offset = _comment_offset(line)
    return line[offset:].rstrip("\r\n") if offset >= 0 else ""


def _without_comment(line: str) -> str:
    offset = _comment_offset(line)
    return line[:offset] if offset >= 0 else line


def _assignment_value(lines: Sequence[str], start: int) -> Tuple[int, str]:
    first = lines[start].split("=", 1)[1]
    values = [_without_comment(first)]
    depth = _balance(first)
    end = start + 1
    while depth > 0 and end < len(lines):
        values.append(_without_comment(lines[end]))
        depth += _balance(lines[end])
        end += 1
    if depth != 0:
        raise StateError(
            "unterminated TOML value",
            host="codex",
            stage="configure",
            operation="parse-config",
        )
    return end, "".join(values).strip()


def _parse_assignments(text: str) -> Tuple[List[str], List[_Assignment], Dict[Key, int]]:
    lines = text.splitlines(keepends=True)
    assignments = []  # type: List[_Assignment]
    sections = {}  # type: Dict[Key, int]
    section = ()  # type: Key
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        if stripped.startswith("[["):
            section = ()
            index += 1
            continue
        section_match = _SECTION_RE.match(lines[index])
        if section_match:
            section = tuple(section_match.group(1).split("."))
            sections.setdefault(section, index)
            index += 1
            continue
        match = _ASSIGNMENT_RE.match(lines[index])
        if not match:
            index += 1
            continue
        key_parts = tuple(match.group("key").split("."))
        path = section + key_parts
        end, value = _assignment_value(lines, index)
        assignments.append(
            _Assignment(
                path=path,
                start=index,
                end=end,
                indent=match.group("indent"),
                key_text=match.group("key"),
                value=value,
            )
        )
        index = end
    return lines, assignments, sections


def current_values(text: str) -> Dict[Key, str]:
    _, assignments, _ = _parse_assignments(text)
    found = {}  # type: Dict[Key, str]
    for assignment in assignments:
        if assignment.path in _managed_keys():
            if assignment.path in found:
                raise StateError(
                    "duplicate managed Codex config key: {}".format(
                        ".".join(assignment.path)
                    ),
                    host="codex",
                    stage="configure",
                    operation="parse-config",
                )
            found[assignment.path] = assignment.value
        elif any(
            key[: len(assignment.path)] == assignment.path
            for key in _managed_keys()
        ):
            raise StateError(
                "managed Codex config table uses an inline value: {}".format(
                    ".".join(assignment.path)
                ),
                host="codex",
                stage="configure",
                operation="parse-config",
            )
    return found


def _section_end(lines: Sequence[str], start: int) -> int:
    for index in range(start + 1, len(lines)):
        stripped = lines[index].strip()
        if stripped.startswith("["):
            return index
    return len(lines)


def update_config(text: str, settings: Mapping[Key, str]) -> str:
    unknown = [key for key in settings if key not in _managed_keys()]
    if unknown:
        raise StateError(
            "unsupported managed Codex config key: {}".format(".".join(unknown[0])),
            host="codex",
            stage="configure",
            operation="update-config",
        )

    lines, assignments, sections = _parse_assignments(text)
    current_values(text)  # Validate duplicate and inline managed shapes.
    replacements = {}  # type: Dict[int, Tuple[int, str]]
    present = set()  # type: set[Key]
    for assignment in assignments:
        if assignment.path not in settings:
            continue
        present.add(assignment.path)
        original_lines = lines[assignment.start:assignment.end]
        comments = [
            comment
            for comment in (_trailing_comment(line) for line in original_lines)
            if comment
        ]
        newline = "\r\n" if original_lines[0].endswith("\r\n") else "\n"
        prefix = ""
        suffix = ""
        if len(original_lines) == 1 and comments:
            suffix = " " + comments[0]
        elif comments:
            prefix = "".join(
                "{}{}{}".format(assignment.indent, comment, newline)
                for comment in comments
            )
        replacements[assignment.start] = (
            assignment.end,
            "{}{}{} = {}{}{}".format(
                prefix,
                assignment.indent,
                assignment.key_text,
                settings[assignment.path],
                suffix,
                newline,
            ),
        )

    rewritten = []  # type: List[str]
    index = 0
    while index < len(lines):
        replacement = replacements.get(index)
        if replacement is None:
            rewritten.append(lines[index])
            index += 1
        else:
            end, content = replacement
            rewritten.append(content)
            index = end

    missing = [key for key in settings if key not in present]
    if not missing:
        return "".join(rewritten)

    # Re-parse after replacements so insertion indices match the rewritten text.
    lines, _, sections = _parse_assignments("".join(rewritten))
    dotted_tables = {
        assignment.path[:-1]
        for assignment in assignments
        if len(assignment.path) > 1
        and assignment.key_text == ".".join(assignment.path)
    }
    top_level = [
        key
        for key in missing
        if len(key) == 1 or key[:-1] in dotted_tables
    ]
    tables = list(
        dict.fromkeys(
            key[:-1]
            for key in missing
            if len(key) > 1 and key[:-1] not in dotted_tables
        )
    )

    if top_level:
        first_section = next(
            (index for index, line in enumerate(lines) if line.strip().startswith("[")),
            len(lines),
        )
        additions = [
            "{} = {}\n".format(".".join(key), settings[key]) for key in top_level
        ]
        if first_section and lines[first_section - 1].strip():
            additions.append("\n")
        lines[first_section:first_section] = additions

    for table in tables:
        # Earlier insertions can move sections, so find the table each time.
        _, _, current_sections = _parse_assignments("".join(lines))
        keys = [key for key in missing if key[:-1] == table]
        if table in current_sections:
            insertion = _section_end(lines, current_sections[table])
            additions = ["{} = {}\n".format(key[-1], settings[key]) for key in keys]
            if insertion and lines[insertion - 1].strip():
                additions.append("\n")
            lines[insertion:insertion] = additions
        else:
            if lines and lines[-1].strip():
                lines.append("\n")
            lines.append("[{}]\n".format(".".join(table)))
            lines.extend("{} = {}\n".format(key[-1], settings[key]) for key in keys)

    return "".join(lines)


def _prompt_choice(label: str, current: str, allowed: Sequence[str]) -> str:
    default = current if current in allowed else allowed[0]
    while True:
        value = input("{} [{}]: ".format(label, default)).strip() or default
        if value in allowed:
            return value
        print("Choose one of: {}".format(", ".join(allowed)))


def _prompt_bool(label: str, current: bool) -> bool:
    prompt = "Y/n" if current else "y/N"
    while True:
        value = input("{} [{}]: ".format(label, prompt)).strip().lower()
        if not value:
            return current
        if value in ("y", "yes"):
            return True
        if value in ("n", "no"):
            return False


def _decode_string(value: str, fallback: str) -> str:
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError):
        return fallback
    return decoded if isinstance(decoded, str) else fallback


def prompt_settings(current: Mapping[Key, str]) -> Dict[Key, str]:
    """Ask only about the supported global defaults."""
    recommended = RECOMMENDED_SETTINGS
    personality = _prompt_choice(
        "Personality",
        _decode_string(current.get(("personality",), ""), "pragmatic"),
        ("pragmatic", "friendly", "none"),
    )
    effort = _prompt_choice(
        "Reasoning effort",
        _decode_string(current.get(("model_reasoning_effort",), ""), "medium"),
        ("medium", "low", "high", "xhigh", "minimal"),
    )
    summary = _prompt_choice(
        "Reasoning summary",
        _decode_string(current.get(("model_reasoning_summary",), ""), "concise"),
        ("concise", "auto", "detailed", "none"),
    )
    verbosity = _prompt_choice(
        "Response verbosity",
        _decode_string(current.get(("model_verbosity",), ""), "low"),
        ("low", "medium", "high"),
    )
    agents_enabled = _prompt_bool(
        "Enable multi-agent",
        current.get(("agents", "enabled"), "true").lower() != "false",
    )
    raw_threads = current.get(("agents", "max_concurrent_threads_per_session"), "4")
    while True:
        entered = input("Concurrent agents [{}]: ".format(raw_threads)).strip() or raw_threads
        if entered.isdigit() and int(entered) > 0:
            threads = entered
            break
        print("Enter a positive integer.")
    notifications = _prompt_bool(
        "Enable TUI notifications",
        current.get(("tui", "notifications"), "true").lower() != "false",
    )
    idle_sleep = _prompt_bool(
        "Prevent idle sleep during a turn",
        current.get(("features", "prevent_idle_sleep"), "true").lower() != "false",
    )
    return {
        ("personality",): json.dumps(personality),
        ("model_reasoning_effort",): json.dumps(effort),
        ("model_reasoning_summary",): json.dumps(summary),
        ("model_verbosity",): json.dumps(verbosity),
        ("agents", "enabled"): str(agents_enabled).lower(),
        ("agents", "max_concurrent_threads_per_session"): threads,
        ("tui", "status_line"): current.get(
            ("tui", "status_line"), recommended[("tui", "status_line")]
        ),
        ("tui", "notifications"): (
            recommended[("tui", "notifications")] if notifications else "false"
        ),
        ("tui", "notification_condition"): current.get(
            ("tui", "notification_condition"),
            recommended[("tui", "notification_condition")],
        ),
        ("features", "prevent_idle_sleep"): str(idle_sleep).lower(),
    }


class CodexConfigEditor:
    def __init__(self, codex_home: Path, *, dry_run: bool = False) -> None:
        self.codex_home = codex_home.expanduser()
        self.path = self.codex_home / "config.toml"
        self.backup = self.codex_home / "config.toml.hukuhaka-backup"
        self.dry_run = dry_run

    def _read(self) -> Tuple[bytes, bool, int]:
        if not self.path.exists() and not self.path.is_symlink():
            return b"", False, 0o600
        if self.path.is_symlink() or not self.path.is_file():
            raise StateError(
                "Codex config.toml must be a regular file",
                host="codex",
                stage="configure",
                path=str(self.path),
            )
        content = self.path.read_bytes()
        try:
            content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise StateError(
                "Codex config.toml must be UTF-8",
                host="codex",
                stage="configure",
                path=str(self.path),
            ) from exc
        return content, True, stat.S_IMODE(self.path.stat().st_mode)

    def inspect(self) -> Dict[Key, str]:
        original, _, _ = self._read()
        return current_values(original.decode("utf-8"))

    def plan(self, settings: Mapping[Key, str]) -> ConfigPlan:
        original, existed, mode = self._read()
        proposed = update_config(original.decode("utf-8"), settings).encode("utf-8")
        return ConfigPlan(self.path, original, proposed, existed, mode)

    def _doctor(self) -> None:
        command = shutil.which("codex")
        if command is None:
            raise InstallerError(
                "codex CLI is required to validate global config",
                host="codex",
                stage="configure",
                operation="doctor",
            )
        environment = os.environ.copy()
        environment["CODEX_HOME"] = str(self.codex_home)
        result = subprocess.run(
            (command, "doctor", "--json"),
            text=True,
            capture_output=True,
            env=environment,
            check=False,
            timeout=30,
        )
        try:
            payload = json.loads(result.stdout)
            check = payload["checks"]["config.load"]
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            detail = (result.stderr or result.stdout).strip()
            raise InstallerError(
                "codex doctor returned an unexpected JSON report{}".format(
                    ": " + detail if detail else ""
                ),
                host="codex",
                stage="configure",
                operation="doctor",
            ) from exc
        if check.get("status") != "ok":
            raise InstallerError(
                "codex config validation failed: {}".format(
                    check.get("summary", "config.load was not ok")
                ),
                host="codex",
                stage="configure",
                operation="doctor",
            )

    def apply(self, plan: ConfigPlan, *, show_diff: bool = True) -> bool:
        if not plan.changed:
            print("Codex config: already matches the selected defaults.")
            return False
        if show_diff:
            print(plan.diff(), end="")
        if self.dry_run:
            print("Codex config dry run complete. No files were modified.")
            return False
        current, existed, _ = self._read()
        if current != plan.original or existed != plan.existed:
            raise StateError(
                "Codex config changed after the diff was prepared; review it again",
                host="codex",
                stage="configure",
                operation="verify-precondition",
                path=str(self.path),
            )
        self.codex_home.mkdir(parents=True, exist_ok=True)
        if plan.existed:
            atomic_write_bytes(self.backup, plan.original, plan.mode)
        try:
            atomic_write_bytes(self.path, plan.proposed, plan.mode)
            self._doctor()
        except Exception as exc:
            try:
                if plan.existed:
                    atomic_write_bytes(self.path, plan.original, plan.mode)
                elif self.path.exists():
                    self.path.unlink()
            except OSError as rollback_error:
                raise StateError(
                    "Codex config validation failed and the original could not be restored",
                    host="codex",
                    stage="configure",
                    operation="rollback-config",
                    path=str(self.path),
                ) from rollback_error
            if isinstance(exc, InstallerError):
                raise
            raise InstallerError(
                "cannot update global Codex config: {}".format(exc),
                host="codex",
                stage="configure",
                operation="write-config",
                path=str(self.path),
            ) from exc
        print("  [ok] global Codex config -> {}".format(self.path))
        return True

    def verify(self, plan: ConfigPlan) -> None:
        if self.dry_run:
            return
        current, existed, _ = self._read()
        if not existed:
            raise StateError(
                "Codex config.toml is missing after component installation",
                host="codex",
                stage="configure",
                operation="verify",
                path=str(self.path),
            )
        expected = current_values(plan.proposed.decode("utf-8"))
        actual = current_values(current.decode("utf-8"))
        mismatched = [
            key for key, value in expected.items() if actual.get(key) != value
        ]
        if mismatched:
            raise StateError(
                "managed Codex config changed during component installation: {}".format(
                    ".".join(mismatched[0])
                ),
                host="codex",
                stage="configure",
                operation="verify",
                path=str(self.path),
            )
        self._doctor()
