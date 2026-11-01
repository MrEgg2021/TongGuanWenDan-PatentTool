import unittest
from pathlib import Path


class FormalReviewRuleErrorWiringTests(unittest.TestCase):
    def test_review_flow_keeps_rule_errors_and_reports_count(self) -> None:
        source = Path("gui/main_window/mixins/formal_review_ops/companion_ops.py").read_text(encoding="utf-8")

        self.assertIn('rule_errors = list(result.get("rule_errors", []) or [])', source)
        self.assertIn("self._formal_review_rule_errors = rule_errors", source)
        self.assertIn("规则执行异常", source)

    def test_report_export_includes_rule_errors_as_extra_metadata(self) -> None:
        source = Path("gui/main_window/mixins/formal_review_ops/settings_export_ops.py").read_text(encoding="utf-8")

        self.assertIn('extra={"rule_errors": rule_errors} if rule_errors else None', source)

    def test_rule_error_state_is_initialized_and_cleared_with_runtime(self) -> None:
        state_source = Path("gui/main_window/mixins/formal_review_ops/state_ops.py").read_text(encoding="utf-8")
        workspace_source = Path("gui/main_window/mixins/formal_review_ops/workspace_ops.py").read_text(encoding="utf-8")

        self.assertIn('if not hasattr(self, "_formal_review_rule_errors"):', state_source)
        self.assertIn("self._formal_review_rule_errors = []", state_source)
        self.assertIn("self._formal_review_rule_errors = []", workspace_source)


if __name__ == "__main__":
    unittest.main()
