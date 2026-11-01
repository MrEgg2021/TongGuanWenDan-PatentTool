import unittest
from pathlib import Path


class FormalReviewDiffPreviewRendererTests(unittest.TestCase):
    def test_diff_preview_module_removed(self) -> None:
        self.assertFalse(Path("core/formal_review/diff_preview.py").exists())

    def test_formal_review_init_no_longer_exports_diff_preview_symbols(self) -> None:
        source = Path("core/formal_review/__init__.py").read_text(encoding="utf-8")
        self.assertNotIn("from .diff_preview", source)
        self.assertNotIn("build_char_diff_ops", source)
        self.assertNotIn("render_diff_html", source)
        self.assertNotIn('"DiffOp"', source)


if __name__ == "__main__":
    unittest.main()
