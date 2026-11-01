import unittest

from core.formal_review.text_utils import count_effective_chars


class FormalReviewWordCountTests(unittest.TestCase):
    def test_count_ignores_whitespace_only(self) -> None:
        text = "A，B。 C\tD\nE!"
        self.assertEqual(count_effective_chars(text), 8)


if __name__ == "__main__":
    unittest.main()
