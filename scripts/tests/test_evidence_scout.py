from __future__ import annotations

import contextlib
import io
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.install.codex import (
    EVIDENCE_SCOUT_MANIFEST,
    CodexEvidenceScoutDeployment,
    CodexInstaller,
)
from scripts.install.codex_config import EVIDENCE_SCOUT_SETTINGS, current_values
from scripts.install.common import DriftError, InstallerError, StateError
from scripts.install.terminal import prompt_install_plan


ROOT = Path(__file__).resolve().parents[2]


MODEL_CACHE = {
    "client_version": "0.147.0",
    "etag": "test-etag",
    "fetched_at": "2026-08-12T00:00:00Z",
    "models": [
        {
            "slug": "gpt-5.6-sol",
            "multi_agent_version": "v2",
            "display_name": "GPT-5.6-Sol",
        },
        {
            "slug": "gpt-5.6-luna",
            "multi_agent_version": "v1",
            "display_name": "GPT-5.6-Luna",
            "supported_reasoning_levels": ["high", "max"],
        },
    ],
}


def write_model_cache(codex_home: Path, payload: object = MODEL_CACHE) -> bytes:
    codex_home.mkdir(parents=True, exist_ok=True)
    content = (json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8")
    (codex_home / "models_cache.json").write_bytes(content)
    return content


class EvidenceScoutDeploymentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="hukuhaka evidence scout ")
        self.codex_home = Path(self.temp.name) / ".codex"
        self.source = ROOT / "agents" / "evidence-scout.toml"
        self.routing = ROOT / "templates" / "evidence-scout-routing.md"
        self.original_cache = write_model_cache(self.codex_home)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def deployment(self, *, force: bool = False) -> CodexEvidenceScoutDeployment:
        return CodexEvidenceScoutDeployment(
            self.source,
            self.routing,
            self.codex_home,
            "1.2.3",
            enabled=True,
            force=force,
        )

    def assert_no_managed_scout_write(self) -> None:
        self.assertFalse((self.codex_home / "agents").exists())
        self.assertFalse((self.codex_home / "AGENTS.md").exists())
        self.assertFalse((self.codex_home / "config.toml").exists())
        self.assertFalse((self.codex_home / "models-luna-v2.json").exists())
        self.assertFalse((self.codex_home / EVIDENCE_SCOUT_MANIFEST).exists())

    def test_install_is_complete_and_idempotent(self) -> None:
        with mock.patch("scripts.install.codex_config.CodexConfigEditor._doctor"):
            self.deployment().deploy()
            first_agents = (self.codex_home / "AGENTS.md").read_bytes()
            first_manifest = (self.codex_home / EVIDENCE_SCOUT_MANIFEST).read_bytes()
            self.deployment().deploy()

        self.assertEqual(
            self.source.read_bytes(),
            (self.codex_home / "agents" / "evidence-scout.toml").read_bytes(),
        )
        self.assertEqual(first_agents, (self.codex_home / "AGENTS.md").read_bytes())
        self.assertEqual(
            first_manifest,
            (self.codex_home / EVIDENCE_SCOUT_MANIFEST).read_bytes(),
        )
        values = current_values(
            (self.codex_home / "config.toml").read_text(encoding="utf-8")
        )
        for key, expected in EVIDENCE_SCOUT_SETTINGS.items():
            self.assertEqual(expected, values[key])
        self.assertEqual(
            json.dumps(str(self.codex_home / "models-luna-v2.json")),
            values[("model_catalog_json",)],
        )

    def test_install_migrates_legacy_agent_limit(self) -> None:
        config = self.codex_home / "config.toml"
        original = (
            "[agents]\n"
            "max_threads = 9 # legacy alias\n"
            'default_subagent_model = "user-model"\n'
        )
        config.write_text(original, encoding="utf-8")

        with mock.patch("scripts.install.codex_config.CodexConfigEditor._doctor"):
            self.deployment().deploy()

        migrated = config.read_text(encoding="utf-8")
        self.assertIn(
            "max_concurrent_threads_per_session = 4 # legacy alias\n",
            migrated,
        )
        self.assertNotIn("\nmax_threads =", migrated)
        self.assertIn('default_subagent_model = "user-model"\n', migrated)
        self.assertEqual(
            original.encode(),
            self.deployment().config.backup.read_bytes(),
        )

    def test_catalog_changes_only_luna_multi_agent_version(self) -> None:
        with mock.patch("scripts.install.codex_config.CodexConfigEditor._doctor"):
            self.deployment().deploy()

        self.assertEqual(
            self.original_cache, (self.codex_home / "models_cache.json").read_bytes()
        )
        source = json.loads(self.original_cache)
        expected = json.loads(self.original_cache)
        luna = [model for model in expected["models"] if model["slug"] == "gpt-5.6-luna"]
        self.assertEqual(1, len(luna))
        luna[0]["multi_agent_version"] = "v2"
        actual = json.loads(
            (self.codex_home / "models-luna-v2.json").read_text(encoding="utf-8")
        )
        self.assertEqual(expected, actual)
        self.assertNotEqual(source, actual)

        config = (self.codex_home / "config.toml").read_text(encoding="utf-8")
        pointer = 'model_catalog_json = {}'.format(
            json.dumps(str(self.codex_home / "models-luna-v2.json"))
        )
        self.assertIn(pointer, config)
        self.assertLess(config.index(pointer), config.index("[features]"))

    def test_invalid_cache_fails_before_any_managed_write(self) -> None:
        (self.codex_home / "models_cache.json").write_text(
            '{"models": []}\n', encoding="utf-8"
        )

        with self.assertRaisesRegex(StateError, "exactly one gpt-5.6-luna"):
            self.deployment().deploy()

        self.assert_no_managed_scout_write()

    def test_malformed_cache_fails_before_any_managed_write(self) -> None:
        (self.codex_home / "models_cache.json").write_text("{\n", encoding="utf-8")

        with self.assertRaisesRegex(StateError, "must contain valid JSON"):
            self.deployment().deploy()

        self.assert_no_managed_scout_write()

    def test_duplicate_luna_cache_fails_before_any_managed_write(self) -> None:
        payload = json.loads(json.dumps(MODEL_CACHE))
        luna = next(
            model for model in payload["models"] if model["slug"] == "gpt-5.6-luna"
        )
        payload["models"].append(dict(luna))
        write_model_cache(self.codex_home, payload)

        with self.assertRaisesRegex(StateError, "exactly one gpt-5.6-luna"):
            self.deployment().deploy()

        self.assert_no_managed_scout_write()

    def test_unsupported_luna_version_fails_before_any_managed_write(self) -> None:
        payload = json.loads(json.dumps(MODEL_CACHE))
        luna = next(
            model for model in payload["models"] if model["slug"] == "gpt-5.6-luna"
        )
        luna["multi_agent_version"] = "v3"
        write_model_cache(self.codex_home, payload)

        with self.assertRaisesRegex(StateError, "unsupported multi_agent_version"):
            self.deployment().deploy()

        self.assert_no_managed_scout_write()

    def test_exact_manual_catalog_is_adopted(self) -> None:
        expected = json.loads(self.original_cache)
        luna = next(
            model for model in expected["models"] if model["slug"] == "gpt-5.6-luna"
        )
        luna["multi_agent_version"] = "v2"
        catalog = self.codex_home / "models-luna-v2.json"
        catalog.write_text(
            json.dumps(expected, indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )

        with mock.patch("scripts.install.codex_config.CodexConfigEditor._doctor"):
            self.deployment().deploy()

        self.assertTrue((self.codex_home / EVIDENCE_SCOUT_MANIFEST).is_file())
        self.assertEqual(expected, json.loads(catalog.read_text(encoding="utf-8")))

    def test_override_warns_without_changing_override(self) -> None:
        override = self.codex_home / "AGENTS.override.md"
        override.write_text("# User override\n", encoding="utf-8")
        stderr = io.StringIO()

        with contextlib.redirect_stderr(stderr), mock.patch(
            "scripts.install.codex_config.CodexConfigEditor._doctor"
        ):
            self.deployment().deploy()

        self.assertIn("shadows global AGENTS.md", stderr.getvalue())
        self.assertIn("routing is inactive", stderr.getvalue())
        self.assertEqual("# User override\n", override.read_text(encoding="utf-8"))

    def test_catalog_drift_requires_force_and_force_repairs_it(self) -> None:
        with mock.patch("scripts.install.codex_config.CodexConfigEditor._doctor"):
            self.deployment().deploy()
        catalog = self.codex_home / "models-luna-v2.json"
        catalog.write_text('{"user":"change"}\n', encoding="utf-8")

        with self.assertRaisesRegex(DriftError, "managed evidence-scout"):
            self.deployment().deploy()
        with mock.patch("scripts.install.codex_config.CodexConfigEditor._doctor"):
            self.deployment(force=True).deploy()

        luna = [
            model
            for model in json.loads(catalog.read_text(encoding="utf-8"))["models"]
            if model["slug"] == "gpt-5.6-luna"
        ]
        self.assertEqual("v2", luna[0]["multi_agent_version"])

    def test_conflicting_model_catalog_pointer_is_preserved_without_force(self) -> None:
        config = self.codex_home / "config.toml"
        original = 'model_catalog_json = "/user/catalog.json"\n'.encode("utf-8")
        config.write_bytes(original)

        with self.assertRaisesRegex(DriftError, "model_catalog_json already points"):
            self.deployment().deploy()

        self.assertEqual(original, config.read_bytes())
        self.assertFalse((self.codex_home / "models-luna-v2.json").exists())
        self.assertFalse((self.codex_home / EVIDENCE_SCOUT_MANIFEST).exists())

    def test_exact_manual_agent_is_adopted(self) -> None:
        target = self.codex_home / "agents" / "evidence-scout.toml"
        target.parent.mkdir(parents=True)
        target.write_bytes(self.source.read_bytes())

        with mock.patch("scripts.install.codex_config.CodexConfigEditor._doctor"):
            self.deployment().deploy()

        self.assertTrue((self.codex_home / EVIDENCE_SCOUT_MANIFEST).is_file())
        self.assertEqual(self.source.read_bytes(), target.read_bytes())

    def test_conflicting_manual_agent_is_preserved_without_force(self) -> None:
        target = self.codex_home / "agents" / "evidence-scout.toml"
        target.parent.mkdir(parents=True)
        target.write_text("user agent\n", encoding="utf-8")

        with self.assertRaisesRegex(DriftError, "unmanaged evidence-scout"):
            self.deployment().deploy()

        self.assertEqual("user agent\n", target.read_text(encoding="utf-8"))
        self.assertFalse((self.codex_home / EVIDENCE_SCOUT_MANIFEST).exists())

    def test_force_repairs_managed_agent_and_routing_drift(self) -> None:
        with mock.patch("scripts.install.codex_config.CodexConfigEditor._doctor"):
            self.deployment().deploy()
        target = self.codex_home / "agents" / "evidence-scout.toml"
        target.write_text("changed\n", encoding="utf-8")
        agents = self.codex_home / "AGENTS.md"
        agents.write_bytes(agents.read_bytes().replace(b"dynamic", b"altered", 1))

        with self.assertRaisesRegex(DriftError, "managed evidence-scout"):
            self.deployment().deploy()
        with mock.patch("scripts.install.codex_config.CodexConfigEditor._doctor"):
            self.deployment(force=True).deploy()

        self.assertEqual(self.source.read_bytes(), target.read_bytes())
        self.assertIn(self.routing.read_bytes().rstrip(), agents.read_bytes())

    def test_validation_failure_rolls_back_agent_routing_and_config(self) -> None:
        self.codex_home.mkdir(parents=True, exist_ok=True)
        agents = self.codex_home / "AGENTS.md"
        config = self.codex_home / "config.toml"
        agents.write_text("# User guidance\n", encoding="utf-8")
        config.write_text('model = "user-model"\n', encoding="utf-8")
        original_agents = agents.read_bytes()
        original_config = config.read_bytes()

        with mock.patch(
            "scripts.install.codex_config.CodexConfigEditor._doctor",
            side_effect=InstallerError("injected doctor failure"),
        ):
            with self.assertRaisesRegex(InstallerError, "injected doctor failure"):
                self.deployment().deploy()

        self.assertEqual(original_agents, agents.read_bytes())
        self.assertEqual(original_config, config.read_bytes())
        self.assertFalse((self.codex_home / "agents" / "evidence-scout.toml").exists())
        self.assertFalse((self.codex_home / EVIDENCE_SCOUT_MANIFEST).exists())
        self.assertFalse((self.codex_home / "models-luna-v2.json").exists())

    def test_uninstall_removes_only_managed_agent_and_routing(self) -> None:
        self.codex_home.mkdir(parents=True, exist_ok=True)
        agents = self.codex_home / "AGENTS.md"
        agents.write_text("# User guidance\n", encoding="utf-8")
        agents.chmod(0o640)
        with mock.patch("scripts.install.codex_config.CodexConfigEditor._doctor"):
            self.deployment().deploy()
        configured = (self.codex_home / "config.toml").read_bytes()
        configured_catalog = (self.codex_home / "models-luna-v2.json").read_bytes()

        CodexEvidenceScoutDeployment(
            self.source,
            self.routing,
            self.codex_home,
            "1.2.3",
            enabled=False,
        ).uninstall()

        self.assertEqual("# User guidance\n", agents.read_text(encoding="utf-8"))
        self.assertEqual(0o640, stat.S_IMODE(agents.stat().st_mode))
        self.assertFalse((self.codex_home / "agents" / "evidence-scout.toml").exists())
        self.assertFalse((self.codex_home / EVIDENCE_SCOUT_MANIFEST).exists())
        self.assertEqual(configured, (self.codex_home / "config.toml").read_bytes())
        self.assertEqual(
            configured_catalog,
            (self.codex_home / "models-luna-v2.json").read_bytes(),
        )


class EvidenceScoutInstallerIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="hukuhaka evidence integration ")
        self.codex_home = Path(self.temp.name) / ".codex"
        self.catalog = json.loads((ROOT / "components.json").read_text(encoding="utf-8"))
        self.environment = mock.patch.dict(
            os.environ, {"CODEX_HOME": str(self.codex_home)}
        )
        self.environment.start()
        write_model_cache(self.codex_home)

    def tearDown(self) -> None:
        self.environment.stop()
        self.temp.cleanup()

    def test_installer_tracks_and_removes_evidence_scout_component(self) -> None:
        installer = CodexInstaller(ROOT, self.catalog, "1.2.3", local_source=True)
        with mock.patch("scripts.install.codex.shutil.which", return_value="/fake/codex"), mock.patch(
            "scripts.install.codex.run_json", return_value={"installed": []}
        ), mock.patch("scripts.install.codex_config.CodexConfigEditor._doctor"):
            installer.install(["evidence-scout"])
            self.assertEqual({"evidence-scout"}, installer.current_components())
            installer.uninstall()
            self.assertEqual(set(), installer.current_components())

    def test_reset_reinstalls_scout_and_preserves_runtime_catalog(self) -> None:
        installer = CodexInstaller(ROOT, self.catalog, "1.2.3", local_source=True)
        source_cache = (self.codex_home / "models_cache.json").read_bytes()
        with mock.patch(
            "scripts.install.codex.shutil.which", return_value="/fake/codex"
        ), mock.patch(
            "scripts.install.codex.run_json", return_value={"installed": []}
        ), mock.patch(
            "scripts.install.codex_config.CodexConfigEditor._doctor"
        ):
            installer.install(["evidence-scout"])
            configured = (self.codex_home / "config.toml").read_bytes()
            catalog = (self.codex_home / "models-luna-v2.json").read_bytes()
            installer.install(["evidence-scout"], reset=True)

        self.assertTrue((self.codex_home / "agents" / "evidence-scout.toml").is_file())
        self.assertTrue((self.codex_home / EVIDENCE_SCOUT_MANIFEST).is_file())
        self.assertEqual(
            source_cache, (self.codex_home / "models_cache.json").read_bytes()
        )
        self.assertEqual(catalog, (self.codex_home / "models-luna-v2.json").read_bytes())
        self.assertEqual(configured, (self.codex_home / "config.toml").read_bytes())

    def test_interactive_row_names_the_runtime_contract(self) -> None:
        output = io.StringIO()
        plans = prompt_install_plan(
            io.StringIO(),
            output,
            sections=[
                {
                    "host": "codex",
                    "label": "Codex",
                    "version": "0.147.0",
                    "components": [
                        {
                            "name": "evidence-scout",
                            "kind": "agent",
                            "description": "Luna max read-only evidence scout with dynamic routing",
                            "default": True,
                            "lifecycle": "supported",
                        }
                    ],
                    "selected": {"evidence-scout"},
                }
            ],
            keys=["exit"],
        )

        self.assertEqual([], plans)
        rendered = output.getvalue()
        self.assertIn("[x] evidence-scout", rendered)
        self.assertIn("agent: Luna max read-only evidence scout with dynamic routing", rendered)
        self.assertNotIn("optional", rendered)


if __name__ == "__main__":
    unittest.main()
