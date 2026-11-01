from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QFrame, QLabel, QWidget

    _PYSIDE6_AVAILABLE = True
except Exception:
    QApplication = None  # type: ignore[assignment]
    QFrame = object  # type: ignore[assignment]
    QLabel = object  # type: ignore[assignment]
    QWidget = object  # type: ignore[assignment]
    _PYSIDE6_AVAILABLE = False

from gui.main_window.mixins.progress_mixin import ProgressMixin


class _OverlayWindow(QWidget, ProgressMixin):
    def __init__(self, scope: str | None, preview_kind: str = "") -> None:
        super().__init__()
        self._processing_overlay = None
        self._progress_scope = scope
        self._preview_overlay_kind = preview_kind
        self._header_precheck_stage = "预检查完成"
        self._header_precheck_summary = "页眉检测：申请信息确认页✘  权利要求书✓"

    def get_optimize_equation_centering_enabled(self) -> bool:
        return False

    def get_description_paragraph_split_mode(self) -> str:
        return "word"


@unittest.skipUnless(_PYSIDE6_AVAILABLE, "PySide6 not installed")
class ProcessingOverlayHeaderScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def _update_overlay(self, scope: str | None):
        window = _OverlayWindow(scope)
        self.addCleanup(window._hide_processing_overlay)
        window._show_processing_overlay("正在处理...", "准备开始...")
        window._update_processing_overlay(28, "正在处理 (2/7)", "解析：sample.zip")

        overlay = window._processing_overlay
        self.assertIsNotNone(overlay)
        header_box = overlay.findChild(QFrame, "processingHeaderBox")
        header_stage = overlay.findChild(QLabel, "processingHeaderStage")
        header_summary = overlay.findChild(QLabel, "processingHeaderSummary")
        self.assertIsNotNone(header_box)
        self.assertIsNotNone(header_stage)
        self.assertIsNotNone(header_summary)
        return header_box, header_stage, header_summary

    def test_only_document_conversion_scopes_show_header_precheck(self) -> None:
        for scope in ("single", "batch"):
            with self.subTest(scope=scope):
                header_box, header_stage, header_summary = self._update_overlay(scope)
                self.assertFalse(header_box.isHidden())
                self.assertEqual(header_stage.text(), "预检查完成")
                self.assertIn("页眉检测", header_summary.text())

    def test_non_conversion_scopes_hide_stale_header_precheck(self) -> None:
        for scope in ("official_docs", "word_health", "response_correction", None):
            with self.subTest(scope=scope):
                header_box, header_stage, header_summary = self._update_overlay(scope)
                self.assertTrue(header_box.isHidden())
                self.assertEqual(header_stage.text(), "")
                self.assertEqual(header_summary.text(), "")

    def test_preview_warning_is_shown_only_for_full_renderer_work(self) -> None:
        for preview_kind, expected_visible in (("legacy", False), ("manifest", False), ("full", True)):
            with self.subTest(preview_kind=preview_kind):
                window = _OverlayWindow("preview", preview_kind)
                self.addCleanup(window._hide_processing_overlay)
                window._show_processing_overlay("正在处理...", "准备开始...")
                warning = window._processing_overlay.findChild(QLabel, "processingWarnLabel")
                self.assertIsNotNone(warning)
                self.assertEqual(not warning.parentWidget().isHidden(), expected_visible)
                if expected_visible:
                    self.assertIn("正在生成文书 PDF", warning.text())
                else:
                    self.assertEqual("", warning.text())


if __name__ == "__main__":
    unittest.main()
