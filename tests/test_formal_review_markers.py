import unittest

from core.formal_review.text_utils import extract_figure_markers


class FormalReviewMarkersTests(unittest.TestCase):
    def test_extracts_unique_sorted_markers(self) -> None:
        text = "部件(3)连接到阀体（12），另有接口[3]与【2】以及行星齿轮（10/10A）。"
        self.assertEqual(extract_figure_markers(text), ["2", "3", "10/10A", "12"])


if __name__ == "__main__":
    unittest.main()