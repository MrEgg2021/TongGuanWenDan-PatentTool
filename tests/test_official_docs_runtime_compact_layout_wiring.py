from __future__ import annotations

import unittest
from pathlib import Path
from tests.official_docs_source_loader import read_official_docs_page_source


class OfficialDocsRuntimeCompactLayoutWiringTests(unittest.TestCase):
    def test_runtime_uses_single_row_for_summary_and_archive_dirs(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_page_source(repo_root)
        self.assertIn("dirs_row = QHBoxLayout()", text)
        self.assertIn("dirs_row.addLayout(summary_row, 1)", text)
        self.assertIn("dirs_row.addLayout(archive_row, 1)", text)
        self.assertIn("runtime_layout.addLayout(dirs_row, 3, 0, 1, 2)", text)

    def test_save_button_is_in_runtime_area_not_bottom_row(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_page_source(repo_root)
        self.assertIn("btn_save_settings.setProperty(\"officialDocsBigSave\", True)", text)
        self.assertIn("btn_save_settings.setMinimumHeight(36)", text)
        self.assertIn("runtime_layout.addWidget(btn_save_settings, 0, 1, 2, 1", text)
        self.assertNotIn("save_row = QHBoxLayout()", text)


if __name__ == "__main__":
    unittest.main()
