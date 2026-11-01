import unittest
from pathlib import Path


class FormalReviewResultsTreeLayoutBudgetWiringTests(unittest.TestCase):
    def test_runtime_layout_restore_and_wrap_height_wiring(self) -> None:
        source = Path("gui/main_window/mixins/formal_review_ops/issue_view_ops.py").read_text(encoding="utf-8")
        self.assertIn("def _load_results_tree_column_widths_pref(self) -> dict[str, list[int]]:", source)
        self.assertIn("def _persist_current_results_tree_column_widths(self) -> None:", source)
        self.assertIn("def _restore_results_tree_column_widths(self, *, force: bool = False) -> None:", source)
        self.assertIn("ignore_enabled = bool(self._ignore_enabled())", source)
        self.assertIn("hide_ignore_column = bool(not ignore_enabled)", source)
        self.assertIn('mode = self._results_tree_mode_key()', source)
        self.assertIn("set_pref(_RESULTS_TREE_COLUMN_WIDTHS_PREF_KEY, dict(payload))", source)
        self.assertIn("self._apply_results_tree_row_heights(tree)", source)
        self.assertIn("tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)", source)
        self.assertIn("spare = int(viewport_width - visible_total)", source)
        self.assertNotIn("header.resizeSections(QHeaderView.ResizeMode.ResizeToContents)", source)

    def test_results_tree_uses_adjust_ignored_policy(self) -> None:
        source = Path("gui/ui_layout_impl/formal_review_page_parts/page_impl.py").read_text(encoding="utf-8")
        self.assertIn("results_tree.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustIgnored)", source)
        self.assertIn("results_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)", source)


if __name__ == "__main__":
    unittest.main()
