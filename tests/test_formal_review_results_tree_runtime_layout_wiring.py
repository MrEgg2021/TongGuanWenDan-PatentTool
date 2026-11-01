import unittest
from pathlib import Path


class FormalReviewResultsTreeRuntimeLayoutWiringTests(unittest.TestCase):
    def test_runtime_layout_uses_interactive_columns_and_spare_fill(self) -> None:
        source = Path("gui/main_window/mixins/formal_review_ops/issue_view_ops.py").read_text(encoding="utf-8")
        self.assertIn("def _restore_results_tree_column_widths(self, *, force: bool = False) -> None:", source)
        self.assertIn("def _on_results_tree_section_resized(self, *_args) -> None:", source)
        self.assertIn("def _apply_results_tree_row_heights(self, tree) -> None:", source)
        self.assertIn("def _refresh_results_tree_layout(self) -> None:", source)
        self.assertIn("header.setSectionResizeMode(0, QHeaderView.Interactive)", source)
        self.assertIn("header.setSectionResizeMode(2, QHeaderView.Interactive)", source)
        self.assertIn("self._restore_results_tree_column_widths()", source)
        self.assertIn("visible_cols = [idx for idx in range(4) if not bool(tree.isColumnHidden(idx))]", source)
        self.assertIn("spare = int(viewport_width - visible_total)", source)
        self.assertIn("self._apply_results_tree_row_heights(tree)", source)
        self.assertIn("tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)", source)
        self.assertNotIn("header.resizeSections(QHeaderView.ResizeMode.ResizeToContents)", source)


if __name__ == "__main__":
    unittest.main()
