import unittest
from pathlib import Path


class FormalReviewIssueLabelsCnMappingTests(unittest.TestCase):
    def test_group_labels_and_severity_labels_are_cn(self) -> None:
        source = Path("gui/main_window/mixins/formal_review_ops/shared.py").read_text(encoding="utf-8")
        self.assertIn('"fatal": "致命"', source)
        self.assertIn('"error": "错误"', source)
        self.assertIn('"warning": "警告"', source)
        self.assertIn('"medium": "中等"', source)
        self.assertIn('"low": "提醒"', source)
        self.assertIn('return "摘要长度"', source)
        self.assertIn('return "标点符号"', source)
        self.assertIn('return "权利要求引用"', source)
        self.assertIn('return "权利要求阈值"', source)
        self.assertIn('return "规则检查"', source)
        self.assertNotIn("Abstract Length", source)
        self.assertNotIn("Punctuation", source)
        self.assertNotIn("Rule Check", source)


if __name__ == "__main__":
    unittest.main()
