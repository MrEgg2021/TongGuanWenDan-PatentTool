import unittest
from pathlib import Path
from formal_review_source_loader import read_formal_review_page_source


class FormalReviewInputModeWidgetStyleWiringTests(unittest.TestCase):
    def test_input_mode_uses_graphic_checkbox_with_exclusive_group(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_formal_review_page_source(repo_root)
        self.assertIn("from gui.widgets import GraphicCheckBox", text)
        self.assertIn('mode_word_radio = GraphicCheckBox("Word 文件")', text)
        self.assertIn('mode_plain_radio = GraphicCheckBox("纯文本输入")', text)
        self.assertIn("mode_group = QButtonGroup(top_bar)", text)
        self.assertIn("mode_group.setExclusive(True)", text)
        self.assertNotIn("QRadioButton", text)


if __name__ == "__main__":
    unittest.main()
