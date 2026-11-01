import unittest
from formal_review_source_loader import read_formal_review_mixin_source


class FormalReviewSourceUnsavedBlockTests(unittest.TestCase):
    def test_choose_file_has_unsaved_source_guard(self) -> None:
        text = read_formal_review_mixin_source()
        self.assertIn("if detect_unsaved_source(next_source):", text)
        self.assertIn("检测到源文件在 Word 中有未保存修改，请先保存后再导入。", text)


if __name__ == "__main__":
    unittest.main()
