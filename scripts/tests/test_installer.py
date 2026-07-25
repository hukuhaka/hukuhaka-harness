from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.install.claude import ClaudeDeployment
from scripts.install.codex import CodexGuidanceDeployment
from scripts.install.common import DriftError, FileTransaction, InstallerError, StateError
from scripts.install.main import Installer, build_parser
from scripts.install.terminal import prompt_install_plan


ROOT = Path(__file__).resolve().parents[2]
COMPONENTS = ["hukuhaka-report-planner", "hukuhaka-codex", "claude-md"]


class InstallerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="hukuhaka installer ")
        self.home = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    @property
    def claude(self) -> Path:
        return self.home / ".claude"

    @property
    def manifest(self) -> Path:
        return self.claude / ".hukuhaka-manifest.json"

    def deployment(self, *, force: bool = False, dry_run: bool = False) -> ClaudeDeployment:
        return ClaudeDeployment(ROOT, self.home, COMPONENTS, force=force, dry_run=dry_run)

    def test_fresh_reinstall_and_uninstall_are_idempotent(self) -> None:
        self.deployment().deploy()
        first = json.loads(self.manifest.read_text())
        self.deployment().deploy()
        second = json.loads(self.manifest.read_text())
        self.assertEqual(first["files"], second["files"])
        self.assertEqual(first["hashes"], second["hashes"])
        self.assertEqual(2, second["schemaVersion"])
        self.deployment(force=True).uninstall(confirm=False)
        self.assertFalse(self.manifest.exists())
        self.deployment(force=True).uninstall(confirm=False)

    def test_legacy_partial_state_converges_when_dropped_dirs_are_absent(self) -> None:
        self.claude.mkdir(parents=True)
        self.manifest.write_text(
            json.dumps(
                {
                    "version": "1.0.9",
                    "components": ["hukuhaka-ltm", "hukuhaka-project-mapper"],
                    "files": [],
                }
            )
        )
        self.deployment().deploy()
        manifest = json.loads(self.manifest.read_text())
        self.assertEqual(2, manifest["schemaVersion"])
        self.assertEqual(set(COMPONENTS), set(manifest["components"]))

    def test_malformed_registry_fails_before_file_mutation(self) -> None:
        self.claude.mkdir(parents=True)
        (self.claude / "settings.json").write_text("{broken")
        with self.assertRaises(StateError):
            self.deployment().deploy()
        self.assertFalse((self.claude / "CLAUDE.md").exists())
        self.assertEqual("{broken", (self.claude / "settings.json").read_text())

    def test_malformed_manifest_fields_fail_before_file_mutation(self) -> None:
        self.claude.mkdir(parents=True)
        self.manifest.write_text(json.dumps({"schemaVersion": 2, "files": {}, "hashes": []}))
        with self.assertRaises(StateError):
            self.deployment().deploy()
        self.assertFalse((self.claude / "CLAUDE.md").exists())

    def test_managed_file_drift_requires_force(self) -> None:
        self.deployment().deploy()
        target = self.claude / "CLAUDE.md"
        target.write_text("user edit\n")
        with self.assertRaises(DriftError):
            self.deployment().deploy()
        self.assertEqual("user edit\n", target.read_text())
        self.deployment(force=True).deploy()
        self.assertNotEqual("user edit\n", target.read_text())

    def test_apply_failure_rolls_back_files_and_manifest(self) -> None:
        self.deployment().deploy()
        target = self.claude / "CLAUDE.md"
        target.write_text("pre-transaction edit\n")
        original_manifest = self.manifest.read_bytes()
        deployment = self.deployment(force=True)
        with mock.patch.object(
            deployment,
            "_write_registries",
            side_effect=InstallerError("injected registry failure"),
        ):
            with self.assertRaises(InstallerError):
                deployment.deploy()
        self.assertEqual("pre-transaction edit\n", target.read_text())
        self.assertEqual(original_manifest, self.manifest.read_bytes())

    def test_pending_transaction_is_recovered_on_next_run(self) -> None:
        self.claude.mkdir(parents=True)
        target = self.claude / "settings.json"
        target.write_text("old\n")
        transaction = FileTransaction(self.claude)
        transaction.__enter__()
        transaction.write_bytes(target, b"new\n")
        self.assertEqual("new\n", target.read_text())
        self.assertEqual(1, FileTransaction.recover_pending(self.claude))
        self.assertEqual("old\n", target.read_text())

    def test_snapshot_is_not_journaled_until_backup_exists(self) -> None:
        self.claude.mkdir(parents=True)
        target = self.claude / "settings.json"
        target.write_text("old\n")
        transaction = FileTransaction(self.claude)
        transaction.__enter__()
        with mock.patch("shutil.copy2", side_effect=OSError("injected backup failure")):
            with self.assertRaises(OSError):
                transaction.snapshot(target)
        journal = json.loads(transaction.journal_path.read_text())
        self.assertEqual([], journal["entries"])
        transaction.__exit__(None, None, None)

    def test_recovery_rejects_target_outside_state_root(self) -> None:
        self.claude.mkdir(parents=True)
        outside = self.home / "outside.txt"
        outside.write_text("keep\n")
        transaction = FileTransaction(self.claude)
        transaction.__enter__()
        transaction.entries = [
            {"target": str(outside), "existed": False, "backup": "backups/000000"}
        ]
        transaction._write_journal("pending")
        with self.assertRaises(StateError):
            FileTransaction.recover_pending(self.claude)
        self.assertEqual("keep\n", outside.read_text())
        transaction.__exit__(None, None, None)

    def test_uninstall_does_not_create_missing_registries(self) -> None:
        self.claude.mkdir(parents=True)
        self.manifest.write_text(
            json.dumps(
                {
                    "schemaVersion": 2,
                    "version": "1.0.11",
                    "components": [],
                    "files": [],
                    "hashes": {},
                }
            )
        )
        self.deployment(force=True).uninstall(confirm=False)
        self.assertFalse((self.claude / "settings.json").exists())
        self.assertFalse((self.claude / "plugins" / "installed_plugins.json").exists())
        self.assertFalse((self.claude / "plugins" / "known_marketplaces.json").exists())

    def test_uninstall_preserves_optional_statusline(self) -> None:
        self.deployment().deploy()
        settings_path = self.claude / "settings.json"
        settings = json.loads(settings_path.read_text())
        settings["statusLine"] = {"command": "npx ccstatusline"}
        settings_path.write_text(json.dumps(settings))
        legacy = self.claude / "statusline.sh"
        legacy.write_text("user managed\n")
        self.deployment(force=True).uninstall(confirm=False)
        self.assertEqual({"command": "npx ccstatusline"}, json.loads(settings_path.read_text())["statusLine"])
        self.assertEqual("user managed\n", legacy.read_text())

    def test_ghost_registry_and_directory_are_removed(self) -> None:
        plugins = self.claude / "plugins"
        marketplace = plugins / "hukuhaka-plugin"
        removed_names = ("hukuhaka-ltm", "hukuhaka-project-mapper")
        for name in removed_names:
            ghost_dir = marketplace / name
            ghost_dir.mkdir(parents=True)
            (ghost_dir / "old.txt").write_text("old")
        registry = plugins / "installed_plugins.json"
        registry.parent.mkdir(parents=True, exist_ok=True)
        registry.write_text(
            json.dumps(
                {
                    "version": 2,
                    "plugins": {
                        "{}@hukuhaka-plugin".format(name): [
                            {
                                "scope": "user",
                                "installPath": str(marketplace / name),
                                "version": "0",
                            }
                        ]
                        for name in removed_names
                    },
                }
            )
        )
        self.deployment().deploy()
        installed = json.loads(registry.read_text())["plugins"]
        for name in removed_names:
            self.assertNotIn("{}@hukuhaka-plugin".format(name), installed)
            self.assertFalse((marketplace / name).exists())

    def test_dry_run_creates_no_state(self) -> None:
        self.deployment(dry_run=True).deploy()
        self.assertFalse(self.claude.exists())

    def test_reset_preserves_template_and_rejects_modified_plugin(self) -> None:
        self.deployment().deploy()
        plugin = (
            self.claude
            / "plugins"
            / "hukuhaka-plugin"
            / "hukuhaka-report-planner"
            / ".claude-plugin"
            / "plugin.json"
        )
        plugin.write_text("user edit\n")
        with self.assertRaises(DriftError):
            self.deployment().reset_for_install()
        self.assertTrue(plugin.exists())

        self.deployment(force=True).reset_for_install()
        self.assertFalse(plugin.exists())
        self.assertTrue((self.claude / "CLAUDE.md").exists())
        manifest = json.loads(self.manifest.read_text())
        self.assertEqual(["claude-md"], manifest["components"])

    def test_reset_can_include_managed_template(self) -> None:
        self.deployment().deploy()
        self.deployment().reset_for_install(reset_template=True)
        self.assertFalse((self.claude / "CLAUDE.md").exists())
        self.assertFalse(self.manifest.exists())

class InstallerSelectionTests(unittest.TestCase):
    def installer(self, host: str = "claude", *selection: str) -> Installer:
        arguments = [
            "--repo-root",
            str(ROOT),
            "--host",
            host,
            *selection,
        ]
        args = build_parser().parse_args(arguments)
        args.version_explicit = False
        args.selector_used = not bool(selection)
        return Installer(args)

    def test_no_tty_preserves_current_and_adds_supported_defaults(self) -> None:
        installer = self.installer()
        with mock.patch.object(
            installer, "current_components", return_value={"agent-teams"}
        ):
            selected = installer.choose_components()

        self.assertEqual(
            [
                "hukuhaka-report-planner",
                "hukuhaka-engineering-plan",
                "hukuhaka-codex",
                "claude-md",
                "agent-teams",
            ],
            selected,
        )
        self.assertFalse(installer.args.selector_used)

    def test_explicit_selection_does_not_probe_tty(self) -> None:
        installer = self.installer(
            "claude",
            "--components",
            "hukuhaka-engineering-plan",
        )
        with mock.patch.object(installer, "current_components", return_value=set()), mock.patch.object(
            installer, "_tty_available", side_effect=AssertionError("TTY probe was unexpected")
        ):
            self.assertEqual(["hukuhaka-engineering-plan"], installer.choose_components())

    def test_removed_legacy_components_are_unknown(self) -> None:
        for name in ("hukuhaka-ltm", "hukuhaka-project-mapper"):
            installer = self.installer("claude", "--components", name)
            with self.assertRaisesRegex(InstallerError, "unknown component '{}'".format(name)):
                installer.choose_components()

    def test_declared_alias_resolves_to_current_component(self) -> None:
        installer = self.installer(
            "claude",
            "--components",
            "old-report-planner",
        )
        installer.aliases["old-report-planner"] = "hukuhaka-report-planner"
        self.assertEqual(
            ["hukuhaka-report-planner"],
            installer.choose_components(),
        )


class CodexGuidanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="hukuhaka codex ")
        self.codex_home = Path(self.temp.name)
        self.source = self.codex_home / "source.md"
        self.source.write_text("# Managed\n")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def deployment(self, *, force: bool = False) -> CodexGuidanceDeployment:
        return CodexGuidanceDeployment(
            self.source,
            self.codex_home,
            "1.0.13",
            enabled=True,
            force=force,
        )

    def test_install_and_uninstall_preserve_user_text(self) -> None:
        target = self.codex_home / "AGENTS.md"
        target.write_text("# User\n")
        self.deployment().deploy()
        self.assertIn("# User", target.read_text())
        self.assertIn("# Managed", target.read_text())
        CodexGuidanceDeployment(
            self.source,
            self.codex_home,
            "1.0.13",
            enabled=False,
        ).uninstall()
        self.assertEqual("# User\n", target.read_text())

    def test_modified_managed_block_requires_force(self) -> None:
        self.deployment().deploy()
        target = self.codex_home / "AGENTS.md"
        target.write_text(target.read_text().replace("# Managed", "# Changed"))
        with self.assertRaises(DriftError):
            self.deployment().deploy()
        self.deployment(force=True).deploy()
        self.assertIn("# Managed", target.read_text())


class PlainTerminalSelectionTests(unittest.TestCase):
    def test_hosts_are_rendered_separately_with_reset_before_install(self) -> None:
        output = io.StringIO()
        plans = prompt_install_plan(
            io.StringIO(),
            output,
            sections=[
                {
                    "host": "claude",
                    "label": "Claude Code",
                    "available": True,
                    "version": "2.1",
                    "components": [{"name": "planner", "kind": "plugin"}],
                    "selected": {"planner"},
                },
                {
                    "host": "codex",
                    "label": "Codex",
                    "available": False,
                    "version": "",
                    "components": [],
                    "selected": set(),
                },
            ],
            keys=("down", "down", "toggle", "down", "down", "enter"),
        )

        self.assertEqual(1, len(plans))
        self.assertEqual("claude", plans[0].host)
        self.assertTrue(plans[0].reset_before_install)
        self.assertFalse(plans[0].reset_templates)
        rendered = output.getvalue()
        self.assertIn("Claude Code", rendered)
        self.assertIn("Codex", rendered)
        self.assertIn("unavailable", rendered)


if __name__ == "__main__":
    unittest.main()
