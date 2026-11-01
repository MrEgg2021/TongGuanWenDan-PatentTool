import inspect
import unittest
from contextlib import ExitStack
from unittest.mock import patch
from pathlib import Path

from core.formal_review.models import ClaimItem, FormalReviewDocument
from gui.main_window.mixins.formal_review_ops import companion_ops


class _MarkerEdit:
    def __init__(self, text: str) -> None:
        self._text = text

    def toPlainText(self) -> str:
        return self._text


class _DummyReviewWindow:
    _prepare_marker_basis_rule_inputs = companion_ops._prepare_marker_basis_rule_inputs
    _run_review_on_current_document = companion_ops._run_review_on_current_document

    def __init__(self, *, mode: str, marker_text: str) -> None:
        self._formal_review_input_mode = mode
        self._formal_review_document = FormalReviewDocument(
            claims=[ClaimItem(num=1, text="一种装置。")],
            description="",
            abstract="",
            drawings="",
        )
        self._formal_review_needs_parse = False
        self._formal_review_rule_enabled = {
            "claim.ref.marker_basis.missing": True,
            "claim.ref.term_basis.missing": True,
        }
        self._formal_review_rule_params = {}
        self._formal_review_skipped_rule_labels = []
        self._formal_review_rule_errors = []
        self._formal_review_issues = []
        self.formal_review_marker_edit = _MarkerEdit(marker_text)
        self.status_text = ""

    def _set_status_text(self, text: str) -> None:
        self.status_text = str(text)

    def _render_claims_tree(self) -> None:
        return None

    def _build_document_from_current_views(self):
        return self._formal_review_document

    def _formal_review_fill_claims_table(self) -> None:
        return None

    def _rebuild_issue_ids(self, _issues) -> None:
        return None

    def _apply_ignore_state(self, _issues) -> None:
        return None

    def _render_issue_views(self) -> None:
        return None

    def _ask_continue_cancel_cn(self, *_args, **_kwargs) -> bool:
        raise AssertionError("empty marker note must not require a confirmation dialog")


class _DummyCompanionCycleWindow:
    _run_companion_review_cycle = companion_ops._run_companion_review_cycle

    def __init__(self, *, review_ok: bool = False) -> None:
        self._formal_review_busy = False
        self._formal_review_companion_session = object()
        self.sync_called = False
        self.review_ok = bool(review_ok)

    def _connect_or_attach_companion(self) -> bool:
        return True

    def _dock_companion_windows_once(self) -> None:
        return None

    def _ensure_com_find_ready_or_prompt(self, *, context: str) -> bool:
        return True

    def _ensure_companion_doc_clean_or_prompt(self, *, trigger: str) -> bool:
        return True

    def _reset_issue_views(self, *, clear_ignore: bool) -> None:
        return None

    def _apply_document_snapshot(self, *, document, anchors, editable_segments, projections) -> None:
        return None

    def _run_review_on_current_document(self) -> bool:
        return self.review_ok

    def _apply_input_mode_to_ui(self) -> None:
        return None

    def _auto_sync_comments_to_copy(self, *, trigger: str) -> bool:
        self.sync_called = True
        return True

    def _show_formal_review_cycle_summary_dialog(self, *, trigger: str, auto_sync_comments: bool) -> None:
        return None

    def _set_status_text(self, _text: str) -> None:
        return None

    def _emit_formal_review_overlay_progress(self, _percent: int, _status_text: str) -> None:
        return None


class FormalReviewMarkerInputGuardWiringTests(unittest.TestCase):
    def test_review_method_has_no_obsolete_prompt_switch(self) -> None:
        parameters = tuple(inspect.signature(companion_ops._run_review_on_current_document).parameters)

        self.assertEqual(("self",), parameters)

    def _run_review_and_capture_enabled_rules(self, *, marker_text: str, mode: str = "word", patch_warning: bool = True):
        captured: dict[str, object] = {}

        def fake_run_formal_review(_document, **kwargs):
            captured["enabled_rule_ids"] = set(kwargs.get("enabled_rule_ids") or set())
            captured["marker_note_map"] = dict(kwargs.get("marker_note_map") or {})
            return {"issues": [], "rule_errors": []}

        with ExitStack() as stack:
            stack.enter_context(patch("gui.main_window.mixins.formal_review_ops.companion_ops.set_pref", return_value=None))
            stack.enter_context(
                patch(
                    "gui.main_window.mixins.formal_review_ops.companion_ops.load_wordlist_profile_store",
                    return_value=("精简默认", {"精简默认": {"claims": {"forbidden": [], "sensitive": []}, "description": {"forbidden": [], "sensitive": []}}}),
                )
            )
            stack.enter_context(
                patch(
                    "gui.main_window.mixins.formal_review_ops.companion_ops.load_wordlists",
                    return_value={"claims": {"forbidden": [], "sensitive": []}, "description": {"forbidden": [], "sensitive": []}},
                )
            )
            stack.enter_context(
                patch(
                    "gui.main_window.mixins.formal_review_ops.companion_ops.run_formal_review",
                    side_effect=fake_run_formal_review,
                )
            )
            if patch_warning:
                stack.enter_context(patch("gui.main_window.mixins.formal_review_ops.companion_ops.QMessageBox.warning", return_value=0))
            window = _DummyReviewWindow(mode=mode, marker_text=marker_text)
            ok = window._run_review_on_current_document()
        return ok, window, captured

    def test_review_continues_and_skips_marker_basis_rules_when_marker_note_missing(self) -> None:
        for mode in ("plain_text", "word"):
            ok, window, captured = self._run_review_and_capture_enabled_rules(marker_text="", mode=mode)
            self.assertTrue(ok)
            enabled_rule_ids = captured["enabled_rule_ids"]
            self.assertNotIn("claim.ref.marker_basis.missing", enabled_rule_ids)
            self.assertNotIn("claim.ref.term_basis.missing", enabled_rule_ids)
            self.assertEqual({}, captured["marker_note_map"])
            self.assertIn("已跳过", window.status_text)
            self.assertEqual(
                ["附图标记引用基础缺失", "所述后术语未对应标号说明"],
                window._formal_review_skipped_rule_labels,
            )

    def test_valid_marker_note_keeps_marker_basis_rules_enabled(self) -> None:
        ok, window, captured = self._run_review_and_capture_enabled_rules(marker_text="1、装置")
        self.assertTrue(ok)
        enabled_rule_ids = captured["enabled_rule_ids"]
        self.assertIn("claim.ref.marker_basis.missing", enabled_rule_ids)
        self.assertIn("claim.ref.term_basis.missing", enabled_rule_ids)
        self.assertEqual({"1": "装置"}, captured["marker_note_map"])
        self.assertNotIn("已跳过", window.status_text)
        self.assertEqual([], window._formal_review_skipped_rule_labels)

    def test_invalid_marker_note_skips_marker_basis_rules_without_blocking_review(self) -> None:
        ok, window, captured = self._run_review_and_capture_enabled_rules(marker_text="不是标号说明")
        self.assertTrue(ok)
        enabled_rule_ids = captured["enabled_rule_ids"]
        self.assertNotIn("claim.ref.marker_basis.missing", enabled_rule_ids)
        self.assertNotIn("claim.ref.term_basis.missing", enabled_rule_ids)
        self.assertEqual({}, captured["marker_note_map"])
        self.assertIn("无有效映射", window.status_text)

    def test_companion_cycle_does_not_sync_when_review_failed(self) -> None:
        window = _DummyCompanionCycleWindow(review_ok=False)
        with patch(
            "gui.main_window.mixins.formal_review_ops.companion_ops.get_document_snapshot",
            return_value=(FormalReviewDocument(), [], [], None),
        ):
            ok = window._run_companion_review_cycle(trigger="start_check", auto_sync_comments=True, redock=False)
        self.assertFalse(ok)
        self.assertFalse(window.sync_called)

    def test_companion_cycle_syncs_when_review_continues_after_marker_note_skip(self) -> None:
        window = _DummyCompanionCycleWindow(review_ok=True)
        with patch(
            "gui.main_window.mixins.formal_review_ops.companion_ops.get_document_snapshot",
            return_value=(FormalReviewDocument(), [], [], None),
        ), patch(
            "gui.main_window.mixins.formal_review_ops.companion_ops.QMessageBox.information",
            return_value=0,
        ):
            ok = window._run_companion_review_cycle(trigger="start_check", auto_sync_comments=True, redock=False)
        self.assertTrue(ok)
        self.assertTrue(window.sync_called)

    def test_legacy_blocking_guard_is_removed_from_start_review_path(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "gui/main_window/mixins/formal_review_ops/companion_ops.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("if not self._ensure_marker_basis_prerequisites_or_prompt():", source)
        self.assertNotIn("请先在左侧输入标号说明，再点击“开始审查”。", source)
        self.assertIn("_prepare_marker_basis_rule_inputs", source)

    def test_old_hard_block_strings_are_not_used_in_start_review_path(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "gui/main_window/mixins/formal_review_ops/companion_ops.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("形式审查：已阻断（启用引用基础规则时，标号说明不能为空）", source)

    def test_run_formal_review_call_passes_rule_params_marker_note_map_and_filtered_rules(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "gui/main_window/mixins/formal_review_ops/companion_ops.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("rule_params=dict(getattr(self, \"_formal_review_rule_params\", {}) or {})", source)
        self.assertIn("marker_note_map=marker_note_map", source)
        self.assertIn("enabled_rule_ids=enabled_rule_ids", source)

    def test_wordlist_hit_status_mentions_active_profile_without_word_comment_guidance(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "gui/main_window/mixins/formal_review_ops/companion_ops.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("词库命中 {wordlist_issue_count} 条，来自当前方案", source)
        self.assertIn("可在 设置 > 词库管理 调整", source)

    def test_no_message_box_warning_on_missing_marker_note(self) -> None:
        with patch("gui.main_window.mixins.formal_review_ops.companion_ops.QMessageBox.warning") as warning:
            ok, _window, _captured = self._run_review_and_capture_enabled_rules(marker_text="", patch_warning=False)
        self.assertTrue(ok)
        warning.assert_not_called()

    def test_empty_marker_continues_without_obsolete_prompt_switch(self) -> None:
        ok, _window, _captured = self._run_review_and_capture_enabled_rules(marker_text="")
        self.assertTrue(ok)

    def test_missing_marker_note_does_not_mutate_saved_rule_preferences(self) -> None:
        ok, window, captured = self._run_review_and_capture_enabled_rules(marker_text="")
        self.assertTrue(ok)
        self.assertTrue(window._formal_review_rule_enabled["claim.ref.marker_basis.missing"])
        self.assertTrue(window._formal_review_rule_enabled["claim.ref.term_basis.missing"])
        self.assertNotIn("claim.ref.marker_basis.missing", captured["enabled_rule_ids"])
        self.assertNotIn("claim.ref.term_basis.missing", captured["enabled_rule_ids"])

    def test_skipped_rule_labels_reset_between_reviews(self) -> None:
        ok1, window1, _captured1 = self._run_review_and_capture_enabled_rules(marker_text="")
        ok2, window2, _captured2 = self._run_review_and_capture_enabled_rules(marker_text="1、装置")
        self.assertTrue(ok1)
        self.assertTrue(ok2)
        self.assertEqual(["附图标记引用基础缺失", "所述后术语未对应标号说明"], window1._formal_review_skipped_rule_labels)
        self.assertEqual([], window2._formal_review_skipped_rule_labels)

    def test_skipped_rule_summary_appears_in_word_cycle_summary_dialog(self) -> None:
        window = _DummyReviewWindow(mode="word", marker_text="")
        window._formal_review_issues = []
        window._formal_review_skipped_rule_labels = ["附图标记引用基础缺失", "所述后术语未对应标号说明"]
        window._formal_review_last_sync_summary = {"trigger": "start_check", "written": 0, "skipped": 0, "failed": 0}
        with patch("gui.main_window.mixins.formal_review_ops.companion_ops.QMessageBox.information") as information:
            companion_ops._show_formal_review_cycle_summary_dialog(
                window,
                trigger="start_check",
                auto_sync_comments=True,
            )
        message = str(information.call_args.args[2])
        self.assertIn("本轮已跳过", message)
        self.assertIn("附图标记引用基础缺失", message)

    def test_existing_failed_review_still_does_not_sync(self) -> None:
        window = _DummyCompanionCycleWindow(review_ok=False)
        with patch(
            "gui.main_window.mixins.formal_review_ops.companion_ops.get_document_snapshot",
            return_value=(FormalReviewDocument(), [], [], None),
        ):
            ok = window._run_companion_review_cycle(trigger="start_check", auto_sync_comments=True, redock=False)
        self.assertFalse(ok)
        self.assertFalse(window.sync_called)

    def test_review_is_not_blocked_for_plain_and_word_when_required_marker_note_missing(self) -> None:
        for mode in ("plain_text", "word"):
            ok, window, _captured = self._run_review_and_capture_enabled_rules(marker_text="", mode=mode)
            self.assertTrue(ok)
            self.assertIn("已跳过", window.status_text)


if __name__ == "__main__":
    unittest.main()
