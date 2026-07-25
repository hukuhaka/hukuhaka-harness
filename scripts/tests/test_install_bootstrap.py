from __future__ import annotations

import io
import os
import shutil
import shlex
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path
from typing import List, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[2]


class InstallBootstrapTests(unittest.TestCase):
    def run_bootstrap(
        self,
        arguments: Sequence[str],
    ) -> Tuple[subprocess.CompletedProcess[str], List[str], str]:
        with tempfile.TemporaryDirectory() as temp_name:
            temp = Path(temp_name)
            source = temp / "source"
            script = source / "scripts" / "install.sh"
            runtime = source / "scripts" / "install" / "main.py"
            runtime.parent.mkdir(parents=True)
            shutil.copy2(ROOT / "scripts" / "install.sh", script)
            runtime.write_text("", encoding="utf-8")
            (source / "components.json").write_text("{}\n", encoding="utf-8")
            (source / "VERSION").write_text("1.1.1\n", encoding="utf-8")

            fake_bin = temp / "bin"
            fake_bin.mkdir()
            invocation_log = temp / "python-invocations.log"
            fake_python = fake_bin / "python3"
            fake_python.write_text(
                """#!/bin/bash
set -eu
if [ "${1:-}" = "-c" ]; then
    exit 0
fi
{
    printf '%s\\n' __CALL__
    printf '%s\\n' "$@"
} >> "$BOOTSTRAP_LOG"
""",
                encoding="utf-8",
            )
            fake_python.chmod(0o755)

            env = os.environ.copy()
            env["PATH"] = "{}:{}".format(fake_bin, env.get("PATH", ""))
            env["HOME"] = str(temp / "home")
            env["BOOTSTRAP_LOG"] = str(invocation_log)
            result = subprocess.run(
                ("/bin/bash", str(script)) + tuple(arguments),
                cwd=temp,
                env=env,
                text=True,
                capture_output=True,
            )
            calls = (
                invocation_log.read_text(encoding="utf-8").splitlines()
                if invocation_log.is_file()
                else []
            )
            return result, calls, str(source.resolve())

    def run_remote_bootstrap(self) -> Tuple[subprocess.CompletedProcess[str], Path, List[str]]:
        temp_context = tempfile.TemporaryDirectory()
        self.addCleanup(temp_context.cleanup)
        temp = Path(temp_context.name)
        version = "1.1.1"
        archive_root = "hukuhaka-harness-{}".format(version)
        archive = temp / "release.tar.gz"
        public_sources = (
            ROOT / ".agents",
            ROOT / "marketplace",
            ROOT / "templates",
            ROOT / "components.json",
            ROOT / "scripts" / "install",
        )
        with tarfile.open(archive, "w:gz") as handle:
            for source in public_sources:
                relative = source.relative_to(ROOT)
                handle.add(source, arcname="{}/{}".format(archive_root, relative.as_posix()))
            version_bytes = (version + "\n").encode("utf-8")
            version_info = tarfile.TarInfo("{}/VERSION".format(archive_root))
            version_info.size = len(version_bytes)
            version_info.mode = 0o644
            handle.addfile(version_info, io.BytesIO(version_bytes))

        fake_bin = temp / "bin"
        fake_bin.mkdir()
        fake_curl = fake_bin / "curl"
        fake_curl.write_text(
            """#!/bin/bash
set -eu
output=""
url=""
while [ "$#" -gt 0 ]; do
    case "$1" in
        -o)
            output="$2"
            shift 2
            ;;
        -*)
            shift
            ;;
        *)
            url="$1"
            shift
            ;;
    esac
done
case "$url" in
    */releases/latest)
        printf '{"tag_name":"v%s"}\\n' "$BOOTSTRAP_VERSION"
        ;;
    */archive/refs/tags/v*.tar.gz)
        cp "$BOOTSTRAP_ARCHIVE" "$output"
        ;;
    *)
        printf 'unexpected curl URL: %s\\n' "$url" >&2
        exit 2
        ;;
esac
""",
            encoding="utf-8",
        )
        fake_curl.chmod(0o755)

        python_log = temp / "python.log"
        actual_python = shutil.which("python3")
        self.assertIsNotNone(actual_python)
        fake_python = fake_bin / "python3"
        fake_python.write_text(
            """#!/bin/bash
printf '%s ' "$@" >> "$BOOTSTRAP_PYTHON_LOG"
printf '\\n' >> "$BOOTSTRAP_PYTHON_LOG"
exec {} "$@"
""".format(shlex.quote(str(actual_python))),
            encoding="utf-8",
        )
        fake_python.chmod(0o755)

        fake_claude = fake_bin / "claude"
        fake_claude.write_text(
            """#!/bin/bash
if [ "${1:-}" = "--version" ]; then
    printf 'claude bootstrap test double\\n'
fi
exit 0
""",
            encoding="utf-8",
        )
        fake_claude.chmod(0o755)

        home = temp / "home"
        home.mkdir()
        env = os.environ.copy()
        env.update(
            {
                "PATH": "{}:{}".format(fake_bin, env.get("PATH", "")),
                "HOME": str(home),
                "BOOTSTRAP_ARCHIVE": str(archive),
                "BOOTSTRAP_VERSION": version,
                "BOOTSTRAP_PYTHON_LOG": str(python_log),
            }
        )
        script_text = (ROOT / "scripts" / "install.sh").read_text(encoding="utf-8")
        result = subprocess.run(
            ("/bin/bash", "-c", script_text),
            cwd=temp,
            env=env,
            text=True,
            capture_output=True,
        )
        calls = (
            python_log.read_text(encoding="utf-8").splitlines()
            if python_log.is_file()
            else []
        )
        return result, home, calls

    def test_zero_arguments_forward_once_without_bash_32_nounset_failure(self) -> None:
        result, calls, source = self.run_bootstrap(())

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertNotIn("unbound variable", result.stderr)
        self.assertEqual(
            [
                "__CALL__",
                "-m",
                "scripts.install.main",
                "--repo-root",
                source,
                "--resolved-version",
                "1.1.1",
                "--local-source",
            ],
            calls,
        )

    def test_user_arguments_are_forwarded_once_and_unchanged(self) -> None:
        user_arguments = (
            "--host",
            "codex",
            "--components",
            "alpha,beta",
            "--dry-run",
        )
        result, calls, source = self.run_bootstrap(user_arguments)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            [
                "__CALL__",
                "-m",
                "scripts.install.main",
                "--repo-root",
                source,
                "--resolved-version",
                "1.1.1",
                "--local-source",
            ]
            + list(user_arguments),
            calls,
        )

    def test_remote_zero_argument_bootstrap_downloads_and_installs_once(self) -> None:
        result, home, calls = self.run_remote_bootstrap()

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("Downloading hukuhaka-harness v1.1.1...", result.stdout)
        self.assertNotIn("unbound variable", result.stderr)
        runtime_calls = [line for line in calls if "-m scripts.install.main" in line]
        self.assertEqual(1, len(runtime_calls), calls)
        manifest = home / ".claude" / ".hukuhaka-manifest.json"
        self.assertTrue(manifest.is_file(), result.stdout)
        self.assertIn('"version": "1.1.1"', manifest.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
