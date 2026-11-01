import unittest
from pathlib import Path


class FormalReviewResultsTreePersistenceAndGuardWiringTests(unittest.TestCase):
    def test_shared_declares_results_tree_width_pref_key(self) -> None:
        source = Path("gui/main_window/mixins/formal_review_ops/shared.py").read_text(encoding="utf-8")
        self.assertIn('_RESULTS_TREE_COLUMN_WIDTHS_PREF_KEY = "formal_review.results_tree.column_widths.v1"', source)
        self.assertIn("_RESULTS_TREE_DEFAULT_WIDTHS = (120, 80, 220, 80)", source)
        self.assertIn("_RESULTS_TREE_MIN_WIDTH = 36", source)

    def test_state_bootstraps_results_tree_width_persistence_state(self) -> None:
        source = Path("gui/main_window/mixins/formal_review_ops/state_ops.py").read_text(encoding="utf-8")
        self.assertIn('if not hasattr(self, "_formal_review_results_tree_width_mode_applied"):', source)
        self.assertIn('if not hasattr(self, "_formal_review_results_tree_restoring_widths"):', source)
        self.assertIn('if not hasattr(self, "_formal_review_results_tree_width_save_pending"):', source)
        self.assertIn('if not hasattr(self, "_formal_review_results_tree_column_widths_by_mode"):', source)
        self.assertIn("self._formal_review_results_tree_column_widths_by_mode = self._load_results_tree_column_widths_pref()", source)

    def test_issue_view_persists_widths_and_uses_guarded_spare_space_fill(self) -> None:
        source = Path("gui/main_window/mixins/formal_review_ops/issue_view_ops.py").read_text(encoding="utf-8")
        self.assertIn('return "plain_text" if bool(self._ignore_enabled()) else "word"', source)
        self.assertIn("set_pref(_RESULTS_TREE_COLUMN_WIDTHS_PREF_KEY, dict(payload))", source)
        self.assertIn("with QSignalBlocker(tree):", source)
        self.assertIn("if bool(issue.ignored) == bool(ignored):", source)
        self.assertIn("spare = int(viewport_width - visible_total)", source)
        self.assertIn("if spare > 0 and 2 in visible_cols:", source)
        self.assertIn("self._formal_review_results_tree_restoring_widths = True", source)


if __name__ == "__main__":
    unittest.main()
