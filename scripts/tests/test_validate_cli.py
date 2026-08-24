from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class ValidateCliTests(unittest.TestCase):
    def test_official_refresh_tracks_current_codex_index_and_prunes_generated_stale_docs(self) -> None:
        script_path = ROOT / "scripts" / "maintenance" / "refresh-officials.sh"
        if not script_path.is_file():
            self.skipTest("private official-docs refresh script is not in the public checkout")
        script = script_path.read_text(encoding="utf-8")

        self.assertIn('LLMS_URL="https://learn.chatgpt.com/docs/llms.txt"', script)
        self.assertIn("https://learn\\.chatgpt\\.com/docs/", script)
        self.assertIn("prune_stale_docs", script)
        self.assertIn('-path "$DEST/openai" -prune', script)

    def test_validation_probes_do_not_pipe_into_early_exit_consumers(self) -> None:
        script = (ROOT / "scripts" / "validate.sh").read_text(encoding="utf-8")

        self.assertNotIn("| grep -q", script)
        self.assertNotIn("| head -1", script)

    def test_invalid_arguments_exit_two_without_running_validation(self) -> None:
        result = subprocess.run(
            (str(ROOT / "scripts" / "validate.sh"), "--unknown"),
            cwd=ROOT,
            text=True,
            capture_output=True,
        )

        self.assertEqual(2, result.returncode)
        self.assertIn("Usage:", result.stderr)

    def test_invalid_profile_exits_two_without_running_validation(self) -> None:
        result = subprocess.run(
            (str(ROOT / "scripts" / "validate.sh"), "--profile", "unknown"),
            cwd=ROOT,
            text=True,
            capture_output=True,
        )

        self.assertEqual(2, result.returncode)
        self.assertIn("profile must be private or public", result.stderr)

    def test_release_mode_is_rejected_in_public_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            script = root / "scripts" / "validate.sh"
            script.parent.mkdir()
            shutil.copy2(ROOT / "scripts" / "validate.sh", script)
            result = subprocess.run(
                (str(script), "--release", "v1.1.1"),
                cwd=root,
                text=True,
                capture_output=True,
            )

        self.assertEqual(2, result.returncode)
        self.assertIn("private source checkout", result.stderr)


if __name__ == "__main__":
    unittest.main()
