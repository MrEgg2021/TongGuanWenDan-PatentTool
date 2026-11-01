import unittest
from formal_review_source_loader import read_formal_review_page_source


class FormalReviewChangedOnlyToggleWiringTests(unittest.TestCase):
    def test_page_removes_per_tab_changed_only_toggles_and_signals(self) -> None:
        text = read_formal_review_page_source()
        self.assertNotIn("FormalReviewClaimsChangedOnlyToggle", text)
        self.assertNotIn("FormalReviewDescriptionChangedOnlyToggle", text)
        self.assertNotIn("FormalReviewAbstractChangedOnlyToggle", text)
        self.assertNotIn("FormalReviewDrawingsChangedOnlyToggle", text)
        self.assertNotIn("on_formal_review_changed_only_toggled", text)

    def test_page_exports_changed_only_handles_as_none(self) -> None:
        text = read_formal_review_page_source()
        self.assertIn("window.formal_review_claims_changed_only_toggle = None", text)
        self.assertIn("window.formal_review_description_changed_only_toggle = None", text)
        self.assertIn("window.formal_review_abstract_changed_only_toggle = None", text)
        self.assertIn("window.formal_review_drawings_changed_only_toggle = None", text)


if __name__ == "__main__":
    unittest.main()
