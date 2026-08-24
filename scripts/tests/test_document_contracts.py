from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).with_name("document_contracts.py")
SPEC = importlib.util.spec_from_file_location("document_contracts", MODULE_PATH)
assert SPEC and SPEC.loader
document_contracts = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(document_contracts)


class DocumentLinkTests(unittest.TestCase):
    def test_non_git_public_candidate_uses_all_markdown_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            source = root / "README.md"
            nested = root / "marketplace" / "plugin" / "README.md"
            nested.parent.mkdir(parents=True)
            source.write_text("# Root\n", encoding="utf-8")
            nested.write_text("# Plugin\n", encoding="utf-8")

            self.assertEqual([source, nested], document_contracts.tracked_markdown(root))

    def test_reports_missing_target_and_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            source = root / "README.md"
            target = root / "guide.md"
            source.write_text("[missing](none.md) [anchor](guide.md#absent)\n", encoding="utf-8")
            target.write_text("# Present\n", encoding="utf-8")
            with mock.patch.object(document_contracts, "tracked_markdown", return_value=[source, target]):
                errors = document_contracts.validate_links(root)
            self.assertTrue(any("missing link target" in error for error in errors))
            self.assertTrue(any("missing anchor" in error for error in errors))

    def test_accepts_existing_relative_target_and_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            source = root / "README.md"
            target = root / "guide.md"
            source.write_text("[guide](guide.md#current-contract)\n", encoding="utf-8")
            target.write_text("## Current contract\n", encoding="utf-8")
            with mock.patch.object(document_contracts, "tracked_markdown", return_value=[source, target]):
                self.assertEqual([], document_contracts.validate_links(root))


if __name__ == "__main__":
    unittest.main()
