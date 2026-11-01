from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtWidgets import QAbstractItemView, QApplication

from core.cnipa_preview.models import PreviewDocument
from gui.main_window.mixins.preview_export_impl import ops_impl
from gui.ui_layout_impl.preview_page import (
    _PREVIEW_STATUS_ROLE,
    _PREVIEW_STATUS_TONE_ROLE,
    build_preview_page,
    rebuild_preview_document_rows,
)


class _PreviewWindow:
    def __init__(self) -> None:
        self._preview_last_zip_path = "case.zip"
        self._preview_documents = tuple(
            PreviewDocument(str(index), f"10{index:04d}", f"文件名称 {index}", f"{index}.xml")
            for index in range(1, 7)
        )
        document_ids = {document.id for document in self._preview_documents}
        self._preview_export_selections = {"case.zip": document_ids}
        self._preview_pdf_map = {}
        self._preview_pdf_errors = {}
        self._preview_manifest_errors = {}
        self._preview_document_orders = {}
        self._preview_merged_temp_pdf_path = ""
        self._preview_reorder_refresh_pending = False

    def _on_preview_doc_check_toggled(self, document_id: str, checked: bool) -> None:
        return None

    def _on_preview_documents_reordered(self) -> None:
        ops_impl.on_preview_documents_reordered(self)


class PreviewDocumentDragLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_native_move_keeps_every_document_and_list_can_expand(self) -> None:
        window = _PreviewWindow()
        page = build_preview_page(window)
        rebuild_preview_document_rows(window, window._preview_documents)
        ops_impl.apply_preview_export_state(window)

        document_list = window.preview_document_list
        self.assertGreater(document_list.maximumHeight(), 460)
        self.assertTrue(document_list.showDropIndicator())
        self.assertFalse(document_list.dragDropOverwriteMode())
        self.assertTrue(
            all(
                not bool(document_list.item(index).flags() & Qt.ItemIsDropEnabled)
                for index in range(document_list.count())
            )
        )
        self.assertTrue(
            all(
                bool(document_list.item(index).flags() & Qt.ItemIsDragEnabled)
                for index in range(document_list.count())
            )
        )
        self.assertTrue(document_list.model().moveRows(QModelIndex(), 0, 1, QModelIndex(), 4))
        self.app.processEvents()
        self.app.processEvents()

        self.assertEqual(
            [document_list.item(index).data(Qt.UserRole) for index in range(document_list.count())],
            ["2", "3", "4", "1", "5", "6"],
        )
        self.assertTrue(
            all(document_list.itemWidget(document_list.item(index)) is None for index in range(document_list.count()))
        )
        self.assertEqual(len(window.preview_doc_items), 6)
        self.assertTrue(all(item.checkState() == Qt.Checked for item in window.preview_doc_items.values()))
        page.deleteLater()

    def test_attachment_rows_report_pending_and_merged_states(self) -> None:
        window = _PreviewWindow()
        page = build_preview_page(window)
        attachment = window._preview_documents[0]
        window._preview_passthrough_ids = frozenset({attachment.id})
        rebuild_preview_document_rows(window, window._preview_documents)
        ops_impl.apply_preview_export_state(window)

        item = window.preview_doc_items[attachment.id]
        plain_item = window.preview_doc_items[window._preview_documents[1].id]
        self.assertEqual(item.data(_PREVIEW_STATUS_ROLE), "待并入")
        self.assertEqual(item.data(_PREVIEW_STATUS_TONE_ROLE), "info")
        self.assertTrue(bool(item.flags() & Qt.ItemIsEnabled))
        self.assertEqual(plain_item.data(_PREVIEW_STATUS_ROLE), "待生成")

        window._preview_pdf_map = {attachment.id: b"%PDF-1.7\nattachment"}
        ops_impl.apply_preview_export_state(window)
        self.assertEqual(item.data(_PREVIEW_STATUS_ROLE), "已并入")
        self.assertEqual(item.data(_PREVIEW_STATUS_TONE_ROLE), "info")
        page.deleteLater()

    def test_lightweight_mode_keeps_four_document_list_draggable_and_ordered(self) -> None:
        window = _PreviewWindow()
        page = build_preview_page(window)
        with patch.object(ops_impl, "get_pdf_preview_mode", return_value="legacy"):
            ops_impl.apply_preview_mode_ui(window)

        self.assertEqual(window.preview_document_list.dragDropMode(), QAbstractItemView.InternalMove)
        window._preview_document_orders["case.zip"] = ("100004", "100001", "100002", "100003")
        ops_impl.prepare_legacy_preview_case(window, "case.zip")

        self.assertEqual(
            [document.id for document in window._preview_documents],
            ["100004", "100001", "100002", "100003"],
        )
        page.deleteLater()

    def test_page_construction_does_not_start_runtime_before_agreement(self) -> None:
        for mode in ("legacy", "full"):
            with self.subTest(mode=mode):
                window = _PreviewWindow()
                window._apply_preview_mode_ui = Mock()
                window._ensure_full_preview_prewarm = Mock()
                with patch("gui.ui_layout_impl.preview_page.get_pdf_preview_mode", return_value=mode), \
                     patch("gui.ui_layout_impl.preview_page.QTimer.singleShot") as schedule:
                    page = build_preview_page(window)
                scheduled = [call.args[1] for call in schedule.call_args_list]
                self.assertNotIn(window._ensure_full_preview_prewarm, scheduled)
                page.deleteLater()


if __name__ == "__main__":
    unittest.main()
