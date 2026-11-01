import unittest

from core.formal_review.models import FormalReviewDocument
from core.formal_review.semantic_rules import check_drawings_figure_reference_issues


class FormalReviewDrawingsFigureCrosscheckTests(unittest.TestCase):
    def test_reports_structure_error_when_impl_heading_missing(self) -> None:
        doc = FormalReviewDocument(
            description="一种设备\n技术领域\n本发明涉及机械领域。",
            drawings="图1为结构示意图。",
        )
        issues = check_drawings_figure_reference_issues(doc)
        self.assertEqual(1, len(issues))
        self.assertEqual("description.impl_heading.missing_for_figure_check", issues[0].rule_id)
        self.assertEqual("error", issues[0].severity)

    def test_reports_missing_figures_after_impl_heading(self) -> None:
        doc = FormalReviewDocument(
            description=(
                "一种设备\n"
                "具体实施方式\n"
                "如图1所示，主体包括壳体。\n"
                "如图3所示，壳体连接支架。"
            ),
            drawings="图1-图3为本申请结构示意图。",
        )
        issues = check_drawings_figure_reference_issues(doc)
        self.assertEqual(1, len(issues))
        self.assertEqual("drawings.figure.ref.missing_in_impl", issues[0].rule_id)
        self.assertIn("图2", str(issues[0].message))

    def test_range_coverage_passes_when_all_figures_present(self) -> None:
        doc = FormalReviewDocument(
            description=(
                "一种设备\n"
                "具体实施例\n"
                "图1示出基座。\n"
                "图2示出连接件。\n"
                "图3示出端盖。"
            ),
            drawings="图3到图1为结构示意图。",
        )
        issues = check_drawings_figure_reference_issues(doc)
        self.assertEqual([], issues)


if __name__ == "__main__":
    unittest.main()

