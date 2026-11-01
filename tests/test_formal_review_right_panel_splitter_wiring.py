import unittest
from pathlib import Path
from formal_review_source_loader import read_formal_review_page_source


class FormalReviewRightPanelSplitterWiringTests(unittest.TestCase):
    def test_right_panel_uses_vertical_splitter_with_marker_above_detail(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_formal_review_page_source(repo_root)
        self.assertIn("right_splitter = QSplitter(Qt.Vertical)", text)
        self.assertIn('right_splitter.setObjectName("FormalReviewRightPanelSplitter")', text)
        self.assertIn("right_splitter.addWidget(marker_section)", text)
        self.assertIn("right_splitter.addWidget(detail_section)", text)
        self.assertIn("right_splitter.setSizes([220, 280])", text)
        self.assertIn("window.formal_review_right_splitter = right_splitter", text)


if __name__ == "__main__":
    unittest.main()
