import unittest
from formal_review_source_loader import read_formal_review_mixin_source, read_formal_review_page_source


class FormalReviewWordExportWiringTests(unittest.TestCase):
    def test_export_button_and_handler_are_removed(self) -> None:
        mixin = read_formal_review_mixin_source()
        page = read_formal_review_page_source()

        self.assertNotIn("def on_formal_review_export_annotated_word", mixin)
        self.assertNotIn("export_annotated_copy", mixin)
        self.assertNotIn("导出批注Word", page)


if __name__ == "__main__":
    unittest.main()

