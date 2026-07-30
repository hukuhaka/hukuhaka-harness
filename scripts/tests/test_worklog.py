from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "marketplace" / "hukuhaka-worklog"
SCRIPT = PLUGIN / "skills" / "worklog" / "scripts" / "worklog.py"
SPEC = importlib.util.spec_from_file_location("hukuhaka_worklog_script", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
WORKLOG = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = WORKLOG
SPEC.loader.exec_module(WORKLOG)


def history_entry(day: int, title: str, body: str = "Recorded result.") -> str:
    return f"### 2026-07-{day:02d} — {title}\n\n{body}"


class WorklogScriptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="hukuhaka worklog ")
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_setup_is_idempotent_and_preserves_unmanaged_instructions(self) -> None:
        instructions = self.root / "CLAUDE.md"
        instructions.write_text("# Existing\n\nKeep this text.\n", encoding="utf-8")

        WORKLOG.setup(self.root, "claude")
        first = instructions.read_text(encoding="utf-8")
        WORKLOG.setup(self.root, "claude")

        self.assertEqual(first, instructions.read_text(encoding="utf-8"))
        self.assertIn("# Existing\n\nKeep this text.", first)
        self.assertEqual(1, first.count(WORKLOG.BEGIN_MARKER))
        self.assertTrue((self.root / ".hukuhaka" / "work.md").is_file())
        self.assertTrue((self.root / ".hukuhaka" / "changelog.md").is_file())
        self.assertTrue((self.root / ".hukuhaka" / "changelog").is_dir())

    def test_setup_targets_agents_for_codex(self) -> None:
        WORKLOG.setup(self.root, "codex")

        agents = (self.root / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("`$worklog`", agents)
        self.assertFalse((self.root / "CLAUDE.md").exists())

    def test_hook_runs_claude_setup_and_blocks_the_model(self) -> None:
        output = io.StringIO()
        payload = {
            "prompt": "/hukuhaka-worklog:worklog setup",
            "cwd": str(self.root),
        }

        WORKLOG.run_hook(io.StringIO(json.dumps(payload)), output, {})
        response = json.loads(output.getvalue())

        self.assertEqual("block", response["decision"])
        self.assertIn("worklog setup (claude)", response["reason"])
        self.assertTrue((self.root / "CLAUDE.md").is_file())
        self.assertFalse((self.root / "AGENTS.md").exists())

        repeated = io.StringIO()
        WORKLOG.run_hook(io.StringIO(json.dumps(payload)), repeated, {})
        self.assertIn("Created: none", json.loads(repeated.getvalue())["reason"])

    def test_hook_runs_codex_setup_from_plugin_data(self) -> None:
        output = io.StringIO()
        payload = {
            "prompt": "$worklog setup",
            "cwd": str(self.root),
        }

        WORKLOG.run_hook(
            io.StringIO(json.dumps(payload)),
            output,
            {"PLUGIN_DATA": ""},
        )
        response = json.loads(output.getvalue())

        self.assertEqual("block", response["decision"])
        self.assertIn("worklog setup (codex)", response["reason"])
        self.assertTrue((self.root / "AGENTS.md").is_file())
        self.assertFalse((self.root / "CLAUDE.md").exists())

    def test_hook_status_and_archive_are_mechanical(self) -> None:
        WORKLOG.setup(self.root, "claude")
        changelog = self.root / ".hukuhaka" / "changelog.md"
        entries = [history_entry(day, f"Entry {day}") for day in range(20, 8, -1)]
        changelog.write_text(
            WORKLOG.CHANGELOG_TEMPLATE.rstrip() + "\n\n" + "\n\n".join(entries) + "\n",
            encoding="utf-8",
        )

        status_output = io.StringIO()
        WORKLOG.run_hook(
            io.StringIO(
                json.dumps(
                    {
                        "prompt": "/hukuhaka-worklog:worklog status",
                        "cwd": str(self.root),
                    }
                )
            ),
            status_output,
            {},
        )
        self.assertIn("Worklog status", json.loads(status_output.getvalue())["reason"])

        archive_output = io.StringIO()
        WORKLOG.run_hook(
            io.StringIO(
                json.dumps(
                    {
                        "prompt": "/hukuhaka-worklog:worklog archive",
                        "cwd": str(self.root),
                    }
                )
            ),
            archive_output,
            {},
        )
        response = json.loads(archive_output.getvalue())
        self.assertEqual("block", response["decision"])
        self.assertIn("kept 10 in Recent; moved 2", response["reason"])
        self.assertTrue(
            (self.root / ".hukuhaka" / "changelog" / "2026-07.md").is_file()
        )

    def test_hook_passes_through_nonmechanical_requests(self) -> None:
        for prompt in (
            "$worklog record this as planned",
            "$worklog archive --keep 20",
            "$worklog status ",
            "please set up the worklog",
        ):
            with self.subTest(prompt=prompt):
                output = io.StringIO()
                WORKLOG.run_hook(
                    io.StringIO(json.dumps({"prompt": prompt, "cwd": str(self.root)})),
                    output,
                    {"PLUGIN_DATA": "test"},
                )
                self.assertEqual("", output.getvalue())
        self.assertFalse((self.root / ".hukuhaka").exists())

    def test_hook_fails_closed_for_recognized_command_errors(self) -> None:
        missing_cwd = io.StringIO()
        WORKLOG.run_hook(
            io.StringIO(json.dumps({"prompt": "$worklog setup"})),
            missing_cwd,
            {"PLUGIN_DATA": "test"},
        )
        response = json.loads(missing_cwd.getvalue())
        self.assertEqual("block", response["decision"])
        self.assertIn("missing cwd", response["reason"])

        WORKLOG.setup(self.root, "claude")
        (self.root / ".hukuhaka" / "work.md").write_text(
            "# Work\n\n## Unexpected\n",
            encoding="utf-8",
        )
        malformed = io.StringIO()
        WORKLOG.run_hook(
            io.StringIO(
                json.dumps(
                    {
                        "prompt": "/hukuhaka-worklog:worklog status",
                        "cwd": str(self.root),
                    }
                )
            ),
            malformed,
            {},
        )
        response = json.loads(malformed.getvalue())
        self.assertEqual("block", response["decision"])
        self.assertIn("work.md must contain exactly", response["reason"])

    def test_malformed_markers_fail_before_creating_worklog_files(self) -> None:
        (self.root / "AGENTS.md").write_text(
            f"{WORKLOG.BEGIN_MARKER}\nmissing end\n",
            encoding="utf-8",
        )

        with self.assertRaises(WORKLOG.WorklogError):
            WORKLOG.setup(self.root, "codex")

        self.assertFalse((self.root / ".hukuhaka").exists())

    def test_setup_ignores_legacy_backlog(self) -> None:
        legacy = self.root / ".claude" / "backlog.md"
        legacy.parent.mkdir()
        legacy.write_text("legacy content\n", encoding="utf-8")

        WORKLOG.setup(self.root, "claude")

        self.assertEqual("legacy content\n", legacy.read_text(encoding="utf-8"))

    def test_status_reports_structural_counts_without_rewriting(self) -> None:
        WORKLOG.setup(self.root, "claude")
        work = self.root / ".hukuhaka" / "work.md"
        work.write_text(
            """# Work

## In Progress

- **Active item.** Current state.
  - Next gate: run the fixture.

## Planned

- **Planned item.** Future state.

## On Hold

- **Held item.** Waiting.
  - Revisit when: the API ships.
""",
            encoding="utf-8",
        )
        before = work.read_bytes()
        output = io.StringIO()

        with redirect_stdout(output):
            WORKLOG.status(self.root)

        self.assertEqual(before, work.read_bytes())
        self.assertIn("In Progress (1)", output.getvalue())
        self.assertIn("Planned (1)", output.getvalue())
        self.assertIn("On Hold (1)", output.getvalue())
        self.assertIn("Recent history: 0/10", output.getvalue())

    def test_archive_keeps_ten_and_is_idempotent(self) -> None:
        WORKLOG.setup(self.root, "claude")
        changelog = self.root / ".hukuhaka" / "changelog.md"
        entries = [history_entry(day, f"Entry {day}") for day in range(20, 8, -1)]
        changelog.write_text(
            WORKLOG.CHANGELOG_TEMPLATE.rstrip() + "\n\n" + "\n\n".join(entries) + "\n",
            encoding="utf-8",
        )

        WORKLOG.archive_history(self.root, 10)
        first_main = changelog.read_text(encoding="utf-8")
        archive = self.root / ".hukuhaka" / "changelog" / "2026-07.md"
        first_archive = archive.read_text(encoding="utf-8")
        WORKLOG.archive_history(self.root, 10)

        self.assertEqual(10, len(WORKLOG.parse_history(first_main, changelog)[1]))
        self.assertIn("Entry 10", first_archive)
        self.assertIn("Entry 9", first_archive)
        self.assertEqual(first_main, changelog.read_text(encoding="utf-8"))
        self.assertEqual(first_archive, archive.read_text(encoding="utf-8"))

    def test_archive_conflict_fails_before_recent_changes(self) -> None:
        WORKLOG.setup(self.root, "claude")
        changelog = self.root / ".hukuhaka" / "changelog.md"
        entries = [history_entry(day, f"Entry {day}") for day in range(20, 9, -1)]
        changelog.write_text(
            WORKLOG.CHANGELOG_TEMPLATE.rstrip() + "\n\n" + "\n\n".join(entries) + "\n",
            encoding="utf-8",
        )
        archive = self.root / ".hukuhaka" / "changelog" / "2026-07.md"
        archive.write_text(
            "# Changelog — 2026-07\n\n"
            + history_entry(10, "Entry 10", "Conflicting result.")
            + "\n",
            encoding="utf-8",
        )
        before = changelog.read_bytes()

        with self.assertRaises(WORKLOG.WorklogError):
            WORKLOG.archive_history(self.root, 10)

        self.assertEqual(before, changelog.read_bytes())

        output = io.StringIO()
        WORKLOG.run_hook(
            io.StringIO(
                json.dumps(
                    {
                        "prompt": "/hukuhaka-worklog:worklog archive",
                        "cwd": str(self.root),
                    }
                )
            ),
            output,
            {},
        )
        response = json.loads(output.getvalue())
        self.assertEqual("block", response["decision"])
        self.assertIn("conflicting archive entry", response["reason"])
        self.assertEqual(before, changelog.read_bytes())


class WorklogPackageTests(unittest.TestCase):
    def test_dual_host_manifests_share_identity_and_version(self) -> None:
        claude = json.loads(
            (PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        codex = json.loads(
            (PLUGIN / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        self.assertEqual("hukuhaka-worklog", claude["name"])
        self.assertEqual(claude["name"], codex["name"])
        self.assertEqual(claude["version"], codex["version"])
        self.assertEqual("0.2.0", claude["version"])
        self.assertEqual("./skills/", claude["skills"])
        self.assertEqual("./skills/", codex["skills"])
        self.assertEqual("./hooks/claude-codex-hooks.json", claude["hooks"])
        self.assertEqual("./hooks/claude-codex-hooks.json", codex["hooks"])

    def test_shared_skill_is_model_invokable_and_host_neutral(self) -> None:
        skill = (PLUGIN / "skills" / "worklog" / "SKILL.md").read_text(encoding="utf-8")
        header = skill.split("---", 2)[1]
        self.assertNotIn("disable-model-invocation", header)
        self.assertNotIn("allowed-tools", header)
        self.assertIn(".hukuhaka/work.md", skill)
        self.assertIn("Never read, migrate, or write a legacy `backlog.md`", skill)
        self.assertNotIn("references/writing-guide.md", skill)
        self.assertFalse(
            (
                PLUGIN
                / "skills"
                / "worklog"
                / "references"
                / "writing-guide.md"
            ).exists()
        )


if __name__ == "__main__":
    unittest.main()
