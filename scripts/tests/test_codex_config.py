from __future__ import annotations

import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.install.codex_config import (
    RECOMMENDED_SETTINGS,
    CodexConfigEditor,
    current_values,
    update_config,
)
from scripts.install.common import InstallerError, StateError


class CodexConfigTextTests(unittest.TestCase):
    def test_recommended_settings_are_idempotent(self) -> None:
        first = update_config("", RECOMMENDED_SETTINGS)
        second = update_config(first, RECOMMENDED_SETTINGS)

        self.assertEqual(first, second)
        self.assertEqual(RECOMMENDED_SETTINGS, current_values(first))
        self.assertNotIn("\nmodel =", first)

    def test_unmanaged_text_comments_and_tables_are_preserved(self) -> None:
        original = (
            "# personal note\n"
            'model = "gpt-user-choice"\n'
            'personality = "friendly" # replace this value\n'
            "\n"
            "[mcp_servers.example]\n"
            'command = "example"\n'
            "\n"
            "[agents]\n"
            "enabled = false\n"
            "custom_limit = 9\n"
        )

        updated = update_config(original, RECOMMENDED_SETTINGS)

        self.assertIn("# personal note\n", updated)
        self.assertIn("# replace this value", updated)
        self.assertIn('model = "gpt-user-choice"\n', updated)
        self.assertIn("[mcp_servers.example]\ncommand = \"example\"\n", updated)
        self.assertIn("custom_limit = 9\n", updated)
        self.assertEqual(RECOMMENDED_SETTINGS, current_values(updated))

    def test_dotted_managed_keys_remain_dotted(self) -> None:
        original = (
            "agents.enabled = false\n"
            "tui.notification_condition = \"always\"\n"
            "features.prevent_idle_sleep = false\n"
        )

        updated = update_config(original, RECOMMENDED_SETTINGS)

        self.assertIn("agents.max_concurrent_threads_per_session = 4", updated)
        self.assertIn("tui.status_line =", updated)
        self.assertNotIn("\n[agents]\n", updated)
        self.assertNotIn("\n[tui]\n", updated)
        self.assertEqual(RECOMMENDED_SETTINGS, current_values(updated))

    def test_multiline_managed_array_is_replaced_as_one_value(self) -> None:
        original = (
            "[tui]\n"
            "status_line = [\n"
            '  "model",\n'
            '  "current-dir",\n'
            "]\n"
        )

        updated = update_config(
            original,
            {("tui", "status_line"): RECOMMENDED_SETTINGS[("tui", "status_line")]},
        )

        self.assertEqual(
            RECOMMENDED_SETTINGS[("tui", "status_line")],
            current_values(updated)[("tui", "status_line")],
        )
        self.assertNotIn('  "model",', updated)

    def test_duplicate_managed_key_is_rejected(self) -> None:
        with self.assertRaisesRegex(StateError, "duplicate managed Codex config key"):
            update_config(
                'personality = "friendly"\npersonality = "pragmatic"\n',
                RECOMMENDED_SETTINGS,
            )

    def test_inline_managed_table_is_rejected(self) -> None:
        with self.assertRaisesRegex(StateError, "inline value"):
            update_config(
                "agents = { enabled = false }\n",
                RECOMMENDED_SETTINGS,
            )


class CodexConfigApplyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="hukuhaka config ")
        self.codex_home = Path(self.temp.name) / ".codex"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def editor(self, *, dry_run: bool = False) -> CodexConfigEditor:
        return CodexConfigEditor(self.codex_home, dry_run=dry_run)

    def test_new_file_is_atomic_private_and_validated(self) -> None:
        editor = self.editor()
        plan = editor.plan(RECOMMENDED_SETTINGS)

        with mock.patch.object(editor, "_doctor") as doctor:
            self.assertTrue(editor.apply(plan, show_diff=False))

        doctor.assert_called_once_with()
        self.assertEqual(
            RECOMMENDED_SETTINGS,
            current_values(editor.path.read_text(encoding="utf-8")),
        )
        self.assertEqual(0o600, stat.S_IMODE(editor.path.stat().st_mode))
        self.assertFalse(editor.backup.exists())

    def test_existing_file_mode_and_unmanaged_text_are_preserved_with_backup(self) -> None:
        self.codex_home.mkdir()
        path = self.codex_home / "config.toml"
        original = b'# keep\nmodel = "user-model"\npersonality = "friendly"\n'
        path.write_bytes(original)
        path.chmod(0o640)
        editor = self.editor()
        plan = editor.plan(RECOMMENDED_SETTINGS)

        with mock.patch.object(editor, "_doctor"):
            editor.apply(plan, show_diff=False)

        self.assertEqual(original, editor.backup.read_bytes())
        self.assertEqual(0o640, stat.S_IMODE(editor.path.stat().st_mode))
        self.assertIn('model = "user-model"', editor.path.read_text(encoding="utf-8"))

    def test_doctor_failure_restores_the_original(self) -> None:
        self.codex_home.mkdir()
        path = self.codex_home / "config.toml"
        original = b'personality = "friendly"\n'
        path.write_bytes(original)
        editor = self.editor()
        plan = editor.plan(RECOMMENDED_SETTINGS)

        with mock.patch.object(
            editor,
            "_doctor",
            side_effect=InstallerError("doctor rejected config"),
        ):
            with self.assertRaisesRegex(InstallerError, "doctor rejected"):
                editor.apply(plan, show_diff=False)

        self.assertEqual(original, path.read_bytes())
        self.assertEqual(original, editor.backup.read_bytes())

    def test_dry_run_creates_no_directory_or_file(self) -> None:
        editor = self.editor(dry_run=True)
        plan = editor.plan(RECOMMENDED_SETTINGS)

        with mock.patch.object(editor, "_doctor") as doctor:
            self.assertFalse(editor.apply(plan, show_diff=False))

        doctor.assert_not_called()
        self.assertFalse(self.codex_home.exists())

    def test_change_after_diff_is_refused(self) -> None:
        self.codex_home.mkdir()
        editor = self.editor()
        editor.path.write_text('personality = "friendly"\n', encoding="utf-8")
        plan = editor.plan(RECOMMENDED_SETTINGS)
        editor.path.write_text('personality = "none"\n', encoding="utf-8")

        with self.assertRaisesRegex(StateError, "changed after the diff"):
            editor.apply(plan, show_diff=False)

        self.assertEqual(
            'personality = "none"\n',
            editor.path.read_text(encoding="utf-8"),
        )

    def test_verify_allows_plugin_sections_added_after_apply(self) -> None:
        editor = self.editor()
        plan = editor.plan(RECOMMENDED_SETTINGS)

        with mock.patch.object(editor, "_doctor"):
            editor.apply(plan, show_diff=False)

        with editor.path.open("a", encoding="utf-8") as config:
            config.write(
                '\n[plugins."hukuhaka-report-planner@hukuhaka-harness"]\n'
                "enabled = true\n"
            )

        with mock.patch.object(editor, "_doctor") as doctor:
            editor.verify(plan)

        doctor.assert_called_once_with()
        self.assertEqual(
            RECOMMENDED_SETTINGS,
            current_values(editor.path.read_text(encoding="utf-8")),
        )
        self.assertIn(
            '[plugins."hukuhaka-report-planner@hukuhaka-harness"]',
            editor.path.read_text(encoding="utf-8"),
        )

    def test_verify_rejects_managed_value_changed_by_component_install(self) -> None:
        editor = self.editor()
        plan = editor.plan(RECOMMENDED_SETTINGS)

        with mock.patch.object(editor, "_doctor"):
            editor.apply(plan, show_diff=False)
        editor.path.write_text(
            editor.path.read_text(encoding="utf-8").replace(
                'model_reasoning_effort = "medium"',
                'model_reasoning_effort = "high"',
            ),
            encoding="utf-8",
        )

        with mock.patch.object(editor, "_doctor") as doctor:
            with self.assertRaisesRegex(
                StateError, "managed Codex config changed"
            ):
                editor.verify(plan)

        doctor.assert_not_called()

    def test_doctor_accepts_config_ok_when_other_checks_make_exit_nonzero(self) -> None:
        editor = self.editor()
        report = (
            '{"checks":{"config.load":{"status":"ok","summary":"config loaded"},'
            '"auth.credentials":{"status":"fail"}}}'
        )
        completed = subprocess.CompletedProcess(
            ["codex", "doctor", "--json"],
            1,
            stdout=report,
            stderr="",
        )

        with mock.patch(
            "scripts.install.codex_config.shutil.which", return_value="/fake/codex"
        ), mock.patch(
            "scripts.install.codex_config.subprocess.run", return_value=completed
        ):
            editor._doctor()


if __name__ == "__main__":
    unittest.main()
