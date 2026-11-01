import unittest
from formal_review_source_loader import read_formal_review_mixin_source


class FormalReviewChooseFileSilentCopyTimestampTests(unittest.TestCase):
    def test_timestamp_working_copy_naming_and_collision_suffix(self) -> None:
        text = read_formal_review_mixin_source()
        self.assertIn('stamp = datetime.now().strftime("%Y%m%d_%H%M%S")', text)
        self.assertIn('candidate = parent / f"{stem}_形式审查副本_{stamp}{ext}"', text)
        self.assertIn('candidate = parent / f"{stem}_形式审查副本_{stamp}_{idx}{ext}"', text)
        self.assertIn("shutil.copy2(str(source), str(candidate))", text)


if __name__ == "__main__":
    unittest.main()
