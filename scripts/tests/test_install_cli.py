from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Dict, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[2]
INSTALL = ROOT / "scripts" / "install.sh"
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()


class InstallCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_context = tempfile.TemporaryDirectory(prefix="hukuhaka install cli ")
        self.temp = Path(self.temp_context.name)
        self.bin_dir = self.temp / "bin"
        self.bin_dir.mkdir()
        self.home = self.temp / "home"
        self.home.mkdir()
        self._write_executable(
            "claude",
            """#!/bin/bash
if [ "${1:-}" = "--version" ]; then
    printf 'claude test double\n'
elif [ "${1:-}" = "plugin" ] && [ "${2:-}" = "list" ] && [ "${3:-}" = "--json" ]; then
    config_dir="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
    python3 - "$config_dir" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
installed_path = root / "plugins" / "installed_plugins.json"
settings_path = root / "settings.json"
installed = json.loads(installed_path.read_text()) if installed_path.is_file() else {"plugins": {}}
settings = json.loads(settings_path.read_text()) if settings_path.is_file() else {}
enabled = settings.get("enabledPlugins", {})
plugins = []
for plugin_id, entries in installed.get("plugins", {}).items():
    if not isinstance(entries, list) or not entries:
        continue
    item = dict(entries[0])
    item.update({"id": plugin_id, "enabled": enabled.get(plugin_id) is True})
    plugins.append(item)
print(json.dumps(plugins))
PY
fi
exit 0
""",
        )

    def tearDown(self) -> None:
        self.temp_context.cleanup()

    def _write_executable(self, name: str, content: str) -> Path:
        path = self.bin_dir / name
        path.write_text(content, encoding="utf-8")
        path.chmod(0o755)
        return path

    def _environment(self, **extra: str) -> Dict[str, str]:
        environment = os.environ.copy()
        environment.update(
            {
                "HOME": str(self.home),
                "PATH": "{}:{}".format(self.bin_dir, environment.get("PATH", "")),
            }
        )
        environment.update(extra)
        return environment

    def _run(
        self,
        arguments: Sequence[str],
        *,
        environment: Optional[Dict[str, str]] = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ("/bin/bash", str(INSTALL), "--source-dir", str(ROOT), "--version", VERSION)
            + tuple(arguments),
            cwd=ROOT,
            env=environment or self._environment(),
            text=True,
            capture_output=True,
        )

    def _install_fake_codex(self) -> Tuple[Path, Path]:
        state = self.temp / "codex-state"
        codex_home = self.temp / "codex-home"
        state.mkdir()
        codex_home.mkdir()
        self._write_executable(
            "codex",
            """#!/bin/bash
set -eu
state_dir="${FAKE_CODEX_STATE:?}"
marketplace="$state_dir/marketplace"
plugins="$state_dir/plugins"
touch "$plugins"
if [ "${1:-}" = "--version" ]; then
    printf 'codex fake 0.145.0\n'
elif [ "${1:-}" = "plugin" ] && [ "${2:-}" = "marketplace" ] && [ "${3:-}" = "add" ]; then
    if [ -f "$marketplace" ]; then
        printf '{"alreadyAdded":true}\n'
    else
        : > "$marketplace"
        printf '{"alreadyAdded":false}\n'
    fi
elif [ "${1:-}" = "plugin" ] && [ "${2:-}" = "marketplace" ] && [ "${3:-}" = "list" ]; then
    if [ -f "$marketplace" ]; then
        printf '{"marketplaces":[{"name":"hukuhaka-harness","root":"%s","marketplaceSource":{"sourceType":"local","source":"%s"}}]}\n' "$FAKE_SOURCE_ROOT" "$FAKE_SOURCE_ROOT"
    else
        printf '{"marketplaces":[]}\n'
    fi
elif [ "${1:-}" = "plugin" ] && [ "${2:-}" = "marketplace" ] && [ "${3:-}" = "remove" ]; then
    rm -f "$marketplace"
    printf '{}\n'
elif [ "${1:-}" = "plugin" ] && [ "${2:-}" = "list" ]; then
    first=1
    printf '{"installed":['
    while IFS= read -r name; do
        [ -n "$name" ] || continue
        [ "$first" -eq 1 ] || printf ','
        first=0
        version="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$FAKE_SOURCE_ROOT/marketplace/$name/.codex-plugin/plugin.json")"
        printf '{"name":"%s","marketplaceName":"hukuhaka-harness","pluginId":"%s@hukuhaka-harness","version":"%s"}' "$name" "$name" "$version"
    done < "$plugins"
    printf ']}\n'
elif [ "${1:-}" = "plugin" ] && [ "${2:-}" = "add" ]; then
    name="${3%%@*}"
    version="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$FAKE_SOURCE_ROOT/marketplace/$name/.codex-plugin/plugin.json")"
    cache_root="$CODEX_HOME/plugins/cache/hukuhaka-harness/$name"
    installed="$cache_root/$version"
    rm -rf "$cache_root"
    mkdir -p "$cache_root"
    cp -R "$FAKE_SOURCE_ROOT/marketplace/$name" "$installed"
    if ! grep -Fxq "$name" "$plugins"; then
        printf '%s\n' "$name" >> "$plugins"
    fi
    printf '{"pluginId":"%s@hukuhaka-harness","name":"%s","marketplaceName":"hukuhaka-harness","version":"%s","installedPath":"%s"}\n' "$name" "$name" "$version" "$installed"
elif [ "${1:-}" = "plugin" ] && [ "${2:-}" = "remove" ]; then
    name="${3%%@*}"
    next="$plugins.next"
    grep -Fxv "$name" "$plugins" > "$next" || true
    mv "$next" "$plugins"
    rm -rf "$CODEX_HOME/plugins/cache/hukuhaka-harness/$name"
    printf '{}\n'
else
    printf 'unexpected fake codex args: %s\n' "$*" >&2
    exit 2
fi
""",
        )
        return state, codex_home

    def test_claude_install_reinstall_and_uninstall_through_shell_entrypoint(
        self,
    ) -> None:
        arguments = ("claude", "install", "--recommended", "--yes")
        first = self._run(arguments)
        second = self._run(arguments)

        self.assertEqual(0, first.returncode, first.stderr)
        self.assertEqual(0, second.returncode, second.stderr)
        self.assertRegex(
            first.stdout,
            r"hukuhaka-worklog +not installed → 0\.3\.0",
        )
        self.assertRegex(
            second.stdout,
            r"hukuhaka-worklog +0\.3\.0 \(same version\)",
        )
        manifest_path = self.home / ".claude" / ".hukuhaka-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(VERSION, manifest["version"])
        self.assertEqual(
            {
                "hukuhaka-report-planner",
                "hukuhaka-engineering-plan",
                "hukuhaka-worklog",
                "hukuhaka-codex",
                "claude-md",
            },
            set(manifest["components"]),
        )

        first_remove = self._run(("claude", "uninstall", "--yes"))
        second_remove = self._run(("claude", "uninstall", "--yes"))
        self.assertEqual(0, first_remove.returncode, first_remove.stderr)
        self.assertEqual(0, second_remove.returncode, second_remove.stderr)
        self.assertFalse(manifest_path.exists())

    def test_claude_install_uses_configured_config_dir(self) -> None:
        config_dir = self.temp / "custom claude config"
        result = self._run(
            ("claude", "install", "--recommended", "--yes"),
            environment=self._environment(CLAUDE_CONFIG_DIR=str(config_dir)),
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue((config_dir / ".hukuhaka-manifest.json").is_file())
        self.assertFalse((self.home / ".claude").exists())
        self.assertIn("Run /reload-plugins", result.stdout)

    def test_fake_codex_desired_state_dry_run_and_lifecycle(self) -> None:
        state, codex_home = self._install_fake_codex()
        environment = self._environment(
            CODEX_HOME=str(codex_home),
            FAKE_CODEX_STATE=str(state),
            FAKE_SOURCE_ROOT=str(ROOT),
        )

        dry_run = self._run(
            ("codex", "install", "--recommended", "--dry-run", "--yes"),
            environment=environment,
        )
        self.assertEqual(0, dry_run.returncode, dry_run.stderr)
        self.assertIn("plugin add hukuhaka-report-planner@hukuhaka-harness", dry_run.stdout)
        self.assertIn("plugin add hukuhaka-worklog@hukuhaka-harness", dry_run.stdout)
        self.assertFalse((state / "marketplace").exists())
        self.assertEqual("", (state / "plugins").read_text(encoding="utf-8"))

        recommended = ("codex", "install", "--recommended", "--yes")
        first = self._run(recommended, environment=environment)
        second = self._run(recommended, environment=environment)
        self.assertEqual(0, first.returncode, first.stderr)
        self.assertEqual(0, second.returncode, second.stderr)
        self.assertRegex(
            first.stdout,
            r"hukuhaka-worklog +not installed → 0\.3\.0",
        )
        self.assertRegex(
            second.stdout,
            r"hukuhaka-worklog +0\.3\.0 \(same version\)",
        )
        self.assertEqual(
            {
                "hukuhaka-report-planner",
                "hukuhaka-engineering-plan",
                "hukuhaka-worklog",
            },
            set((state / "plugins").read_text(encoding="utf-8").splitlines()),
        )
        self.assertTrue((codex_home / ".hukuhaka-guidance-manifest.json").is_file())

        reduced = self._run(
            (
                "codex",
                "install",
                "--components",
                "hukuhaka-report-planner",
                "--yes",
            ),
            environment=environment,
        )
        self.assertEqual(0, reduced.returncode, reduced.stderr)
        self.assertEqual(
            ["hukuhaka-report-planner"],
            (state / "plugins").read_text(encoding="utf-8").splitlines(),
        )
        self.assertFalse((codex_home / ".hukuhaka-guidance-manifest.json").exists())

        first_remove = self._run(("codex", "uninstall", "--yes"), environment=environment)
        second_remove = self._run(("codex", "uninstall", "--yes"), environment=environment)
        self.assertEqual(0, first_remove.returncode, first_remove.stderr)
        self.assertEqual(0, second_remove.returncode, second_remove.stderr)
        self.assertEqual("", (state / "plugins").read_text(encoding="utf-8"))

    @unittest.skipUnless(shutil.which("codex"), "codex CLI not available")
    def test_installed_codex_cli_temp_home_lifecycle(self) -> None:
        codex_home = self.temp / "real-codex-home"
        codex_home.mkdir()
        environment = os.environ.copy()
        environment.update({"HOME": str(self.home), "CODEX_HOME": str(codex_home)})
        arguments = ("codex", "install", "--recommended", "--yes")

        first = self._run(arguments, environment=environment)
        second = self._run(arguments, environment=environment)
        first_remove = self._run(("codex", "uninstall", "--yes"), environment=environment)
        second_remove = self._run(("codex", "uninstall", "--yes"), environment=environment)

        self.assertEqual(0, first.returncode, first.stderr)
        self.assertEqual(0, second.returncode, second.stderr)
        self.assertEqual(0, first_remove.returncode, first_remove.stderr)
        self.assertEqual(0, second_remove.returncode, second_remove.stderr)


if __name__ == "__main__":
    unittest.main()
