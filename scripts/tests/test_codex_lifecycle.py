from __future__ import annotations

import copy
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence
from unittest import mock

from scripts.install.codex import REMOTE_MARKETPLACE_SOURCE, CodexInstaller
from scripts.install.common import InstallerError


ROOT = Path(__file__).resolve().parents[2]


class FakeCodex:
    def __init__(self) -> None:
        self.plugins = []  # type: List[Dict[str, str]]
        self.marketplace = False
        self.marketplace_source_type = ""
        self.marketplace_source = ""
        self.marketplace_root = ""
        self.marketplace_commit = ""
        self.marketplace_refs = {}  # type: Dict[str, str]
        self.fail_marketplace_refs = set()  # type: set[str]
        self.calls = []  # type: List[Sequence[str]]
        self.fail_add = ""

    def remote_marketplace(self, commit: str, *, ref: str = "v1.1.6") -> None:
        self.marketplace = True
        self.marketplace_source_type = "git"
        self.marketplace_source = REMOTE_MARKETPLACE_SOURCE
        self.marketplace_root = "/tmp/fake-marketplace"
        self.marketplace_commit = commit
        self.marketplace_refs[ref] = commit

    def git_commit(self, _root: Path, ref: str) -> Optional[str]:
        if not self.marketplace:
            return None
        if ref == "HEAD":
            return self.marketplace_commit or None
        suffix = "^{commit}"
        return self.marketplace_refs.get(
            ref[: -len(suffix)] if ref.endswith(suffix) else ref
        )

    def installed(self, name: str) -> None:
        self.plugins.append(
            {
                "name": name,
                "marketplaceName": "hukuhaka-harness",
                "pluginId": "{}@hukuhaka-harness".format(name),
            }
        )

    def run_json(self, command: Sequence[str], *, stage: str) -> Dict[str, Any]:
        self.calls.append(tuple(command))
        words = tuple(command[1:-1])
        if words == ("plugin", "list"):
            return {"installed": copy.deepcopy(self.plugins)}
        if words[:3] == ("plugin", "marketplace", "add"):
            ref = words[words.index("--ref") + 1] if "--ref" in words else ""
            if ref in self.fail_marketplace_refs:
                raise InstallerError("injected marketplace add failure for {}".format(ref))
            self.marketplace = True
            source = words[3]
            if source.startswith("/"):
                self.marketplace_source_type = "local"
                self.marketplace_source = source
                self.marketplace_root = source
            else:
                self.marketplace_source_type = "git"
                self.marketplace_source = REMOTE_MARKETPLACE_SOURCE
                self.marketplace_root = "/tmp/fake-marketplace"
                self.marketplace_commit = ref
                self.marketplace_refs[ref] = ref
            return {"alreadyAdded": False}
        if words == ("plugin", "marketplace", "list"):
            return {
                "marketplaces": (
                    [
                        {
                            "name": "hukuhaka-harness",
                            "marketplaceSource": {
                                "sourceType": self.marketplace_source_type,
                                "source": self.marketplace_source,
                            },
                            "root": self.marketplace_root,
                        }
                    ]
                    if self.marketplace
                    else []
                )
            }
        if words[:2] == ("plugin", "add"):
            name = words[2].split("@", 1)[0]
            if name == self.fail_add:
                raise InstallerError("injected plugin add failure")
            source = ROOT / "marketplace" / name
            metadata = json.loads(
                (source / ".codex-plugin" / "plugin.json").read_text(
                    encoding="utf-8"
                )
            )
            version = str(metadata["version"])
            cache_root = (
                Path(os.environ["CODEX_HOME"])
                / "plugins"
                / "cache"
                / "hukuhaka-harness"
                / name
            )
            shutil.rmtree(cache_root, ignore_errors=True)
            installed_path = cache_root / version
            shutil.copytree(source, installed_path)
            self.plugins = [plugin for plugin in self.plugins if plugin["name"] != name]
            result = {
                "name": name,
                "marketplaceName": "hukuhaka-harness",
                "pluginId": "{}@hukuhaka-harness".format(name),
                "version": version,
                "installedPath": str(installed_path),
            }
            self.plugins.append(dict(result))
            return result
        if words[:2] == ("plugin", "remove"):
            plugin_id = words[2]
            name = plugin_id.split("@", 1)[0]
            self.plugins = [
                plugin for plugin in self.plugins if plugin["pluginId"] != plugin_id
            ]
            shutil.rmtree(
                Path(os.environ["CODEX_HOME"])
                / "plugins"
                / "cache"
                / "hukuhaka-harness"
                / name,
                ignore_errors=True,
            )
            return {}
        if words[:3] == ("plugin", "marketplace", "remove"):
            self.marketplace = False
            return {}
        raise AssertionError("unexpected command at {}: {}".format(stage, command))


class CodexLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="hukuhaka codex lifecycle ")
        self.codex_home = Path(self.temp.name) / ".codex"
        self.catalog = json.loads((ROOT / "components.json").read_text(encoding="utf-8"))
        self.catalog["components"][0]["aliases"] = ["old-report-planner"]
        self.fake = FakeCodex()
        self.environment = mock.patch.dict(
            os.environ, {"CODEX_HOME": str(self.codex_home)}
        )
        self.environment.start()
        self.which = mock.patch(
            "scripts.install.codex.shutil.which", return_value="/fake/codex"
        )
        self.which.start()
        self.runner = mock.patch(
            "scripts.install.codex.run_json", side_effect=self.fake.run_json
        )
        self.runner.start()

    def tearDown(self) -> None:
        self.runner.stop()
        self.which.stop()
        self.environment.stop()
        self.temp.cleanup()

    def installer(self, *, local_source: bool = True) -> CodexInstaller:
        return CodexInstaller(
            ROOT,
            self.catalog,
            "1.2.3",
            local_source=local_source,
        )

    def test_exact_desired_state_adds_canonical_before_removing_alias_and_omitted(self) -> None:
        self.fake.installed("old-report-planner")
        self.fake.installed("hukuhaka-engineering-plan")

        self.installer().install(["hukuhaka-report-planner", "agents-md"])

        names = {plugin["name"] for plugin in self.fake.plugins}
        self.assertEqual({"hukuhaka-report-planner"}, names)
        add_index = next(
            index
            for index, command in enumerate(self.fake.calls)
            if command[1:3] == ("plugin", "add")
        )
        remove_indices = [
            index
            for index, command in enumerate(self.fake.calls)
            if command[1:3] == ("plugin", "remove")
        ]
        self.assertTrue(remove_indices)
        self.assertLess(add_index, min(remove_indices))
        agents_path = self.codex_home / "AGENTS.md"
        self.assertTrue(agents_path.is_file())
        self.assertIn("## Handle User Challenges", agents_path.read_text())

    def test_remote_marketplace_is_pinned_to_the_resolved_release(self) -> None:
        with mock.patch("scripts.install.codex.git_commit", return_value="target"):
            self.installer(local_source=False).install(["hukuhaka-report-planner"])

        add = next(
            command
            for command in self.fake.calls
            if command[1:4] == ("plugin", "marketplace", "add")
        )
        self.assertEqual(("--ref", "v1.2.3"), add[-3:-1])

    def test_remote_marketplace_old_ref_is_replaced_before_plugin_install(self) -> None:
        self.fake.remote_marketplace("old-commit")

        with mock.patch(
            "scripts.install.codex.git_commit", side_effect=self.fake.git_commit
        ):
            installer = self.installer(local_source=False)
            installer.install(["hukuhaka-report-planner"])

        self.assertEqual("v1.2.3", self.fake.marketplace_commit)
        remove_index = next(
            index
            for index, command in enumerate(self.fake.calls)
            if command[1:4] == ("plugin", "marketplace", "remove")
        )
        marketplace_add_index = next(
            index
            for index, command in enumerate(self.fake.calls)
            if command[1:4] == ("plugin", "marketplace", "add")
        )
        plugin_add_index = next(
            index
            for index, command in enumerate(self.fake.calls)
            if command[1:3] == ("plugin", "add")
        )
        self.assertLess(remove_index, marketplace_add_index)
        self.assertLess(marketplace_add_index, plugin_add_index)
        self.assertIn("updated marketplace to v1.2.3", installer.completed)

    def test_remote_marketplace_target_ref_is_reused(self) -> None:
        self.fake.remote_marketplace("target-commit", ref="v1.2.3")

        with mock.patch(
            "scripts.install.codex.git_commit", side_effect=self.fake.git_commit
        ):
            self.installer(local_source=False).install(["hukuhaka-report-planner"])

        marketplace_mutations = [
            command
            for command in self.fake.calls
            if command[1:4]
            in (
                ("plugin", "marketplace", "add"),
                ("plugin", "marketplace", "remove"),
            )
        ]
        self.assertEqual([], marketplace_mutations)

    def test_remote_marketplace_update_failure_restores_old_commit(self) -> None:
        self.fake.remote_marketplace("old-commit")
        self.fake.fail_marketplace_refs.add("v1.2.3")

        with mock.patch(
            "scripts.install.codex.git_commit", side_effect=self.fake.git_commit
        ):
            installer = self.installer(local_source=False)
            with self.assertRaisesRegex(InstallerError, "restored previous revision"):
                installer.install(["hukuhaka-report-planner"])

        self.assertTrue(self.fake.marketplace)
        self.assertEqual("old-commit", self.fake.marketplace_commit)
        self.assertEqual([], installer.completed)

    def test_remote_marketplace_rollback_failure_is_partial(self) -> None:
        self.fake.remote_marketplace("old-commit")
        self.fake.fail_marketplace_refs.update(("v1.2.3", "old-commit"))

        with mock.patch(
            "scripts.install.codex.git_commit", side_effect=self.fake.git_commit
        ):
            installer = self.installer(local_source=False)
            with self.assertRaisesRegex(InstallerError, "rollback failed"):
                installer.install(["hukuhaka-report-planner"])

        self.assertFalse(self.fake.marketplace)
        self.assertIn("marketplace update incomplete", installer.completed)

    def test_remote_marketplace_foreign_source_is_preserved(self) -> None:
        self.fake.remote_marketplace("foreign-commit")
        self.fake.marketplace_source = "https://github.com/example/fork.git"

        installer = self.installer(local_source=False)
        with self.assertRaisesRegex(InstallerError, "different source"):
            installer.install(["hukuhaka-report-planner"])

        self.assertTrue(self.fake.marketplace)
        self.assertFalse(
            any(
                command[1:4] == ("plugin", "marketplace", "remove")
                for command in self.fake.calls
            )
        )

    def test_remote_marketplace_without_head_is_preserved(self) -> None:
        self.fake.remote_marketplace("")

        with mock.patch(
            "scripts.install.codex.git_commit", side_effect=self.fake.git_commit
        ):
            with self.assertRaisesRegex(InstallerError, "cannot snapshot"):
                self.installer(local_source=False).install(
                    ["hukuhaka-report-planner"]
                )

        self.assertTrue(self.fake.marketplace)
        self.assertFalse(
            any(
                command[1:4] == ("plugin", "marketplace", "remove")
                for command in self.fake.calls
            )
        )

    def test_canonical_add_failure_preserves_existing_alias(self) -> None:
        self.fake.installed("old-report-planner")
        self.fake.fail_add = "hukuhaka-report-planner"

        with self.assertRaisesRegex(InstallerError, "injected plugin add failure"):
            self.installer().install(["hukuhaka-report-planner"])

        self.assertEqual(["old-report-planner"], [p["name"] for p in self.fake.plugins])
        self.assertFalse(
            any(command[1:3] == ("plugin", "remove") for command in self.fake.calls)
        )

    def test_missing_codex_cli_is_a_failure(self) -> None:
        with mock.patch("scripts.install.codex.shutil.which", return_value=None):
            with self.assertRaisesRegex(InstallerError, "codex CLI is required"):
                self.installer().uninstall()

    def test_reset_and_uninstall_do_not_touch_global_config(self) -> None:
        self.codex_home.mkdir(parents=True)
        config = self.codex_home / "config.toml"
        config.write_text('model = "user-choice"\n', encoding="utf-8")
        original = config.read_bytes()
        self.fake.installed("hukuhaka-report-planner")
        self.fake.marketplace = True

        self.installer().install(
            ["hukuhaka-engineering-plan"],
            reset=True,
            include_template=True,
        )
        self.assertEqual(original, config.read_bytes())
        self.installer().uninstall()
        self.assertEqual(original, config.read_bytes())


if __name__ == "__main__":
    unittest.main()
