from __future__ import annotations

import unittest
from pathlib import Path
from official_docs_source_loader import read_official_docs_mixin_source, read_official_docs_page_source


class OfficialDocsRuntimeErrorLabelVisibilityWiringTests(unittest.TestCase):
    def test_error_label_hidden_by_default(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_page_source(repo_root)
        self.assertIn("settings_error_label.setVisible(False)", text)

    def test_mixin_uses_show_hide_message_helper(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_mixin_source(repo_root)
        self.assertIn("def _set_official_docs_settings_message(self, text: str) -> None:", text)
        self.assertIn("label.setVisible(bool(message))", text)
        self.assertIn("self._set_official_docs_settings_message(\"\")", text)


if __name__ == "__main__":
    unittest.main()
