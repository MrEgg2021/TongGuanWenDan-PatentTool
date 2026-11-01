import unittest
from pathlib import Path
from formal_review_source_loader import read_formal_review_page_source


class FormalReviewResultsTreeCompactStyleWiringTests(unittest.TestCase):
    def test_results_tree_wiring_uses_wrap_friendly_columns(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_formal_review_page_source(repo_root)
        self.assertIn('results_tree.setObjectName("FormalReviewResultsTree")', text)
        self.assertIn("results_tree.setIndentation(10)", text)
        self.assertIn("header.setSectionResizeMode(0, QHeaderView.Interactive)", text)
        self.assertIn("header.setSectionResizeMode(1, QHeaderView.Interactive)", text)
        self.assertIn("header.setSectionResizeMode(2, QHeaderView.Interactive)", text)
        self.assertIn("header.setSectionResizeMode(3, QHeaderView.Interactive)", text)
        self.assertIn("results_tree.setColumnWidth(0, 120)", text)
        self.assertIn("results_tree.setTextElideMode(Qt.ElideNone)", text)
        self.assertIn("results_tree.setWordWrap(True)", text)
        self.assertIn("results_tree.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustIgnored)", text)
        self.assertIn("claims_tree.setIndentation(12)", text)

    def test_qss_contains_compact_rules_for_results_and_claims_tree(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = (repo_root / "gui/ui_layout_impl/theme.qss").read_text(encoding="utf-8")
        self.assertIn("QTreeWidget#FormalReviewResultsTree::item {", text)
        self.assertIn("QTreeWidget#FormalReviewResultsTree::branch {", text)
        self.assertIn("QTreeWidget#FormalReviewClaimsTree::item {", text)
        self.assertIn("QTreeWidget#FormalReviewClaimsTree::branch {", text)
        self.assertIn("QLabel#FormalReviewClaimMarkerLabel {", text)
        self.assertIn("QLabel#FormalReviewAbstractCountLabel {", text)


if __name__ == "__main__":
    unittest.main()
