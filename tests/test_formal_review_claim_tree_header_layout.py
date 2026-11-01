import unittest
from pathlib import Path
from formal_review_source_loader import read_formal_review_mixin_source


class FormalReviewClaimTreeHeaderLayoutTests(unittest.TestCase):
    def test_claim_header_combines_title_count_and_refs(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_formal_review_mixin_source(repo_root)
        self.assertIn('base_title = f"权利要求{claim_num}    字数：{claim.word_count}    引用前述：{refs_text}"', text)
        self.assertIn("root = QTreeWidgetItem([base_title])", text)
        self.assertIn('return "权" + "/".join(str(value) for value in values)', text)
        self.assertNotIn("claim_stats:", text)

    def test_claim_marker_line_uses_wrapped_label(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_formal_review_mixin_source(repo_root)
        self.assertIn('marker_item.setData(0, Qt.UserRole, f"claim_markers:{claim_num}")', text)
        self.assertIn('marker_label = QLabel(f"附图标记：{markers_text}")', text)
        self.assertIn("marker_label.setWordWrap(True)", text)
        self.assertIn("content_editor.document().setDocumentMargin(0)", text)
        self.assertLess(text.find('content_item.setData(0, Qt.UserRole, f"claim_content:{claim_num}")'), text.find('marker_item.setData(0, Qt.UserRole, f"claim_markers:{claim_num}")'))


if __name__ == "__main__":
    unittest.main()
