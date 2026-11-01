import unittest
from formal_review_source_loader import read_formal_review_mixin_source


class FormalReviewClaimsChangedOnlyCollapseWiringTests(unittest.TestCase):
    def test_claims_tree_keeps_basic_header_state_without_changed_only_logic(self) -> None:
        text = read_formal_review_mixin_source()
        self.assertIn('root.setData(0, Qt.UserRole + 2, base_title)', text)
        self.assertIn('root.setExpanded(True)', text)
        self.assertNotIn('claims_only_changed_active', text)
        self.assertNotIn('def _apply_changed_only_visibility', text)


if __name__ == "__main__":
    unittest.main()
