import unittest
from pathlib import Path


class FormalReviewResizeRefreshWiringTests(unittest.TestCase):
    def test_resize_event_triggers_results_tree_refresh(self) -> None:
        source = Path("gui/main_window/mixins/progress_mixin.py").read_text(encoding="utf-8")
        self.assertIn("def resizeEvent(self, event):", source)
        self.assertIn("if formal_page is not None and bool(formal_page.isVisible()):", source)
        self.assertIn("if hasattr(self, \"_refresh_results_tree_layout\"):", source)
        self.assertIn("if hasattr(self, \"_schedule_results_tree_layout_refresh\"):", source)

    def test_state_wiring_registers_resize_related_tree_signals(self) -> None:
        source = Path("gui/main_window/mixins/formal_review_ops/state_ops.py").read_text(encoding="utf-8")
        self.assertIn("results_tree.itemExpanded.connect(lambda *_: self._schedule_results_tree_layout_refresh())", source)
        self.assertIn("results_tree.itemCollapsed.connect(lambda *_: self._schedule_results_tree_layout_refresh())", source)
        self.assertIn("header.sectionResized.connect(self._on_results_tree_section_resized)", source)

    def test_schedule_uses_single_shot_refresh(self) -> None:
        source = Path("gui/main_window/mixins/formal_review_ops/issue_view_ops.py").read_text(encoding="utf-8")
        self.assertIn("def _schedule_results_tree_layout_refresh(self) -> None:", source)
        self.assertIn("QTimer.singleShot(0, _run)", source)


if __name__ == "__main__":
    unittest.main()
