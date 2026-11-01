from __future__ import annotations

import unittest
from pathlib import Path
from gui_source_loader import read_official_docs_dialogs_source


class OfficialDocsDoneDialogFilterSearchTests(unittest.TestCase):
    def test_done_dialog_uses_single_select_status_filter(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_dialogs_source(repo_root)
        self.assertIn("status_group.setExclusive(True)", text)
        self.assertIn('filter_state = {"status": "all", "query": ""}', text)
        self.assertIn('if status_filter != "all"', text)

    def test_done_dialog_search_supports_pinyin_matching(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_dialogs_source(repo_root)
        self.assertIn("get_pinyin_full(source_zip)", text)
        self.assertIn("get_pinyin_initials(source_zip)", text)
        self.assertIn("get_pinyin_full(output_name)", text)
        self.assertIn("get_pinyin_initials(output_name)", text)
        self.assertIn("return any(query in item for item in lowered)", text)


if __name__ == "__main__":
    unittest.main()
