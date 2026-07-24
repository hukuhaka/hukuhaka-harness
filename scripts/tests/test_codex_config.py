import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.harness_installer.codex_config import CodexConfigDocument, CodexConfigWizard
from scripts.harness_installer.errors import StateError
from scripts.harness_installer.install import Installer, build_parser


class FakeTty:
    def __init__(self, answers: str) -> None:
        self.input = io.StringIO(answers)
        self.output = io.StringIO()

    def write(self, value: str) -> int:
        return self.output.write(value)

    def flush(self) -> None:
        return None

    def readline(self) -> str:
        return self.input.readline()


class CodexConfigDocumentTests(unittest.TestCase):
    def test_adds_recommended_keys_without_rewriting_unknown_settings(self) -> None:
        original = 'model = "gpt-5.4"\n\n[history]\npersistence = "save-all"\n'
        document = CodexConfigDocument(original)
        result = document.apply(
            [
                ((None, "personality"), "pragmatic"),
                (("agents", "max_threads"), 4),
                (("tui", "status_line"), ["model-with-reasoning", "used-tokens"]),
                (("features", "prevent_idle_sleep"), True),
            ]
        )

        self.assertIn('model = "gpt-5.4"', result)
        self.assertIn('[history]\npersistence = "save-all"', result)
        self.assertIn('personality = "pragmatic"', result)
        self.assertIn('[agents]\nmax_threads = 4', result)
        self.assertIn('[tui]\nstatus_line = [', result)
        self.assertIn('[features]\nprevent_idle_sleep = true', result)

    def test_preserves_dotted_table_style(self) -> None:
        original = 'tui.theme = "dark"\nmodel = "gpt-5.4"\n'
        result = CodexConfigDocument(original).apply(
            [(("tui", "notification_condition"), "unfocused")]
        )

        self.assertIn('tui.theme = "dark"', result)
        self.assertIn('tui.notification_condition = "unfocused"', result)
        self.assertNotIn("[tui]", result)

    def test_top_level_append_handles_missing_final_newline(self) -> None:
        result = CodexConfigDocument('model = "gpt-5.4"').apply(
            [((None, "personality"), "pragmatic")]
        )

        self.assertEqual('model = "gpt-5.4"\npersonality = "pragmatic"\n', result)

    def test_quoted_and_array_tables_end_a_managed_section(self) -> None:
        original = (
            "[tui]\n"
            'theme = "custom"\n'
            '[projects."/tmp/repo"]\n'
            'trust_level = "trusted"\n'
            "[[hooks.Stop]]\n"
            'command = "check"\n'
        )
        document = CodexConfigDocument(original)

        self.assertNotIn(("tui", "trust_level"), document.assignments)
        self.assertNotIn(("tui", "command"), document.assignments)

    def test_replaces_only_the_selected_multiline_assignment(self) -> None:
        original = (
            "[tui]\n"
            "status_line = [\n"
            '  "current-dir",\n'
            "]\n"
            'theme = "custom"\n'
        )
        result = CodexConfigDocument(original).apply(
            [(("tui", "status_line"), ["model-with-reasoning", "current-dir"])]
        )

        self.assertIn('  "model-with-reasoning",', result)
        self.assertIn('theme = "custom"', result)

    def test_rejects_inline_managed_table(self) -> None:
        with self.assertRaises(StateError):
            CodexConfigDocument('tui = { theme = "dark" }\n')

    def test_rejects_unterminated_value(self) -> None:
        with self.assertRaises(StateError):
            CodexConfigDocument('[tui]\nstatus_line = [\n  "current-dir",\n')


class CodexConfigWizardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="codex-config-test-")
        self.codex_home = Path(self.temp.name) / ".codex"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def wizard(self, answers: str, *, dry_run: bool = False) -> CodexConfigWizard:
        return CodexConfigWizard(
            self.codex_home,
            FakeTty(answers),  # type: ignore[arg-type]
            dry_run=dry_run,
        )

    @mock.patch.object(CodexConfigWizard, "_validate")
    def test_default_answers_create_balanced_config_without_web_search(self, validate: mock.Mock) -> None:
        wizard = self.wizard("\n" * 9)

        self.assertTrue(wizard.run())

        text = (self.codex_home / "config.toml").read_text()
        self.assertIn('personality = "pragmatic"', text)
        self.assertIn('model_reasoning_effort = "medium"', text)
        self.assertIn("max_threads = 4", text)
        self.assertIn("max_depth = 1", text)
        self.assertIn('  "used-tokens",', text)
        self.assertIn('  "five-hour-limit",', text)
        self.assertIn('  "weekly-limit",', text)
        self.assertIn('notification_condition = "unfocused"', text)
        self.assertIn("prevent_idle_sleep = true", text)
        self.assertNotIn("web_search", text)
        validate.assert_called_once()

    @mock.patch.object(CodexConfigWizard, "_validate")
    def test_existing_conflict_defaults_to_keep_and_creates_backup(self, validate: mock.Mock) -> None:
        self.codex_home.mkdir(parents=True)
        path = self.codex_home / "config.toml"
        original = 'personality = "friendly"\ncustom_key = 7\n'
        path.write_text(original)
        # Defaults for the questionnaire, keep the conflicting personality, apply the diff.
        wizard = self.wizard("\n" * 10)

        self.assertTrue(wizard.run())

        result = path.read_text()
        self.assertIn('personality = "friendly"', result)
        self.assertIn("custom_key = 7", result)
        self.assertEqual(original, (self.codex_home / "config.toml.hukuhaka-backup").read_text())

    @mock.patch.object(CodexConfigWizard, "_validate")
    def test_dry_run_validates_but_does_not_write(self, validate: mock.Mock) -> None:
        wizard = self.wizard("\n" * 9, dry_run=True)

        self.assertTrue(wizard.run())

        self.assertFalse((self.codex_home / "config.toml").exists())
        validate.assert_called_once()

    @mock.patch.object(CodexConfigWizard, "_validate", side_effect=StateError("invalid"))
    def test_validation_failure_does_not_write(self, validate: mock.Mock) -> None:
        wizard = self.wizard("\n" * 9)

        with self.assertRaises(StateError):
            wizard.run()

        self.assertFalse((self.codex_home / "config.toml").exists())

    @mock.patch("scripts.harness_installer.codex_config.subprocess.run")
    def test_validation_uses_codex_config_load_check(self, run: mock.Mock) -> None:
        run.return_value = mock.Mock(
            returncode=1,
            stdout='{"checks":{"config.load":{"status":"ok","summary":"config loaded"}}}',
            stderr="missing auth",
        )

        self.wizard("")._validate('personality = "pragmatic"\n')

        self.assertEqual(("codex", "doctor", "--json"), run.call_args.args[0])

    @mock.patch("scripts.harness_installer.codex_config.subprocess.run")
    def test_validation_rejects_failed_codex_config_load_check(self, run: mock.Mock) -> None:
        run.return_value = mock.Mock(
            returncode=1,
            stdout='{"checks":{"config.load":{"status":"fail","summary":"invalid TOML"}}}',
            stderr="",
        )

        with self.assertRaises(StateError):
            self.wizard("")._validate('personality = "pragmatic"\n')


class InstallerCodexConfigTests(unittest.TestCase):
    def installer(self, *, configure: bool) -> Installer:
        arguments = [
            "--repo-root",
            str(Path(__file__).resolve().parents[2]),
            "--host",
            "codex",
            "--components",
            "hukuhaka-report-planner",
            "--skip-preflight",
        ]
        if configure:
            arguments.append("--configure-codex")
        args = build_parser().parse_args(arguments)
        args.version_explicit = False
        args.selector_used = False
        return Installer(args)

    def test_explicit_install_does_not_prompt_without_flag(self) -> None:
        installer = self.installer(configure=False)
        with mock.patch.object(installer, "_deploy_codex", return_value=True), mock.patch.object(
            installer, "_configure_codex", return_value=True
        ) as configure:
            self.assertEqual(0, installer.run())
        configure.assert_not_called()

    def test_configure_flag_runs_wizard_after_successful_codex_install(self) -> None:
        installer = self.installer(configure=True)
        with mock.patch.object(installer, "_deploy_codex", return_value=True), mock.patch.object(
            installer, "_configure_codex", return_value=True
        ) as configure:
            self.assertEqual(0, installer.run())
        configure.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
