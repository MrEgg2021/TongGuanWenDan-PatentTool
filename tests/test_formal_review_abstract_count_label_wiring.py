import unittest
from pathlib import Path
from formal_review_source_loader import read_formal_review_mixin_source, read_formal_review_page_source


class FormalReviewAbstractCountLabelWiringTests(unittest.TestCase):
    def test_page_declares_abstract_count_label(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_formal_review_page_source(repo_root)
        self.assertIn('abstract_count_label = QLabel("摘要字数：0/300（合规）")', text)
        self.assertIn('abstract_count_label.setObjectName("FormalReviewAbstractCountLabel")', text)
        self.assertIn("window.formal_review_abstract_count_label = abstract_count_label", text)

    def test_mixin_updates_abstract_count_label(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_formal_review_mixin_source(repo_root)
        self.assertIn("def _update_abstract_count_label(self) -> None:", text)
        self.assertIn("count = int(count_effective_chars(source_text))", text)
        self.assertIn('label.setText(f"摘要字数：{count}/{threshold}（{state_text}）")', text)
        self.assertIn("abstract_text.textChanged.connect(self._update_abstract_count_label)", text)
        self.assertIn("self._update_abstract_count_label()", text)
        self.assertIn("self._clear_document_views()", text)
        self.assertIn("self._populate_document_views()", text)


if __name__ == "__main__":
    unittest.main()
