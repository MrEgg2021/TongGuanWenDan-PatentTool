import unittest
from pathlib import Path
from gui_source_loader import read_modern_shell_source


class FormalReviewLayoutWiringTests(unittest.TestCase):
    def test_ui_layout_builds_and_mounts_formal_review_page(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = (repo_root / "gui/ui_layout.py").read_text(encoding="utf-8")
        self.assertIn("build_formal_review_page(self)", text)
        self.assertIn("scroll_content_layout.addWidget(formal_review_page, 100)", text)
        self.assertIn("self._formal_review_page = formal_review_page", text)

    def test_sidebar_has_formal_review_entry(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_modern_shell_source(repo_root)
        self.assertIn('nav_formal_review = QPushButton("形式审查")', text)
        self.assertIn("layout.addWidget(nav_formal_review)", text)
        self.assertIn("container.nav_formal_review = getattr(sidebar, \"nav_formal_review\", None)", text)


if __name__ == "__main__":
    unittest.main()
