import unittest
from pathlib import Path
from formal_review_source_loader import read_formal_review_mixin_source


class FormalReviewClaimTreeContentOrderTests(unittest.TestCase):
    def test_claim_tree_renders_body_before_marker_block(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        text = read_formal_review_mixin_source(repo_root)
        content_index = text.find('content_item.setData(0, Qt.UserRole, f"claim_content:{claim_num}")')
        marker_index = text.find('marker_item.setData(0, Qt.UserRole, f"claim_markers:{claim_num}")')
        self.assertGreaterEqual(content_index, 0)
        self.assertGreaterEqual(marker_index, 0)
        self.assertLess(content_index, marker_index)


if __name__ == "__main__":
    unittest.main()
