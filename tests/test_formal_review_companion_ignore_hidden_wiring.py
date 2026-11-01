import unittest
from pathlib import Path


class FormalReviewCompanionIgnoreHiddenWiringTests(unittest.TestCase):
    def test_results_tree_ignore_column_forced_hidden_in_companion_mode(self) -> None:
        source = Path("gui/main_window/mixins/formal_review_ops/issue_view_ops.py").read_text(encoding="utf-8")
        self.assertIn("ignore_enabled = bool(self._ignore_enabled())", source)
        self.assertIn("hide_ignore_column = bool(not ignore_enabled)", source)

    def test_companion_mode_does_not_render_ignored_markers(self) -> None:
        source = Path("gui/main_window/mixins/formal_review_ops/issue_view_ops.py").read_text(encoding="utf-8")
        self.assertIn("if ignore_enabled and bool(issue.ignored):", source)
        self.assertIn("ignored_text = \"（已忽略）\" if (ignore_enabled and bool(issue.ignored)) else \"\"", source)
        self.assertIn("toggle.setEnabled(bool(ignore_enabled and issue.issue_id))", source)
        self.assertIn("toggle.setChecked(bool(ignore_enabled and issue.ignored))", source)


if __name__ == "__main__":
    unittest.main()
