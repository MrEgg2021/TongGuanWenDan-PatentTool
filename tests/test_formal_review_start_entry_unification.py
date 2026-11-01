import unittest

from formal_review_source_loader import read_formal_review_mixin_source


class FormalReviewStartEntryUnificationTests(unittest.TestCase):
    def test_parse_delegates_to_connect_word_in_word_mode(self) -> None:
        text = read_formal_review_mixin_source()
        self.assertIn("def on_formal_review_parse(self):", text)
        self.assertIn("self.on_formal_review_connect_word()", text)
        self.assertIn("def on_formal_review_start_check(self):", text)


if __name__ == "__main__":
    unittest.main()
