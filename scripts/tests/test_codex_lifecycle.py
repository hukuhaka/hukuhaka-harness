from __future__ import annotations

import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List, Sequence
from unittest import mock

from scripts.install.codex import CodexInstaller
from scripts.install.common import InstallerError


ROOT = Path(__file__).resolve().parents[2]


class FakeCodex:
    def __init__(self) -> None:
        self.plugins = []  # type: List[Dict[str, str]]
        self.marketplace = False
        self.calls = []  # type: List[Sequence[str]]
        self.fail_add = ""

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
            self.marketplace = True
            return {"alreadyAdded": False}
        if words == ("plugin", "marketplace", "list"):
            return {
                "marketplaces": (
                    [
                        {
                            "name": "hukuhaka-harness",
                            "marketplaceSource": {
                                "sourceType": "github",
                                "source": "hukuhaka/hukuhaka-harness",
                            },
                            "root": "/tmp/fake-marketplace",
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
            self.plugins = [plugin for plugin in self.plugins if plugin["name"] != name]
            self.installed(name)
            return {}
        if words[:2] == ("plugin", "remove"):
            plugin_id = words[2]
            self.plugins = [
                plugin for plugin in self.plugins if plugin["pluginId"] != plugin_id
            ]
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

    def installer(self, *, local_source: bool = False) -> CodexInstaller:
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
        self.assertTrue((self.codex_home / "AGENTS.md").is_file())

    def test_remote_marketplace_is_pinned_to_the_resolved_release(self) -> None:
        self.installer().install(["hukuhaka-report-planner"])

        add = next(
            command
            for command in self.fake.calls
            if command[1:4] == ("plugin", "marketplace", "add")
        )
        self.assertEqual(("--ref", "v1.2.3"), add[-2:])

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
