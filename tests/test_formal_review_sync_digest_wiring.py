import unittest
from formal_review_source_loader import read_formal_review_page_source


class FormalReviewSyncDigestWiringTests(unittest.TestCase):
    def test_page_exposes_sync_digest_label(self) -> None:
        text = read_formal_review_page_source()
        self.assertIn('sync_digest_label = QLabel("最近同步：暂无")', text)
        self.assertIn('sync_digest_label.setObjectName("FormalReviewSyncDigestLabel")', text)
        self.assertIn("window.formal_review_sync_digest_label = sync_digest_label", text)


if __name__ == "__main__":
    unittest.main()
