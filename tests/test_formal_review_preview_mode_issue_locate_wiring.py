import unittest
from formal_review_source_loader import read_formal_review_mixin_source


class FormalReviewPreviewModeIssueLocateWiringTests(unittest.TestCase):
    def test_locate_issue_no_longer_touches_preview_mode(self) -> None:
        text = read_formal_review_mixin_source()
        self.assertIn("def _locate_issue(self, issue_id: str) -> None:", text)
        self.assertNotIn('_formal_review_diff_preview_enabled', text)
        self.assertNotIn("self._set_diff_preview_mode(False, sync_toggle=True)", text)
        self.assertIn("locate_issue_in_word(", text)
        self.assertIn('projections=getattr(self, "_formal_review_projections", None)', text)
        self.assertIn("activate_window=True", text)


if __name__ == "__main__":
    unittest.main()
