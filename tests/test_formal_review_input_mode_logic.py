import unittest
from formal_review_source_loader import read_formal_review_mixin_source, read_formal_review_page_source


class FormalReviewInputModeLogicTests(unittest.TestCase):
    def test_page_contains_mode_radios_and_parse_button(self) -> None:
        text = read_formal_review_page_source()
        self.assertIn('mode_word_radio = GraphicCheckBox("Word 文件")', text)
        self.assertIn('mode_plain_radio = GraphicCheckBox("纯文本输入")', text)
        self.assertIn("mode_group = QButtonGroup(top_bar)", text)
        self.assertIn("mode_group.setExclusive(True)", text)
        self.assertIn('parse_btn = QPushButton("解析")', text)

    def test_settings_button_opens_formal_review_settings(self) -> None:
        text = read_formal_review_page_source()
        self.assertIn("btn_settings.clicked.connect(window.on_formal_review_open_settings)", text)
        self.assertNotIn("btn_settings.clicked.connect(window._nav_to_settings)", text)

    def test_export_annotated_word_is_removed(self) -> None:
        mixin = read_formal_review_mixin_source()
        page = read_formal_review_page_source()
        self.assertNotIn("def on_formal_review_export_annotated_word", mixin)
        self.assertNotIn("导出批注Word", mixin)
        self.assertNotIn("导出批注Word", page)


if __name__ == "__main__":
    unittest.main()
