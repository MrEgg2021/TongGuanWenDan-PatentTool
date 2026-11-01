import unittest
from formal_review_source_loader import read_formal_review_mixin_source


class FormalReviewChangedOnlyStateLogicTests(unittest.TestCase):
    def test_mixin_removes_changed_only_state_fields(self) -> None:
        text = read_formal_review_mixin_source()
        self.assertNotIn('_CHANGED_ONLY_SECTIONS = ("claims", "description", "abstract", "drawings")', text)
        self.assertNotIn("_formal_review_changed_only_by_tab", text)
        self.assertNotIn("_formal_review_claim_changed_map", text)

    def test_mixin_removes_changed_only_computation_paths(self) -> None:
        text = read_formal_review_mixin_source()
        self.assertNotIn("def _segment_is_changed(self, segment_id: str) -> bool:", text)
        self.assertNotIn("def _rebuild_changed_state(self) -> None:", text)
        self.assertNotIn("def _apply_changed_only_visibility(self, *, force_claim_collapse: bool = False) -> None:", text)


if __name__ == "__main__":
    unittest.main()
