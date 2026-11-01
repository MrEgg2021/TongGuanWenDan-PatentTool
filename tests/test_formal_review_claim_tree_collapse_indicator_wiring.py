import unittest
from pathlib import Path
from formal_review_source_loader import read_formal_review_page_source


class FormalReviewClaimTreeCollapseIndicatorWiringTests(unittest.TestCase):
    def test_claim_tree_keeps_expand_collapse_indicator_visible(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        page_text = read_formal_review_page_source(repo_root)
        qss_text = (repo_root / "gui/ui_layout_impl/theme.qss").read_text(encoding="utf-8")
        self.assertIn("claims_tree.setRootIsDecorated(True)", page_text)
        self.assertIn("claims_tree.setItemsExpandable(True)", page_text)
        self.assertIn("claims_tree.setIndentation(12)", page_text)
        self.assertIn("QTreeWidget#FormalReviewClaimsTree::branch {", qss_text)
        self.assertIn("margin-left: 2px;", qss_text)


if __name__ == "__main__":
    unittest.main()
