import unittest
from pathlib import Path
from formal_review_source_loader import read_formal_review_mixin_source


class FormalReviewIssueFocusWiringTests(unittest.TestCase):
    def test_locate_issue_calls_focus_flow(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_formal_review_mixin_source(repo_root)
        self.assertIn("def _focus_issue(self, issue: Issue | None) -> None:", text)
        self.assertIn("self._focus_issue(issue)", text)

    def test_focus_issue_moves_cursor_and_keeps_target_visible(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_formal_review_mixin_source(repo_root)
        self.assertIn("editor.setTextCursor(cursor)", text)
        self.assertIn("editor.ensureCursorVisible()", text)

    def test_claim_focus_expands_and_scrolls_tree(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_formal_review_mixin_source(repo_root)
        self.assertIn("def _expand_claim_tree_for_focus(self, claim_num: int) -> None:", text)
        self.assertIn("tree.scrollToItem(focus_item)", text)


if __name__ == "__main__":
    unittest.main()
