from __future__ import annotations

import unittest
from unittest.mock import patch

from core.official_docs.models import ProcessItemResult, ProcessOptions, ProcessSummary
from gui.main_window.mixins.official_docs_ops import process_ops


class _DummyWindow:
    def __init__(self) -> None:
        self.events: list[str] = []
        self._official_docs_dirty = False
        self._official_docs_saved_settings = {}
        self._official_docs_leaves = {
            "leaf-1": {
                "zip_path": "D:/input/leaf-1.zip",
                "display_name": "leaf-1.zip",
                "checked": True,
            },
            "leaf-unchecked": {
                "zip_path": "D:/input/unchecked.zip",
                "display_name": "unchecked.zip",
                "checked": False,
            },
        }
        self._official_docs_last_process_leaf_ids: list[str] = []
        self._progress_scope = None
        self._processing_overlay = None
        self.official_docs_start_button = None

    def _init_official_docs_state(self) -> None:
        return None

    def _iter_checked_leaf_ids(self):
        return iter(["leaf-1"])

    def _build_official_docs_options(self, *, use_saved: bool) -> ProcessOptions:
        self.assert_use_saved = use_saved
        return ProcessOptions(
            summary_root_dir="D:/summary",
            archive_root_dir="D:/archive",
            write_summary=True,
            write_archive=False,
            confirm_each=False,
        )

    def _validate_official_docs_settings(self, _settings):
        return []

    def _build_collision_resolver(self):
        return lambda _summary, _archive: "rename"

    def _reset_cancel_state(self) -> None:
        return None

    def _show_processing_overlay(self, _status: str, _detail: str) -> None:
        return None

    def _hide_processing_overlay(self) -> None:
        return None

    def _collect_done_dirs(self, _summary: ProcessSummary) -> list[str]:
        return []

    def _cache_official_docs_process_results(self, _summary: ProcessSummary) -> None:
        return None

    def on_official_docs_clear_items(self) -> None:
        self.events.append("clear")

    def _refresh_official_docs_page_from_state(self) -> None:
        self.events.append("refresh")


class OfficialDocsAutoClearAfterCompletionTests(unittest.TestCase):
    def test_result_dialog_closes_before_whole_task_list_is_cleared(self) -> None:
        window = _DummyWindow()
        summary = ProcessSummary(
            total=1,
            failed=1,
            items=[
                ProcessItemResult(
                    source_zip_path="D:/input/leaf-1.zip",
                    status="fail",
                    reason="sample failure",
                )
            ],
        )

        with (
            patch.object(process_ops, "process_official_notice_archives", return_value=summary),
            patch.object(process_ops, "show_official_docs_done_dialog", side_effect=lambda *_args, **_kwargs: window.events.append("dialog")),
            patch.object(process_ops, "QApplication"),
        ):
            process_ops.on_official_docs_start_processing(window)

        self.assertEqual(window.events, ["dialog", "clear"])

    def test_processing_exception_keeps_task_list(self) -> None:
        window = _DummyWindow()

        with (
            patch.object(process_ops, "process_official_notice_archives", side_effect=RuntimeError("boom")),
            patch.object(process_ops, "show_blocking_alert_modal"),
            patch.object(process_ops, "QApplication"),
        ):
            process_ops.on_official_docs_start_processing(window)

        self.assertNotIn("clear", window.events)


if __name__ == "__main__":
    unittest.main()
