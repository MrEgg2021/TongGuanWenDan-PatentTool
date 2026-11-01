import unittest
from formal_review_source_loader import read_formal_review_page_source


class FormalReviewToolbarFlowWrapWiringTests(unittest.TestCase):
    def test_top_toolbar_uses_flow_layout(self) -> None:
        text = read_formal_review_page_source()
        self.assertIn("TOPBAR_ROW_HEIGHT = 34", text)
        self.assertIn("class _FlowLayout(QLayout):", text)
        self.assertIn("top_bar_layout = QVBoxLayout(top_bar)", text)
        self.assertIn("top_controls = QWidget(top_bar)", text)
        self.assertIn("top_layout = _FlowLayout(top_controls, margin=0, h_spacing=8, v_spacing=6)", text)
        self.assertIn("file_edit.setMinimumWidth(0)", text)
        self.assertIn("file_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)", text)
        self.assertIn("mode_word_radio.setFixedHeight(TOPBAR_ROW_HEIGHT)", text)
        self.assertIn("mode_plain_radio.setFixedHeight(TOPBAR_ROW_HEIGHT)", text)
        self.assertIn("for _btn in (choose_btn, parse_btn, btn_start, btn_export_report, btn_settings):", text)
        self.assertIn("word_state_label.setWordWrap(True)", text)
        self.assertIn("dirty_state_label.setWordWrap(True)", text)
        self.assertIn("word_state_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)", text)
        self.assertIn("dirty_state_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)", text)
        self.assertIn("top_status_layout = QVBoxLayout(top_status)", text)
        self.assertIn("top_bar_layout.addWidget(top_status)", text)


if __name__ == "__main__":
    unittest.main()

