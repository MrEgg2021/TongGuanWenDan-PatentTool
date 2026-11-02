from __future__ import annotations

import os
import tempfile
import unittest
import zipfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from gui.main_window.mixins.official_docs_ops import task_tree_ops

    _PYSIDE6_AVAILABLE = True
except Exception:
    task_tree_ops = None  # type: ignore[assignment]
    _PYSIDE6_AVAILABLE = False


class _Host:
    _official_docs_last_import_ignored: list = []

    def _init_official_docs_state(self) -> None:
        self._official_docs_last_import_ignored = []

    def _ensure_official_docs_temp_root(self) -> str:
        return tempfile.mkdtemp(prefix="tgd_import_feedback_")

    def _get_official_docs_settings_snapshot(self, *, sync_current_type: bool = True) -> dict:
        return {}


@unittest.skipUnless(_PYSIDE6_AVAILABLE, "PySide6 不可用")
class OfficialDocsImportFeedbackTests(unittest.TestCase):
    def test_all_rejected_inputs_show_reason_dialog(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            zip_path = Path(td) / "unsafe.zip"
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("/absolute/notice.pdf", b"%PDF-1.4\n")

            calls: list[tuple[str, str, str]] = []

            class _RecordingBox:
                @staticmethod
                def warning(parent, title, text):
                    calls.append(("warning", title, text))

                @staticmethod
                def information(parent, title, text):
                    calls.append(("information", title, text))

            host = _Host()
            original = task_tree_ops.QMessageBox
            task_tree_ops.QMessageBox = _RecordingBox
            try:
                added = task_tree_ops._add_official_docs_inputs(host, [str(zip_path)])
            finally:
                task_tree_ops.QMessageBox = original

            self.assertEqual(added, 0)
            self.assertTrue(calls)
            self.assertEqual(calls[0][0], "warning")
            self.assertEqual(calls[0][1], "ZIP 未导入")
            self.assertIn("路径不安全", calls[0][2])

    def test_ignored_notice_text_keeps_reason_and_truncates(self) -> None:
        from core.official_docs.input_resolver import NoticeInputIgnored

        items = [
            NoticeInputIgnored(
                source_path=f"p{i}",
                display_name=f"f{i}.zip",
                reason="ZIP 无法导入：测试原因",
            )
            for i in range(10)
        ]

        text = task_tree_ops._official_docs_ignored_notice_text(items, limit=8)

        self.assertIn("f0.zip", text)
        self.assertIn("测试原因", text)
        self.assertIn("其余 2 项已跳过", text)
        self.assertNotIn("f9.zip", text)


if __name__ == "__main__":
    unittest.main()
