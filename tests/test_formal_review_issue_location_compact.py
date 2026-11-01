import unittest
from formal_review_source_loader import read_formal_review_mixin_source


class FormalReviewIssueLocationCompactTests(unittest.TestCase):
    def test_location_text_uses_section_based_compact_rendering(self) -> None:
        text = read_formal_review_mixin_source()
        self.assertIn("def _issue_location_text(issue: Issue) -> str:", text)
        self.assertIn('if section == "claims":', text)
        self.assertIn('if section == "description":', text)
        self.assertIn('if section == "abstract":', text)
        self.assertIn('if section == "drawings":', text)
        self.assertNotIn(" @ ", text)


if __name__ == "__main__":
    unittest.main()
