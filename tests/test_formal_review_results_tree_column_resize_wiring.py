import unittest
from pathlib import Path
from formal_review_source_loader import read_formal_review_page_source


class FormalReviewResultsTreeColumnResizeWiringTests(unittest.TestCase):
    def test_results_tree_wrap_and_resize_policies(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_formal_review_page_source(repo_root)
        self.assertIn("header.setSectionResizeMode(0, QHeaderView.Interactive)", text)
        self.assertIn("header.setSectionResizeMode(1, QHeaderView.Interactive)", text)
        self.assertIn("header.setSectionResizeMode(2, QHeaderView.Interactive)", text)
        self.assertIn("header.setSectionResizeMode(3, QHeaderView.Interactive)", text)
        self.assertIn("results_tree.setWordWrap(True)", text)
        self.assertIn("results_tree.setUniformRowHeights(False)", text)
        self.assertIn("results_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)", text)
        self.assertIn("results_tree.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustIgnored)", text)
        self.assertIn("results_tree.setColumnWidth(0, 120)", text)
        self.assertIn("results_tree.setColumnWidth(1, 80)", text)
        self.assertIn("results_tree.setColumnWidth(3, 80)", text)


if __name__ == "__main__":
    unittest.main()
