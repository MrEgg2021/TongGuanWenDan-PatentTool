from __future__ import annotations

import unittest
from pathlib import Path

from gui_source_loader import read_official_docs_dialogs_source


class OfficialDocsDoneDialogInteractionsWiringTests(unittest.TestCase):
    def test_done_dialog_has_search_status_filter_and_two_open_buttons(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_dialogs_source(repo_root)
        self.assertIn("dialog.setSizeGripEnabled(True)", text)
        self.assertIn('(\"all\", \"总数\", total)', text)
        self.assertIn('(\"success\", \"成功\", success)', text)
        self.assertIn('(\"skip\", \"跳过\", skipped)', text)
        self.assertIn('(\"fail\", \"失败\", failed)', text)
        self.assertIn('search_edit.setPlaceholderText(\"搜索（名称/路径/状态/拼音）\")', text)
        self.assertIn('btn_open_run_dir = QPushButton(\"打开处理目录\")', text)
        self.assertIn('btn_open_selected = QPushButton(\"打开选中文件\")', text)
        self.assertIn("result_table = QTableWidget(0, 2)", text)
        self.assertIn('result_table.setHorizontalHeaderLabels([\"源ZIP路径\", \"处理后PDF文件名\"])', text)
        self.assertIn("result_table.setWordWrap(True)", text)

    def test_done_dialog_removes_lower_dirs_section(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_dialogs_source(repo_root)
        self.assertNotIn('dirs_title = QLabel(\"本次目录\")', text)
        self.assertNotIn("dirs_box = QFrame()", text)
        self.assertNotIn("dirs_list = QListWidget()", text)


if __name__ == "__main__":
    unittest.main()
