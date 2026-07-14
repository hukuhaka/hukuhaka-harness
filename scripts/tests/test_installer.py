from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.harness_installer.claude import ClaudeDeployment
from scripts.harness_installer.errors import DriftError, InstallerError, StateError
from scripts.harness_installer.extras import ExtrasSettings
from scripts.harness_installer.filesystem import FileTransaction


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
        ghost_dir = plugins / "hukuhaka-plugin" / "renamed-plugin"
        ghost_dir.mkdir(parents=True)
        (ghost_dir / "old.txt").write_text("old")
        registry = plugins / "installed_plugins.json"
        registry.parent.mkdir(parents=True, exist_ok=True)
        registry.write_text(
            json.dumps(
                {
                    "version": 2,
                    "plugins": {
                        "renamed-plugin@hukuhaka-plugin": [
                            {"scope": "user", "installPath": str(ghost_dir), "version": "0"}
                        ]
                    },
                }
            )
        )
        self.deployment().deploy()
        installed = json.loads(registry.read_text())["plugins"]
        self.assertNotIn("renamed-plugin@hukuhaka-plugin", installed)
        self.assertFalse(ghost_dir.exists())

    def test_dry_run_creates_no_state(self) -> None:
        self.deployment(dry_run=True).deploy()
        self.assertFalse(self.claude.exists())

    def test_extras_dry_run_does_not_migrate_legacy_state(self) -> None:
        self.claude.mkdir(parents=True)
        legacy = self.claude / "statusline.sh"
        legacy.write_text("#!/bin/sh\n")
        settings = self.claude / "settings.json"
        settings.write_text(json.dumps({"statusLine": {"command": str(legacy)}}))
        manager = ExtrasSettings(self.claude)
        self.assertTrue(manager.mutate("migrate-legacy", dry_run=True))
        self.assertTrue(legacy.exists())
        self.assertIn("statusLine", json.loads(settings.read_text()))

    def test_extras_reject_malformed_settings_without_mutation(self) -> None:
        self.claude.mkdir(parents=True)
        legacy = self.claude / "statusline.sh"
        legacy.write_text("#!/bin/sh\n")
        settings = self.claude / "settings.json"
        settings.write_text("{broken")
        with self.assertRaises(StateError):
            ExtrasSettings(self.claude).mutate("migrate-legacy", dry_run=False)
        self.assertTrue(legacy.exists())
        self.assertEqual("{broken", settings.read_text())


if __name__ == "__main__":
    unittest.main()
