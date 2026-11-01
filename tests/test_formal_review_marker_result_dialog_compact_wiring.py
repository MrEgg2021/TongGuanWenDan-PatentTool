import unittest
from pathlib import Path


class FormalReviewMarkerResultDialogCompactWiringTests(unittest.TestCase):
    def test_marker_result_dialog_helpers_exist(self) -> None:
        source = Path("gui/main_window/mixins/formal_review_ops/marker_ops.py").read_text(encoding="utf-8")
        self.assertIn("def _build_marker_apply_compact_summary(report) -> str:", source)
        self.assertIn("def _build_marker_apply_detail_text(plan, report) -> str:", source)
        self.assertIn("def _show_marker_apply_result_dialog(", source)
        self.assertIn('detail_btn = box.addButton("技术详情", QMessageBox.ActionRole)', source)
        self.assertIn('ok_btn = box.addButton("确定", QMessageBox.AcceptRole)', source)

    def test_direct_apply_uses_summary_plus_detail_dialog(self) -> None:
        source = Path("gui/main_window/mixins/formal_review_ops/marker_ops.py").read_text(encoding="utf-8")
        self.assertIn("title=\"附图标记修订结果\"", source)
        self.assertIn("summary = _build_marker_apply_compact_summary(report)", source)
        self.assertIn("detail = _build_marker_apply_detail_text(plan, report)", source)
        self.assertIn("summary_text=f\"{summary}\\n\\n{tip_line}\"", source)

    def test_zero_command_branch_uses_plan_summary_text(self) -> None:
        source = Path("gui/main_window/mixins/formal_review_ops/marker_ops.py").read_text(encoding="utf-8")
        self.assertIn("if int(getattr(plan, \"command_count\", 0) or 0) <= 0:", source)
        self.assertIn("summary = _build_marker_plan_summary_text(self, plan, parser_warnings=[], include_warning_lines=10)", source)
        self.assertIn("\"未找到可应用的修改。\\n\\n\" + str(summary or \"\")", source)


if __name__ == "__main__":
    unittest.main()
