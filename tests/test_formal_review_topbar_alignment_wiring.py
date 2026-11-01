import unittest
from pathlib import Path


class FormalReviewTopbarAlignmentWiringTests(unittest.TestCase):
    def test_topbar_widgets_use_unified_row_height(self) -> None:
        source = Path("gui/ui_layout_impl/formal_review_page_parts/page_impl.py").read_text(encoding="utf-8")
        self.assertIn("TOPBAR_ROW_HEIGHT = 34", source)
        self.assertIn("mode_hint.setFixedHeight(TOPBAR_ROW_HEIGHT)", source)
        self.assertIn("profile_label.setFixedHeight(TOPBAR_ROW_HEIGHT)", source)
        self.assertIn("profile_combo.setFixedHeight(TOPBAR_ROW_HEIGHT)", source)
        self.assertIn("file_edit.setFixedHeight(TOPBAR_ROW_HEIGHT)", source)
        self.assertIn("word_state_label.setMinimumHeight(TOPBAR_ROW_HEIGHT)", source)
        self.assertIn("dirty_state_label.setMinimumHeight(TOPBAR_ROW_HEIGHT)", source)
        self.assertIn("word_state_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)", source)
        self.assertIn("dirty_state_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)", source)

    def test_flow_layout_supports_height_for_width(self) -> None:
        source = Path("gui/ui_layout_impl/formal_review_page_parts/page_impl.py").read_text(encoding="utf-8")
        self.assertIn("if bool(item.hasHeightForWidth()):", source)
        self.assertIn("if bool(widget.hasHeightForWidth()):", source)

    def test_dense_mode_checkbox_indicator_size_is_overridden(self) -> None:
        source = Path("gui/ui_layout_impl/theme.qss").read_text(encoding="utf-8")
        self.assertIn('QWidget#formalReviewPage[dense="true"] QCheckBox {', source)
        self.assertIn('QWidget#formalReviewPage[dense="true"] QCheckBox::indicator {', source)
        self.assertIn("width: 18px;", source)
        self.assertIn("height: 18px;", source)


if __name__ == "__main__":
    unittest.main()
