import unittest
from pathlib import Path
from formal_review_source_loader import read_formal_review_mixin_source, read_formal_review_page_source


class FormalReviewExportRemovalTests(unittest.TestCase):
    def test_export_annotated_word_removed_completely(self) -> None:
        mixin = read_formal_review_mixin_source()
        page = read_formal_review_page_source()
        annotator = Path("core/formal_review/annotator.py").read_text(encoding="utf-8")

        self.assertNotIn("def on_formal_review_export_annotated_word", mixin)
        self.assertNotIn("export_annotated_copy", mixin)
        self.assertNotIn("导出批注Word", page)
        self.assertNotIn("formal_review_export_word_button", page)
        self.assertNotIn("export_annotated_copy", annotator)


if __name__ == "__main__":
    unittest.main()
