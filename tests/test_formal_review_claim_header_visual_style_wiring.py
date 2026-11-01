import unittest
from pathlib import Path
from formal_review_source_loader import read_formal_review_mixin_source


class FormalReviewClaimHeaderVisualStyleWiringTests(unittest.TestCase):
    def test_claim_header_uses_larger_dark_emphasis(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_formal_review_mixin_source(repo_root)
        self.assertIn('base_title = f"权利要求{claim_num}    字数：{claim.word_count}    引用前述：{refs_text}"', text)
        self.assertIn("root = QTreeWidgetItem([base_title])", text)
        self.assertIn("_CLAIM_HEADER_FONT_SIZE = 13", text)
        self.assertIn("root_font.setPointSize(max(int(root_font.pointSize() or 12), _CLAIM_HEADER_FONT_SIZE))", text)
        self.assertIn('return "权" + "/".join(str(value) for value in values)', text)
        self.assertIn("root_font.setBold(True)", text)
        self.assertIn('root.setForeground(0, QColor("#0F172A"))', text)

    def test_marker_block_has_light_background_style(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = (repo_root / "gui/ui_layout_impl/theme.qss").read_text(encoding="utf-8")
        self.assertIn("QLabel#FormalReviewClaimMarkerLabel {", text)
        self.assertIn("background-color: #EEF6FF;", text)
        self.assertIn("border: 1px solid #BFDBFE;", text)


if __name__ == "__main__":
    unittest.main()
