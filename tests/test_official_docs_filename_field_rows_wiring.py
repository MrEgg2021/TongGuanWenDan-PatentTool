from __future__ import annotations

import unittest
from pathlib import Path
from official_docs_source_loader import read_official_docs_mixin_source, read_official_docs_page_source


class OfficialDocsFilenameFieldRowsWiringTests(unittest.TestCase):
    def test_filename_field_rows_use_drag_handle_and_raw_token_storage(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_official_docs_mixin_source(repo_root)
        self.assertIn('item = QListWidgetItem(f"☰ {token}")', text)
        self.assertIn("item.setData(FILENAME_TOKEN_ROLE, token)", text)
        self.assertIn("item.data(FILENAME_TOKEN_ROLE)", text)
        self.assertIn('if token.startswith("☰"):', text)

    def test_filename_card_readonly_visual_wiring_exists(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        mixin_text = read_official_docs_mixin_source(repo_root)
        qss_text = (repo_root / "gui/ui_layout_impl/theme.qss").read_text(encoding="utf-8")
        self.assertIn('fields_card.setProperty("readonlyMode", not bool(editable))', mixin_text)
        self.assertIn('QFrame#Card[officialDocsFilenameCard="true"][readonlyMode="true"]', qss_text)
        self.assertIn("QListWidget#OfficialDocsFilenameFieldsList::item", qss_text)

    def test_filename_field_supports_move_up_and_down_buttons(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        page_text = read_official_docs_page_source(repo_root)
        mixin_text = read_official_docs_mixin_source(repo_root)
        self.assertIn('btn_move_up = QPushButton("⬆")', page_text)
        self.assertIn('btn_move_down = QPushButton("⬇")', page_text)
        self.assertIn("btn_move_field_up.clicked.connect(window.on_official_docs_move_field_up)", page_text)
        self.assertIn("btn_move_field_down.clicked.connect(window.on_official_docs_move_field_down)", page_text)
        self.assertIn("def on_official_docs_move_field_up(self) -> None:", mixin_text)
        self.assertIn("def on_official_docs_move_field_down(self) -> None:", mixin_text)


if __name__ == "__main__":
    unittest.main()
