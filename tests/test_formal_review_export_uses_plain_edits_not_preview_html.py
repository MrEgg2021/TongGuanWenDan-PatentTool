import unittest
from formal_review_source_loader import read_formal_review_mixin_source


class FormalReviewExportPayloadSourceTests(unittest.TestCase):
    def test_export_annotated_word_handler_is_removed(self) -> None:
        text = read_formal_review_mixin_source()
        self.assertNotIn("def on_formal_review_export_annotated_word", text)
        self.assertNotIn("export_annotated_copy", text)
        self.assertNotIn("导出批注Word", text)


if __name__ == "__main__":
    unittest.main()
