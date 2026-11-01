from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PySide6.QtCore import Qt

from core.cnipa_preview.codeset import (
    CODESET_UNAVAILABLE_NOTICE, LOCAL_CODESET_NOTICE, UNREACHABLE_BASE_PATH, CodesetState,
)
from core.cnipa_preview.models import PreviewDocument
from gui.main_window.mixins.preview_export_impl import ops_impl as ops


def _codeset_state(available: bool) -> CodesetState:
    if available:
        return CodesetState(True, "http://127.0.0.1:9999/public-base/codeset/findByCode", "ok")
    return CodesetState(False, UNREACHABLE_BASE_PATH, "未就绪")


def _local_codeset_state() -> CodesetState:
    return CodesetState(
        True, "http://127.0.0.1:5000/public-base/codeset/findByCode", "已启用自带本机码表", local_table=True,
    )


def _manager(state: CodesetState) -> SimpleNamespace:
    return SimpleNamespace(codeset_state=lambda: state)


class _FakePreviewItem:
    def __init__(self) -> None:
        self.data_by_role = {}
        self.tooltip = ""
        self.flags_value = Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def setData(self, role, value):
        self.data_by_role[role] = value

    def data(self, role):
        return self.data_by_role.get(role)

    def setCheckState(self, _state):
        return None

    def setFlags(self, flags):
        self.flags_value = flags

    def flags(self):
        return self.flags_value

    def setToolTip(self, text):
        self.tooltip = text


class _FakeLabel:
    def __init__(self, text: str = "") -> None:
        self._text = text

    def setText(self, text):
        self._text = str(text)

    def text(self):
        return self._text


class PreviewCodesetNoticeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / "case.zip"
        self.source.write_bytes(b"source")
        self.request_form = PreviewDocument("a", "110101", "发明专利请求书", "110101.xml")
        self.claims = PreviewDocument("b", "100001", "权利要求书", "100001.xml")
        self.items = {"a": _FakePreviewItem(), "b": _FakePreviewItem()}
        self.label = _FakeLabel("已就绪：case_预览.pdf")
        self.window = SimpleNamespace(
            _preview_last_zip_path=str(self.source),
            _preview_documents=(self.request_form, self.claims),
            _preview_export_selections={str(self.source): {"a", "b"}},
            _preview_pdf_map={},
            _preview_pdf_errors={},
            _preview_manifest_errors={},
            preview_doc_items=self.items,
            preview_action_summary_label=self.label,
        )

    def test_request_form_row_explains_missing_codeset_only_when_unavailable(self) -> None:
        with (
            patch.object(ops, "get_default_runtime_manager", return_value=_manager(_codeset_state(False))),
            patch.object(ops, "get_pdf_preview_mode", return_value="full"),
        ):
            ops.apply_preview_export_state(self.window)
        self.assertIn(CODESET_UNAVAILABLE_NOTICE, self.items["a"].tooltip)
        self.assertNotIn(CODESET_UNAVAILABLE_NOTICE, self.items["b"].tooltip)

        with (
            patch.object(ops, "get_default_runtime_manager", return_value=_manager(_codeset_state(True))),
            patch.object(ops, "get_pdf_preview_mode", return_value="full"),
        ):
            ops.apply_preview_export_state(self.window)
        self.assertNotIn(CODESET_UNAVAILABLE_NOTICE, self.items["a"].tooltip)
        self.assertIn("发明专利请求书", self.items["a"].tooltip)

    def test_render_completion_summary_appends_the_notice_only_when_needed(self) -> None:
        result = SimpleNamespace(
            documents=(self.request_form, self.claims),
            pdf_by_document_id={},
            errors_by_document_id={},
            passthrough_document_ids=frozenset(),
        )
        with (
            patch.object(ops, "get_pdf_preview_mode", return_value="full"),
            patch.object(ops, "get_default_runtime_manager", return_value=_manager(_codeset_state(False))),
        ):
            ops.on_preview_render_completed(self.window, result, str(self.source))
        self.assertIn(CODESET_UNAVAILABLE_NOTICE, self.label.text())

        with (
            patch.object(ops, "get_pdf_preview_mode", return_value="full"),
            patch.object(ops, "get_default_runtime_manager", return_value=_manager(_codeset_state(True))),
        ):
            ops.on_preview_render_completed(self.window, result, str(self.source))
        self.assertNotIn(CODESET_UNAVAILABLE_NOTICE, self.label.text())

    def test_notice_is_not_repeated_for_batches_without_request_forms(self) -> None:
        self.window._preview_documents = (self.claims,)
        with (
            patch.object(ops, "get_default_runtime_manager", return_value=_manager(_codeset_state(False))),
            patch.object(ops, "get_pdf_preview_mode", return_value="full"),
        ):
            ops.apply_preview_export_state(self.window)
        self.assertNotIn(CODESET_UNAVAILABLE_NOTICE, self.items["b"].tooltip)

    def test_notice_is_only_appended_once(self) -> None:
        with (
            patch.object(ops, "get_default_runtime_manager", return_value=_manager(_codeset_state(False))),
            patch.object(ops, "get_pdf_preview_mode", return_value="full"),
        ):
            ops.apply_preview_export_state(self.window)
        ops._append_codeset_notice(self.window)
        ops._append_codeset_notice(self.window)
        self.assertEqual(1, self.label.text().count(CODESET_UNAVAILABLE_NOTICE))

    def test_shipped_local_table_is_disclosed_only_for_request_forms(self) -> None:
        with (
            patch.object(ops, "get_default_runtime_manager", return_value=_manager(_local_codeset_state())),
            patch.object(ops, "get_pdf_preview_mode", return_value="full"),
        ):
            ops.apply_preview_export_state(self.window)
        self.assertIn(LOCAL_CODESET_NOTICE, self.items["a"].tooltip)
        self.assertNotIn(CODESET_UNAVAILABLE_NOTICE, self.items["a"].tooltip)
        self.assertNotIn(LOCAL_CODESET_NOTICE, self.items["b"].tooltip)

    def test_shipped_local_table_notice_is_appended_after_a_render(self) -> None:
        result = SimpleNamespace(
            documents=(self.request_form, self.claims),
            pdf_by_document_id={},
            errors_by_document_id={},
            passthrough_document_ids=frozenset(),
        )
        with (
            patch.object(ops, "get_pdf_preview_mode", return_value="full"),
            patch.object(ops, "get_default_runtime_manager", return_value=_manager(_local_codeset_state())),
        ):
            ops.on_preview_render_completed(self.window, result, str(self.source))
        self.assertIn(LOCAL_CODESET_NOTICE, self.label.text())
        self.assertNotIn(CODESET_UNAVAILABLE_NOTICE, self.label.text())

    def test_shipped_local_table_notice_is_not_shown_without_request_forms(self) -> None:
        self.window._preview_documents = (self.claims,)
        with (
            patch.object(ops, "get_default_runtime_manager", return_value=_manager(_local_codeset_state())),
            patch.object(ops, "get_pdf_preview_mode", return_value="full"),
        ):
            ops.apply_preview_export_state(self.window)
            ops._append_codeset_notice(self.window)
        self.assertNotIn(LOCAL_CODESET_NOTICE, self.items["b"].tooltip)
        self.assertNotIn(LOCAL_CODESET_NOTICE, self.label.text())


if __name__ == "__main__":
    unittest.main()
