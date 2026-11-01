import unittest
from formal_review_source_loader import read_formal_review_mixin_source


class FormalReviewTokenFreezeValidatorTests(unittest.TestCase):
    def test_token_freeze_helpers_exist(self) -> None:
        text = read_formal_review_mixin_source()
        self.assertIn("def _tokens_intact(self, segment: EditableSegment, edited_text: str) -> bool:", text)
        self.assertIn("if source_text.count(token) != 1:", text)
        self.assertIn("def _strip_obj_tokens(text: str) -> str:", text)
        self.assertIn("return _TOKEN_RE.sub(\"\", source).strip()", text)

    def test_non_text_segment_writeback_downgrade_path_exists(self) -> None:
        text = read_formal_review_mixin_source()
        self.assertIn("if changed and bool(segment.has_non_text):", text)
        self.assertIn("Placeholder token changed, cannot write revision safely", text)
        self.assertIn("Segment contains non-text object, downgraded to comment", text)


if __name__ == "__main__":
    unittest.main()
