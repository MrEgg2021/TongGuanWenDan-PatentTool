import unittest
from pathlib import Path
from formal_review_source_loader import read_formal_review_mixin_source, read_formal_review_page_source


class FormalReviewResultsGroupCollapseWiringTests(unittest.TestCase):
    def test_results_tree_declares_group_collapse_capability(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        layout_text = read_formal_review_page_source(repo_root)
        self.assertIn("results_tree.setRootIsDecorated(True)", layout_text)
        self.assertIn("results_tree.setItemsExpandable(True)", layout_text)
        self.assertIn("results_tree.setExpandsOnDoubleClick(False)", layout_text)
        self.assertIn("results_tree.setIndentation(10)", layout_text)

    def test_group_row_click_toggles_expand_state(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        mixin_text = read_formal_review_mixin_source(repo_root)
        self.assertIn("def on_formal_review_summary_item_clicked(self, item, _column):", mixin_text)
        self.assertIn("item.setExpanded(not item.isExpanded())", mixin_text)
        self.assertIn("root.setExpanded(True)", mixin_text)


if __name__ == "__main__":
    unittest.main()
