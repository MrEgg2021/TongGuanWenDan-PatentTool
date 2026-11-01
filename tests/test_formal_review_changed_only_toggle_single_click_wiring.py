import unittest
from formal_review_source_loader import read_formal_review_mixin_source


class FormalReviewChangedOnlyToggleSingleClickWiringTests(unittest.TestCase):
    def test_changed_only_methods_removed(self) -> None:
        text = read_formal_review_mixin_source()
        self.assertNotIn("def _set_changed_only_enabled(self, section: str, enabled: bool) -> None:", text)
        self.assertNotIn("def _apply_changed_only_visibility(self, *, force_claim_collapse: bool = False) -> None:", text)
        self.assertNotIn("_formal_review_changed_only_by_tab", text)


if __name__ == "__main__":
    unittest.main()
