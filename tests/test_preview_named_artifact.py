import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import fitz
from PySide6.QtCore import Qt

from core.cnipa_preview.models import PreviewDocument
from gui.main_window.mixins.preview_export_impl import ops_impl as ops
from gui.ui_layout_impl.preview_page import _PREVIEW_STATUS_ROLE, _PREVIEW_STATUS_TONE_ROLE


def pdf_bytes(text):
    with fitz.open() as document:
        page = document.new_page()
        page.insert_text((40, 40), text)
        return document.tobytes()


class _FakePreviewItem:
    """Records the row state written by apply_preview_export_state without a Qt list widget."""

    def __init__(self):
        self.data_by_role = {}
        self.flags_value = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        self.check_state = Qt.Unchecked

    def setData(self, role, value):
        self.data_by_role[role] = value

    def data(self, role):
        return self.data_by_role.get(role)

    def setCheckState(self, state):
        self.check_state = state

    def setFlags(self, flags):
        self.flags_value = flags

    def flags(self):
        return self.flags_value

    def setToolTip(self, text):
        self.tooltip = text


class NamedPreviewArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / "case.zip"
        self.source.write_bytes(b"source")
        self.docs = (PreviewDocument("a", "100001", "权利要求书", "100001.xml"),
                     PreviewDocument("b", "100002", "说明书", "100002.xml"))
        self.window = SimpleNamespace(
            _preview_last_zip_path=str(self.source), _preview_documents=self.docs,
            _preview_export_selections={str(self.source): {"a", "b"}},
            _preview_pdf_map={"a": pdf_bytes("claims"), "b": pdf_bytes("description")},
            _ensure_preview_temp_root=lambda: self.temp.name,
            _preview_cases=[{}], _get_selected_preview_leaf=lambda: (None, {"zip_path": str(self.source)}),
        )
    def test_named_artifact_reused_and_reorder_preserves_open_revision(self):
        first = Path(ops._materialize_preview_pdf(self.window))
        original = first.read_bytes()
        self.assertEqual(first.name, "case_预览.pdf")
        with patch.object(ops, "_write_merged_pdf", side_effect=AssertionError("redundant merge")):
            self.assertEqual(ops._materialize_preview_pdf(self.window), str(first))
        self.window._preview_documents = self.docs[::-1]
        second = Path(ops._materialize_preview_pdf(self.window))
        self.assertNotEqual(first, second)
        self.assertEqual(first.read_bytes(), original)
        with fitz.open(second) as document:
            self.assertIn("description", document[0].get_text())

    def test_missing_selected_pdf_does_not_materialize_partial_success(self):
        del self.window._preview_pdf_map["b"]
        self.assertEqual(ops._materialize_preview_pdf(self.window), "")
        self.window._preview_export_selections[str(self.source)] = {"a"}
        self.assertEqual(Path(ops._materialize_preview_pdf(self.window)).name, "case_预览.pdf")

    def test_full_save_copies_exact_bytes_without_render_or_merge(self):
        first = Path(ops._materialize_preview_pdf(self.window))
        destination = Path(self.temp.name) / "saved.pdf"
        with patch.object(ops, "get_pdf_preview_mode", return_value="full"), \
             patch.object(ops.QFileDialog, "getSaveFileName", return_value=(str(destination), "")), \
             patch.object(ops, "_write_merged_pdf", side_effect=AssertionError("redundant merge")):
            ops.on_preview_export_merged_pdf(self.window)
        self.assertEqual(first.read_bytes(), destination.read_bytes())

    def test_reopen_uses_existing_pdf_and_only_new_selection_renders(self):
        with patch.object(ops, "get_pdf_preview_mode", return_value="full"), \
             patch.object(ops, "_open_preview_with_system_viewer") as opened, \
             patch.object(ops, "preview_single_case") as render:
            ops.on_preview_start_selected_case(self.window)
            opened.assert_called_once()
            render.assert_not_called()
            del self.window._preview_pdf_map["b"]
            self.window._preview_pdf_errors = {}
            with patch.object(ops, "apply_preview_export_state"):
                ops.on_preview_start_selected_case(self.window)
            self.assertEqual(render.call_args.kwargs["selected_document_ids"], ("b",))

    def test_source_change_blocks_saving_stale_preview(self):
        stat = self.source.stat()
        self.window._preview_source_signature = (stat.st_size, stat.st_mtime_ns)
        ops._materialize_preview_pdf(self.window)
        self.source.write_bytes(b"changed-source")
        with patch.object(ops, "get_pdf_preview_mode", return_value="full"), \
             patch.object(ops, "show_blocking_alert_modal") as alert, \
             patch.object(ops.QFileDialog, "getSaveFileName") as save:
            ops.on_preview_export_merged_pdf(self.window)
        save.assert_not_called()
        self.assertIn("发生变化", alert.call_args.args[2])

    def test_single_document_preserves_original_bytes(self):
        self.window._preview_export_selections[str(self.source)] = {"a"}
        artifact = Path(ops._materialize_preview_pdf(self.window))
        self.assertEqual(artifact.read_bytes(), self.window._preview_pdf_map["a"])

    def test_bundle_uses_original_child_name_and_parent_save_directory(self):
        self.window._get_preview_leaf_by_zip_path = lambda _path: (
            {"source_path": str(Path(self.temp.name) / "bundle.zip")}, {"name": "original-case"},
        )
        artifact = Path(ops._materialize_preview_pdf(self.window))
        self.assertEqual(artifact.name, "original-case_预览.pdf")
        self.assertEqual(ops._preview_source_details(self.window)[1], self.temp.name)

    def test_attachment_row_reports_pending_then_merged_into_the_artifact(self):
        attachment, sibling = self.docs
        items = {attachment.id: _FakePreviewItem(), sibling.id: _FakePreviewItem()}
        self.window.preview_doc_items = items
        self.window._preview_passthrough_ids = frozenset({attachment.id})
        self.window._preview_export_selections[str(self.source)] = {attachment.id}
        self.window._preview_pdf_map = {}

        with patch.object(ops, "get_pdf_preview_mode", return_value="full"):
            ops.apply_preview_export_state(self.window)
        self.assertEqual(items[attachment.id].data(_PREVIEW_STATUS_ROLE), "待并入")
        self.assertEqual(items[attachment.id].data(_PREVIEW_STATUS_TONE_ROLE), "info")
        self.assertEqual(items[sibling.id].data(_PREVIEW_STATUS_ROLE), "待生成")

        self.window._preview_pdf_map = {attachment.id: pdf_bytes("attachment")}
        with patch.object(ops, "get_pdf_preview_mode", return_value="full"):
            ops.apply_preview_export_state(self.window)
        self.assertEqual(items[attachment.id].data(_PREVIEW_STATUS_ROLE), "已并入")
        self.assertEqual(items[attachment.id].data(_PREVIEW_STATUS_TONE_ROLE), "info")
        artifact = self.window._preview_merged_temp_pdf_path
        self.assertEqual(Path(artifact).read_bytes(), self.window._preview_pdf_map[attachment.id])


if __name__ == "__main__":
    unittest.main()
