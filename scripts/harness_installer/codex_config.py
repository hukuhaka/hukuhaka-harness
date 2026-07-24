"""Interactive, conservative updates for the user-level Codex config."""

from __future__ import annotations

import ast
import difflib
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, TextIO, Tuple

from .errors import InstallerError, StateError


ConfigKey = Tuple[Optional[str], str]


@dataclass(frozen=True)
class Assignment:
    section: Optional[str]
    key: str
    start: int
    end: int
    raw_value: str
    dotted: bool = False


class CodexConfigDocument:
    """Preserve unknown TOML while editing a small, explicit key set."""

    SECTION_RE = re.compile(r"^\s*\[([A-Za-z0-9_.-]+)\]\s*(?:#.*)?$")
    ANY_SECTION_RE = re.compile(r"^\s*\[\[?.*\]\]?\s*(?:#.*)?$")
    ASSIGNMENT_RE = re.compile(r"^\s*([A-Za-z0-9_.-]+)\s*=")
    MANAGED_SECTIONS = {"agents", "tui", "features"}

    def __init__(self, text: str) -> None:
        self.text = text
        self.lines = text.splitlines(keepends=True)
        self.assignments = {}  # type: Dict[ConfigKey, Assignment]
        self.section_ranges = {}  # type: Dict[str, Tuple[int, int]]
        self.dotted_sections = set()  # type: set[str]
        self._scan()

    @staticmethod
    def _value_complete(text: str) -> bool:
        state = None  # type: Optional[str]
        depth = 0
        escaped = False
        index = 0
        while index < len(text):
            char = text[index]
            following = text[index : index + 3]
            if state == "basic":
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    state = None
            elif state == "literal":
                if char == "'":
                    state = None
            elif state == "multi-basic":
                if following == '\"\"\"':
                    state = None
                    index += 2
                elif char == "\\":
                    index += 1
            elif state == "multi-literal":
                if following == "'''":
                    state = None
                    index += 2
            elif following == '\"\"\"':
                state = "multi-basic"
                index += 2
            elif following == "'''":
                state = "multi-literal"
                index += 2
            elif char == '"':
                state = "basic"
            elif char == "'":
                state = "literal"
            elif char == "#":
                newline = text.find("\n", index)
                if newline < 0:
                    break
                index = newline
            elif char in "[{":
                depth += 1
            elif char in "]}":
                depth -= 1
                if depth < 0:
                    return True
            index += 1
        return state is None and depth == 0

    @staticmethod
    def _assignment_value(statement: str) -> str:
        return statement.split("=", 1)[1].strip()

    def _record(self, assignment: Assignment) -> None:
        identity = (assignment.section, assignment.key)
        if identity in self.assignments:
            label = ".".join(part for part in identity if part)
            raise StateError(
                "duplicate Codex config key '{}' cannot be merged safely".format(label),
                operation="parse-codex-config",
            )
        self.assignments[identity] = assignment

    def _scan(self) -> None:
        current = None  # type: Optional[str]
        section_starts = {}  # type: Dict[str, int]
        index = 0
        while index < len(self.lines):
            line = self.lines[index]
            stripped_line = line.rstrip("\r\n")
            if self.ANY_SECTION_RE.match(stripped_line):
                header = self.SECTION_RE.match(stripped_line)
                current = header.group(1) if header else "__other__"
                if current in self.MANAGED_SECTIONS:
                    if current in section_starts:
                        raise StateError(
                            "duplicate [{}] table cannot be merged safely".format(current),
                            operation="parse-codex-config",
                        )
                    section_starts[current] = index
                index += 1
                continue

            match = self.ASSIGNMENT_RE.match(line)
            if not match:
                index += 1
                continue
            end = index + 1
            statement = line
            while not self._value_complete(self._assignment_value(statement)):
                if end >= len(self.lines):
                    raise StateError(
                        "unterminated TOML value in Codex config",
                        operation="parse-codex-config",
                    )
                statement += self.lines[end]
                end += 1

            raw_key = match.group(1)
            section = current
            key = raw_key
            dotted = False
            if current is None and "." in raw_key:
                prefix, suffix = raw_key.split(".", 1)
                if prefix in self.MANAGED_SECTIONS and "." not in suffix:
                    section, key, dotted = prefix, suffix, True
                    self.dotted_sections.add(prefix)
            if current is None and raw_key in self.MANAGED_SECTIONS:
                raise StateError(
                    "inline '{}' table cannot be merged safely".format(raw_key),
                    operation="parse-codex-config",
                )
            if section is None or section in self.MANAGED_SECTIONS:
                self._record(
                    Assignment(
                        section,
                        key,
                        index,
                        end,
                        self._assignment_value(statement),
                        dotted=dotted,
                    )
                )
            index = end

        ordered_headers = []  # type: List[Tuple[int, str]]
        for line_index, line in enumerate(self.lines):
            if self.ANY_SECTION_RE.match(line.rstrip("\r\n")):
                ordered_headers.append((line_index, "header"))
        for name, start in section_starts.items():
            end = len(self.lines)
            for line_index, _ in ordered_headers:
                if line_index > start:
                    end = line_index
                    break
            self.section_ranges[name] = (start, end)

    @staticmethod
    def _parsed_value(raw: str) -> Any:
        stripped = raw.strip()
        if stripped == "true":
            return True
        if stripped == "false":
            return False
        try:
            return ast.literal_eval(stripped)
        except (SyntaxError, ValueError):
            return object()

    def current_value(self, identity: ConfigKey) -> Any:
        assignment = self.assignments.get(identity)
        if assignment is None:
            return None
        return self._parsed_value(assignment.raw_value)

    def current_display(self, identity: ConfigKey) -> str:
        assignment = self.assignments[identity]
        return " ".join(assignment.raw_value.split())

    @staticmethod
    def render_value(value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, int):
            return str(value)
        if isinstance(value, str):
            escaped = value.replace("\\", "\\\\").replace('"', '\\"')
            return '"{}"'.format(escaped)
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            values = ["  {},".format(CodexConfigDocument.render_value(item)) for item in value]
            return "[\n{}\n]".format("\n".join(values))
        raise TypeError("unsupported Codex config value: {!r}".format(value))

    def _render_assignment(self, identity: ConfigKey, value: Any, dotted: bool = False) -> str:
        section, key = identity
        name = "{}.{}".format(section, key) if dotted and section else key
        rendered = self.render_value(value)
        return "{} = {}\n".format(name, rendered)

    def apply(self, updates: Sequence[Tuple[ConfigKey, Any]]) -> str:
        lines = list(self.lines)
        replacements = []  # type: List[Tuple[int, int, str]]
        additions = {}  # type: Dict[Optional[str], List[Tuple[ConfigKey, Any]]]
        for identity, value in updates:
            existing = self.assignments.get(identity)
            if existing is not None:
                replacements.append(
                    (
                        existing.start,
                        existing.end,
                        self._render_assignment(identity, value, dotted=existing.dotted),
                    )
                )
            else:
                section = identity[0]
                additions.setdefault(section, []).append((identity, value))

        for start, end, rendered in sorted(replacements, reverse=True):
            lines[start:end] = [rendered]

        # Re-scan after replacements so insertion points remain exact.
        intermediate = CodexConfigDocument("".join(lines))
        lines = list(intermediate.lines)

        top = list(additions.pop(None, []))
        for section in list(additions):
            if section in intermediate.dotted_sections:
                top.extend(additions.pop(section))
        if top:
            first_header = next(
                (
                    index
                    for index, line in enumerate(lines)
                    if self.ANY_SECTION_RE.match(line.rstrip("\r\n"))
                ),
                len(lines),
            )
            rendered = "".join(
                intermediate._render_assignment(identity, value, dotted=identity[0] is not None)
                for identity, value in top
            )
            if first_header and not lines[first_header - 1].endswith(("\n", "\r")):
                rendered = "\n" + rendered
            if first_header < len(lines) and first_header and lines[first_header - 1].strip():
                rendered += "\n"
            lines[first_header:first_header] = [rendered]

        for section, items in additions.items():
            current_text = "".join(lines)
            current = CodexConfigDocument(current_text)
            rendered = "".join(current._render_assignment(identity, value) for identity, value in items)
            if section in current.section_ranges:
                _, end = current.section_ranges[section]
                if end and current.lines[end - 1].strip():
                    rendered = "\n" + rendered
                lines = list(current.lines)
                lines[end:end] = [rendered]
            else:
                prefix = "" if not current_text or current_text.endswith("\n\n") else ("\n" if current_text.endswith("\n") else "\n\n")
                lines = list(current.lines)
                lines.append("{}[{}]\n{}".format(prefix, section, rendered))
        return "".join(lines)


class CodexConfigWizard:
    """Ask English configuration questions and apply an approved diff."""

    STATUS_LINE = [
        "model-with-reasoning",
        "context-remaining",
        "used-tokens",
        "five-hour-limit",
        "weekly-limit",
        "git-branch",
        "current-dir",
    ]

    def __init__(
        self,
        codex_home: Path,
        tty: TextIO,
        *,
        dry_run: bool = False,
        codex_command: str = "codex",
    ) -> None:
        self.codex_home = codex_home
        self.config_path = codex_home / "config.toml"
        self.tty = tty
        self.dry_run = dry_run
        self.codex_command = codex_command

    def _write(self, value: str) -> None:
        self.tty.write(value)
        self.tty.flush()

    def _ask_yes_no(self, prompt: str, *, default: bool) -> bool:
        suffix = " [Y/n]: " if default else " [y/N]: "
        while True:
            self._write(prompt + suffix)
            answer = self.tty.readline()
            if answer == "":
                raise InstallerError("input closed", stage="codex-config")
            value = answer.strip().lower()
            if not value:
                return default
            if value in ("y", "yes"):
                return True
            if value in ("n", "no"):
                return False
            self._write("Enter y or n.\n")

    def _ask_choice(self, prompt: str, choices: Sequence[str], default: int) -> int:
        while True:
            self._write("{} [{}]: ".format(prompt, default + 1))
            answer = self.tty.readline()
            if answer == "":
                raise InstallerError("input closed", stage="codex-config")
            value = answer.strip()
            if not value:
                return default
            if value.isdigit() and 1 <= int(value) <= len(choices):
                return int(value) - 1
            self._write("Enter a number from 1 to {}.\n".format(len(choices)))

    def _desired_settings(self) -> List[Tuple[ConfigKey, Any]]:
        settings = [
            ((None, "personality"), "pragmatic"),
            ((None, "model_reasoning_effort"), "medium"),
            ((None, "model_reasoning_summary"), "concise"),
            ((None, "model_verbosity"), "low"),
        ]  # type: List[Tuple[ConfigKey, Any]]

        self._write("\nConcurrent agent limit:\n  1) Conservative (2)\n  2) Balanced (4)\n  3) High (6)\n")
        thread_choice = self._ask_choice("Select", ("2", "4", "6"), 1)
        settings.append((("agents", "max_threads"), (2, 4, 6)[thread_choice]))
        nested = self._ask_yes_no("Allow subagents to spawn subagents?", default=False)
        settings.append((("agents", "max_depth"), 2 if nested else 1))

        cli = self._ask_yes_no("Do you use the Codex CLI?", default=True)
        if cli:
            usage = self._ask_yes_no(
                "Show model, context, usage limits, Git branch, and directory in the status line?",
                default=True,
            )
            if usage:
                settings.append((("tui", "status_line"), list(self.STATUS_LINE)))
            notifications = self._ask_yes_no(
                "Notify when a turn completes or approval is required while the terminal is unfocused?",
                default=True,
            )
            if notifications:
                settings.extend(
                    (
                        (("tui", "notifications"), ["agent-turn-complete", "approval-requested"]),
                        (("tui", "notification_condition"), "unfocused"),
                    )
                )
            else:
                settings.append((("tui", "notifications"), False))

        prevent_sleep = self._ask_yes_no(
            "Prevent this computer from sleeping during active Codex turns?",
            default=True,
        )
        settings.append((("features", "prevent_idle_sleep"), prevent_sleep))

        self._write(
            "\nWeb search mode:\n"
            "  1) Keep the current setting (Codex default when unset)\n"
            "  2) Cached\n"
            "  3) Indexed\n"
            "  4) Live\n"
            "  5) Disabled\n"
        )
        search_choice = self._ask_choice("Select", ("default", "cached", "indexed", "live", "disabled"), 0)
        if search_choice:
            settings.append(((None, "web_search"), ("cached", "indexed", "live", "disabled")[search_choice - 1]))
        return settings

    def _resolve_updates(
        self,
        document: CodexConfigDocument,
        desired: Iterable[Tuple[ConfigKey, Any]],
    ) -> List[Tuple[ConfigKey, Any]]:
        updates = []  # type: List[Tuple[ConfigKey, Any]]
        for identity, value in desired:
            if identity not in document.assignments:
                updates.append((identity, value))
                continue
            if document.current_value(identity) == value:
                continue
            label = ".".join(part for part in identity if part)
            self._write(
                "\nExisting value differs for {}:\n  current: {}\n  proposed: {}\n".format(
                    label,
                    document.current_display(identity),
                    CodexConfigDocument.render_value(value).replace("\n", " "),
                )
            )
            if self._ask_yes_no("Replace the existing value?", default=False):
                updates.append((identity, value))
        return updates

    def _validate(self, text: str) -> None:
        with tempfile.TemporaryDirectory(prefix="hukuhaka-codex-config-") as temp_name:
            home = Path(temp_name)
            (home / "config.toml").write_text(text, encoding="utf-8")
            env = dict(os.environ)
            env["CODEX_HOME"] = str(home)
            result = subprocess.run(
                (self.codex_command, "doctor", "--json"),
                text=True,
                capture_output=True,
                env=env,
            )
            try:
                report = json.loads(result.stdout)
                config_check = report["checks"]["config.load"]
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                detail = (result.stderr or result.stdout or "").strip()
                raise StateError(
                    "Codex config validation returned an invalid report: {}".format(
                        detail or str(exc)
                    ),
                    operation="validate-codex-config",
                    path=str(self.config_path),
                ) from exc
            if config_check.get("status") != "ok":
                detail = str(config_check.get("summary") or result.stderr or "config load failed")
                raise StateError(
                    "Codex rejected the proposed config: {}".format(detail.strip()),
                    operation="validate-codex-config",
                    path=str(self.config_path),
                )

    def _write_atomic(self, text: str) -> None:
        self.codex_home.mkdir(parents=True, exist_ok=True)
        if self.config_path.exists():
            backup = self.config_path.with_name("config.toml.hukuhaka-backup")
            shutil.copy2(str(self.config_path), str(backup))
        descriptor, temp_name = tempfile.mkstemp(prefix=".config.toml.", dir=str(self.codex_home))
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            if self.config_path.exists():
                mode = stat.S_IMODE(self.config_path.stat().st_mode)
                os.chmod(temp_name, mode)
            os.replace(temp_name, str(self.config_path))
        except Exception:
            try:
                os.unlink(temp_name)
            except OSError:
                pass
            raise

    def run(self) -> bool:
        self._write("\nCodex global configuration\n")
        if not self._ask_yes_no("Configure recommended global Codex settings?", default=True):
            self._write("Codex global configuration skipped.\n")
            return False
        try:
            original = self.config_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            original = ""
        except OSError as exc:
            raise StateError(
                "cannot read Codex config: {}".format(exc),
                operation="read-codex-config",
                path=str(self.config_path),
            ) from exc
        document = CodexConfigDocument(original)
        updates = self._resolve_updates(document, self._desired_settings())
        if not updates:
            self._write("Codex global configuration already matches the selected settings.\n")
            return False
        proposed = document.apply(updates)
        diff = "".join(
            difflib.unified_diff(
                original.splitlines(keepends=True),
                proposed.splitlines(keepends=True),
                fromfile=str(self.config_path),
                tofile=str(self.config_path) + " (proposed)",
            )
        )
        self._write("\nProposed changes:\n{}".format(diff))
        if not self._ask_yes_no("Apply these changes?", default=True):
            self._write("Codex global configuration unchanged.\n")
            return False
        self._validate(proposed)
        if self.dry_run:
            self._write("Dry run: Codex global configuration was not modified.\n")
            return True
        self._write_atomic(proposed)
        self._write("Updated {}. Restart Codex to load the settings.\n".format(self.config_path))
        return True
