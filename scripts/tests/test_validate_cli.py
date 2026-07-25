from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class ValidateCliTests(unittest.TestCase):
    def test_invalid_arguments_exit_two_without_running_validation(self) -> None:
        result = subprocess.run(
            (str(ROOT / "scripts" / "validate.sh"), "--unknown"),
            cwd=ROOT,
            text=True,
            capture_output=True,
        )

        self.assertEqual(2, result.returncode)
        self.assertIn("Usage:", result.stderr)

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
