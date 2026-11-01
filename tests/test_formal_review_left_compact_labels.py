import unittest
from formal_review_source_loader import read_formal_review_mixin_source


class FormalReviewLeftCompactLabelsTests(unittest.TestCase):
    def test_left_list_uses_compact_group_and_location_helpers(self) -> None:
        text = read_formal_review_mixin_source()
        self.assertIn("def _issue_group_label_compact_for_list(issue: Issue) -> str:", text)
        self.assertIn("def _issue_location_compact_for_list(issue: Issue) -> str:", text)
        self.assertIn('child = QTreeWidgetItem([_issue_location_compact_for_list(issue), severity, message, ""])', text)

    def test_issue_detail_panel_keeps_full_labels(self) -> None:
        text = read_formal_review_mixin_source()
        self.assertIn('meta_label.setText(f"{_issue_group_label(issue)} {ignored_text}\\n{_issue_location_text(issue)}\\n{str(issue.message or \'\')}".strip())', text)
        self.assertIn("检查项目：{rule_label}", text)


if __name__ == "__main__":
    unittest.main()
