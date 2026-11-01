import unittest

from formal_review_source_loader import read_formal_review_mixin_source


class FormalReviewCompanionComBlockOnceWiringTests(unittest.TestCase):
    def test_state_has_session_level_prompt_flags(self) -> None:
        text = read_formal_review_mixin_source()
        self.assertIn('if not hasattr(self, "_formal_review_com_block_prompted"):', text)
        self.assertIn('if not hasattr(self, "_formal_review_com_block_last_reason"):', text)
        self.assertIn("self._formal_review_com_block_prompted = False", text)
        self.assertIn("self._formal_review_com_block_last_reason = \"\"", text)

    def test_helper_blocks_and_prompts_once(self) -> None:
        text = read_formal_review_mixin_source()
        self.assertIn("def _ensure_com_find_ready_or_prompt(self, *, context: str) -> bool:", text)
        self.assertIn("ready = check_com_find_ready(doc)", text)
        self.assertIn("prompted = bool(getattr(self, \"_formal_review_com_block_prompted\", False))", text)
        self.assertIn("if not prompted:", text)
        self.assertIn("QMessageBox.warning(", text)
        self.assertIn("self._set_status_text(\"形式审查：无法可靠定位 Word 中的文字，请重新连接文档。\")", text)

    def test_word_flow_entrypoints_call_guard(self) -> None:
        text = read_formal_review_mixin_source()
        self.assertIn('self._run_companion_review_cycle(trigger="start_check", auto_sync_comments=True, redock=False)', text)
        self.assertIn("if not self._ensure_com_find_ready_or_prompt(context=f\"review_cycle:{str(trigger or '')}\"):", text)
        self.assertIn("if not self._ensure_com_find_ready_or_prompt(context=f\"comment_sync:{str(trigger or '')}\"):", text)
        self.assertIn("if not self._ensure_com_find_ready_or_prompt(context=f\"locate_issue:{str(issue_id or '')}\"):", text)
        self.assertIn("if not self._ensure_com_find_ready_or_prompt(context=\"marker_apply_direct\"):", text)


if __name__ == "__main__":
    unittest.main()
