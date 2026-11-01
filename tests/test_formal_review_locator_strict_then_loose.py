import unittest
from formal_review_source_loader import read_formal_review_mixin_source


class FormalReviewLocatorStrictThenLooseTests(unittest.TestCase):
    def test_companion_click_locate_uses_strict_then_loose(self) -> None:
        text = read_formal_review_mixin_source()
        # Strict attempt is required for correctness; loose attempt is navigation-only fallback.
        self.assertIn("strict=True", text)
        self.assertIn("strict=False", text)


if __name__ == "__main__":
    unittest.main()

