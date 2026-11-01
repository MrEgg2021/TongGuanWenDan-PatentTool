from __future__ import annotations

import unittest
from pathlib import Path

from gui.main_window.mixins.official_docs_ops.task_tree_ops import (
    _sync_official_docs_list_detail_toggle_text,
)
from official_docs_source_loader import read_official_docs_mixin_source, read_official_docs_page_source


class _TextButton:
    def __init__(self) -> None:
        self.text = ""

    def setText(self, text: str) -> None:
        self.text = text


class OfficialDocsTaskFoldedDefaultV261Tests(unittest.TestCase):
    def test_task_list_and_detail_default_hidden(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_page_source(repo_root)
        self.assertIn("body_splitter.setVisible(False)", text)
        self.assertIn('btn_toggle_task_details = QPushButton("显示列表/详情（0）")', text)
        self.assertIn("drop_actions.addWidget(btn_toggle_task_details)", text)
        self.assertNotIn("list_header.addWidget(btn_toggle_task_details)", text)
        self.assertIn(
            "btn_toggle_task_details.clicked.connect(window.on_official_docs_toggle_task_details_visibility)",
            text,
        )

    def test_task_list_and_detail_auto_shown_after_items_loaded(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_mixin_source(repo_root)
        self.assertIn("def _set_official_docs_list_detail_visible(self, visible: bool) -> None:", text)
        self.assertIn("_set_official_docs_list_detail_visible(self, True)", text)

    def test_task_list_and_detail_hidden_after_clear(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_mixin_source(repo_root)
        self.assertIn("_set_official_docs_list_detail_visible(self, False)", text)

    def test_toggle_text_keeps_total_imported_task_count(self) -> None:
        window = type("Window", (), {})()
        window.official_docs_toggle_task_details_button = _TextButton()
        window._official_docs_leaves = {"leaf-1": {}, "leaf-2": {}}

        _sync_official_docs_list_detail_toggle_text(window, False)
        self.assertEqual(window.official_docs_toggle_task_details_button.text, "显示列表/详情（2）")

        _sync_official_docs_list_detail_toggle_text(window, True)
        self.assertEqual(window.official_docs_toggle_task_details_button.text, "隐藏列表/详情（2）")

    def test_bundle_nodes_default_collapsed(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_mixin_source(repo_root)
        self.assertIn('get(bundle_key, False)', text)


if __name__ == "__main__":
    unittest.main()
