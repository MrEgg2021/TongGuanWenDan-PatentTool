from __future__ import annotations

import os
import time
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QComboBox, QLabel, QLineEdit, QProgressBar, QPushButton, QTableWidget, QWidget

    _PYSIDE6_AVAILABLE = True
except Exception:
    QApplication = None  # type: ignore[assignment]
    QComboBox = object  # type: ignore[assignment]
    QLabel = object  # type: ignore[assignment]
    QLineEdit = object  # type: ignore[assignment]
    QProgressBar = object  # type: ignore[assignment]
    QPushButton = object  # type: ignore[assignment]
    QTableWidget = object  # type: ignore[assignment]
    QWidget = object  # type: ignore[assignment]
    _PYSIDE6_AVAILABLE = False

from core.response_correction import NoticeMeta, PackageResult, ParsedNotice
from core.word_startup_health import WordStartupHealthResult
from core.word_engine import WordComHijackedError
from gui.app_impl.response_correction_imports import StagedImportItem
from gui.main_window.mixins.progress_mixin import ProgressMixin
from gui.main_window.mixins.response_correction_mixin import ResponseCorrectionMixin


def _ok_word_health() -> WordStartupHealthResult:
    return WordStartupHealthResult(
        ok=True,
        pid=2345,
        binding_progid="Word.Application.16",
        error=None,
        killed_before_check=False,
    )


def _failed_word_health(reason_code: str = "word_pid_missing_unclaimed") -> WordStartupHealthResult:
    return WordStartupHealthResult(
        ok=False,
        pid=None,
        binding_progid="Word.Application",
        error="Word health failed.",
        killed_before_check=False,
        reason_code=reason_code,
        user_message="Word health failed.",
        technical_detail="Word health failed.",
    )


class _DummyWindow(ResponseCorrectionMixin):
    def __init__(self) -> None:
        self.alerts: list[tuple[str, str]] = []
        self.worker_calls: list[tuple[str, str]] = []
        self._response_notice_meta = NoticeMeta()
        self._correction_notice_meta = NoticeMeta()
        self._active_response_notice_meta = NoticeMeta()
        self._active_correction_notice_meta = NoticeMeta()

        for prefix in ("response", "correction", "active_response", "active_correction"):
            setattr(self, f"{prefix}_notice_edit", QLineEdit())
            setattr(self, f"{prefix}_application_no_edit", QLineEdit())
            setattr(self, f"{prefix}_title_edit", QLineEdit())
            setattr(self, f"{prefix}_applicant_edit", QLineEdit())
            setattr(self, f"{prefix}_notice_name_edit", QLineEdit())
            setattr(self, f"{prefix}_issue_date_edit", QLineEdit())
            setattr(self, f"{prefix}_doc_serial_edit", QLineEdit())
            setattr(self, f"{prefix}_status_label", QLabel())
            setattr(self, f"{prefix}_output_dir_edit", QLineEdit("D:/out"))
            setattr(self, f"{prefix}_start_btn", QPushButton())
            setattr(self, f"{prefix}_notice_section_body", QWidget())
            toggle = QPushButton()
            toggle.setCheckable(True)
            setattr(self, f"{prefix}_notice_section_toggle", toggle)
            materials = QTableWidget(0, 7)
            setattr(self, f"{prefix}_materials_table", materials)
            staged = QTableWidget(0, 6)
            setattr(self, f"{prefix}_staged_files_table", staged)
            uploaded = QTableWidget(0, 6)
            setattr(self, f"{prefix}_uploaded_files_table", uploaded)
            patent_type_combo = QComboBox()
            patent_type_combo.addItem("发明", "invention")
            patent_type_combo.addItem("实用新型", "utility_model")
            setattr(self, f"{prefix}_patent_type_combo", patent_type_combo)

        self.correction_items_table = QTableWidget(0, 4)
        self.active_correction_items_table = QTableWidget(0, 4)

    def _start_response_correction_worker(self, task_callable, *, flow: str, package_label: str, **_kwargs) -> bool:
        self.worker_calls.append((flow, package_label))
        return True


class _WorkerWindow(QWidget, ProgressMixin, ResponseCorrectionMixin):
    def __init__(self) -> None:
        super().__init__()
        self.alerts: list[tuple[str, str]] = []
        self._processing_overlay = None
        self._result_overlay = None
        self._progress_scope = None
        self._response_correction_busy = False
        self._processing_mode = "single"
        self._current_file_path = ""
        self._current_file_display_text = ""
        self._cancel_requested = False
        self._modern_shell = None
        self.status_label = QLabel("")
        self.detail_label = QLabel("")
        self.batch_status_label = QLabel("")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self._detail_label_style_normal = ""
        self._detail_label_style_error = ""
        self._batch_status_style_normal = ""
        self._batch_status_style_error = ""
        self._response_notice_meta = NoticeMeta()
        for prefix in ("response", "correction", "active_response", "active_correction"):
            setattr(self, f"{prefix}_status_label", QLabel(""))
            setattr(self, f"{prefix}_start_btn", QPushButton())
            setattr(self, f"{prefix}_confirm_imports_btn", QPushButton())

    def get_optimize_equation_centering_enabled(self) -> bool:
        return False

    def get_description_paragraph_split_mode(self) -> str:
        return "word"


@unittest.skipUnless(_PYSIDE6_AVAILABLE, "PySide6 not installed")
class ResponseCorrectionMixinTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def _make_window(self) -> _DummyWindow:
        return _DummyWindow()

    def _pump_until(self, predicate, timeout: float = 5.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self._app.processEvents()
            if predicate():
                return True
            time.sleep(0.01)
        self._app.processEvents()
        return bool(predicate())

    def test_parse_notice_auto_expands_notice_section(self) -> None:
        window = self._make_window()
        window.response_notice_edit.setText("D:/notice.zip")
        window.response_notice_section_body.setVisible(False)
        window.response_notice_section_toggle.setChecked(False)
        parsed = ParsedNotice(
            source_path="D:/notice.zip",
            meta=NoticeMeta(
                application_no="2026101841613",
                invention_title="Example",
                applicant="Applicant",
                notice_name="审查意见通知书",
                notice_code="210401",
                issue_date="20260319",
                doc_serial="2026031900436760",
                patent_type="invention",
            ),
            meta_source="list_xml",
        )

        with patch("gui.main_window.mixins.response_correction_mixin.parse_notice_source", return_value=parsed):
            window._parse_notice_for_flow("response")

        self.assertTrue(window.response_notice_section_body.isVisible())
        self.assertTrue(window.response_notice_section_toggle.isChecked())
        self.assertEqual(window.response_application_no_edit.text(), "2026101841613")

    def test_parse_notice_warns_when_issue_date_missing(self) -> None:
        window = self._make_window()
        parsed = ParsedNotice(
            source_path="D:/notice.pdf",
            meta=NoticeMeta(
                application_no="2026101841613",
                invention_title="Example",
                applicant="Applicant",
                notice_name="审查意见通知书",
                notice_code="210401",
                issue_date="",
                doc_serial="2026031900436760",
                patent_type="invention",
            ),
            meta_source="pdf_fallback",
        )

        with patch("gui.main_window.mixins.response_correction_mixin.parse_notice_source", return_value=parsed):
            window.response_notice_edit.setText("D:/notice.pdf")
            window._parse_notice_for_flow("response")

        self.assertIn("发文日", window.response_status_label.text())
        self.assertIn("补录", window.response_status_label.text())

    def test_parse_notice_warns_when_doc_serial_missing(self) -> None:
        window = self._make_window()
        parsed = ParsedNotice(
            source_path="D:/notice.pdf",
            meta=NoticeMeta(
                application_no="2026101841613",
                invention_title="Example",
                applicant="Applicant",
                notice_name="审查意见通知书",
                notice_code="210401",
                issue_date="20260319",
                doc_serial="",
                patent_type="invention",
            ),
            meta_source="pdf_fallback",
        )

        with patch("gui.main_window.mixins.response_correction_mixin.parse_notice_source", return_value=parsed):
            window.response_notice_edit.setText("D:/notice.pdf")
            window._parse_notice_for_flow("response")

        self.assertIn("发文序号", window.response_status_label.text())
        self.assertIn("补录", window.response_status_label.text())

    def test_confirm_imports_blocks_duplicate_slot_mapping(self) -> None:
        window = self._make_window()
        setattr(
            window,
            "_response_staged_import_items",
            [
                StagedImportItem(source_path="D:/claims-a.docx", source_kind="file", selected_role="100001"),
                StagedImportItem(source_path="D:/claims-b.docx", source_kind="file", selected_role="100001"),
            ],
        )

        with patch(
            "gui.main_window.mixins.response_correction_mixin.show_blocking_alert_modal",
            side_effect=lambda _parent, title, message, **_kwargs: window.alerts.append((title, message)),
        ):
            ok = window._confirm_staged_imports_for_flow("response")

        self.assertFalse(ok)
        self.assertEqual(window._slot_state_for_flow("response"), {})
        self.assertTrue(window.alerts)

    def test_confirm_imports_writes_confirmed_slot_state_only_after_confirmation(self) -> None:
        window = self._make_window()
        item = StagedImportItem(source_path="D:/claims.docx", source_kind="file", selected_role="100001")
        setattr(window, "_response_staged_import_items", [item])

        self.assertEqual(window._slot_state_for_flow("response"), {})

        ok = window._confirm_staged_imports_for_flow("response")

        self.assertTrue(ok)
        self.assertIn("100001", window._slot_state_for_flow("response"))
        self.assertEqual(window.response_materials_table.rowCount(), 1)
        self.assertEqual(window.response_materials_table.item(0, 4).text(), "已上传")

    def test_confirm_imports_without_selected_rows_clears_existing_confirmed_materials(self) -> None:
        window = self._make_window()
        setattr(
            window,
            "_response_document_slots",
            {
                "100001": {
                    "slot_code": "100001",
                    "display_name": "权利要求书",
                    "path": "D:/claims.docx",
                    "preconverted": "0",
                    "source_kind": "word",
                    "created_at": "2026-04-10 11:00:00",
                }
            },
        )
        setattr(
            window,
            "_response_opinion_material",
            {
                "path": "D:/opinion.docx",
                "display_name": "意见陈述书",
                "source_name": "opinion.docx",
                "source_kind": "word",
                "created_at": "2026-04-10 11:00:00",
                "final_path": "D:/opinion.docx",
            },
        )
        setattr(window, "_response_staged_import_items", [])

        ok = window._confirm_staged_imports_for_flow("response")

        self.assertTrue(ok)
        self.assertEqual(window._slot_state_for_flow("response"), {})
        self.assertIsNone(getattr(window, "_response_opinion_material", None))

    def test_refresh_materials_table_registers_combo_wheel_blocker_and_clear_button(self) -> None:
        window = self._make_window()
        setattr(
            window,
            "_response_staged_import_items",
            [StagedImportItem(source_path="D:/claims.docx", source_kind="word", selected_role="100001")],
        )

        window._refresh_materials_table("response")

        combo_wrapper = window.response_materials_table.cellWidget(0, 3)
        clear_wrapper = window.response_materials_table.cellWidget(0, 1)
        combo = combo_wrapper.findChild(QComboBox) if combo_wrapper is not None else None
        clear_btn = clear_wrapper.findChild(QPushButton) if clear_wrapper is not None else None
        blocker = getattr(window, "_response_combo_wheel_blocker", None)
        self.assertIsInstance(combo, QComboBox)
        self.assertIsInstance(clear_btn, QPushButton)
        self.assertEqual(clear_btn.text(), "清除")
        self.assertIsNotNone(blocker)
        self.assertIn(combo, getattr(blocker, "_targets", set()))
        self.assertGreaterEqual(window.response_materials_table.verticalHeader().defaultSectionSize(), 52)
        self.assertGreaterEqual(clear_btn.minimumHeight(), 38)
        self.assertGreaterEqual(combo.minimumHeight(), 38)

        clear_layout = clear_wrapper.layout() if clear_wrapper is not None else None
        combo_layout = combo_wrapper.layout() if combo_wrapper is not None else None
        self.assertIsNotNone(clear_layout)
        self.assertIsNotNone(combo_layout)
        self.assertEqual(clear_layout.contentsMargins().top(), 0)
        self.assertEqual(clear_layout.contentsMargins().bottom(), 0)
        self.assertEqual(combo_layout.contentsMargins().top(), 0)
        self.assertEqual(combo_layout.contentsMargins().bottom(), 0)
        self.assertGreaterEqual(
            window.response_materials_table.verticalHeader().defaultSectionSize(),
            combo.sizeHint().height() + 10,
        )

    def test_ingest_import_paths_auto_parses_notice_and_only_stages_remaining_materials(self) -> None:
        window = self._make_window()
        parsed = ParsedNotice(
            source_path="D:/notice.zip",
            meta=NoticeMeta(
                application_no="2026101841613",
                invention_title="Example",
                applicant="Applicant",
                notice_name="审查意见通知书",
                notice_code="210401",
                issue_date="20260319",
                doc_serial="2026031900436760",
                patent_type="invention",
            ),
            meta_source="list_xml",
        )

        with patch(
            "gui.main_window.mixins.response_correction_mixin.collect_response_correction_files",
            return_value=(["D:/notice.zip", "D:/claims.docx"], []),
        ), patch(
            "gui.main_window.mixins.response_correction_mixin.parse_notice_source",
            return_value=parsed,
        ), patch(
            "gui.main_window.mixins.response_correction_mixin.show_drop_ignored_message",
            return_value=None,
        ):
            window._ingest_import_paths_for_flow("response", ["D:/folder"])

        self.assertEqual(window.response_notice_edit.text(), "D:/notice.zip")
        self.assertEqual(window.response_application_no_edit.text(), "2026101841613")
        self.assertEqual(window.response_materials_table.rowCount(), 1)
        items = getattr(window, "_response_staged_import_items")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].source_path, "D:/claims.docx")

    def test_ingest_import_paths_active_response_auto_prefills_supported_other_notice(self) -> None:
        window = self._make_window()
        parsed = ParsedNotice(
            source_path="D:/acceptance.pdf",
            meta=NoticeMeta(
                application_no="2026101841613",
                invention_title="Accepted Title",
                applicant="Accepted Applicant",
                notice_name="专利申请受理通知书",
                notice_code="200101",
                issue_date="20260319",
                doc_serial="2026031900436760",
                patent_type="invention",
            ),
            meta_source="pdf_fallback",
        )

        with patch(
            "gui.main_window.mixins.response_correction_mixin.collect_response_correction_files",
            return_value=(["D:/acceptance.pdf", "D:/claims.docx"], []),
        ), patch(
            "gui.main_window.mixins.response_correction_mixin.parse_notice_source",
            return_value=parsed,
        ), patch(
            "gui.main_window.mixins.response_correction_mixin.show_drop_ignored_message",
            return_value=None,
        ):
            window._ingest_import_paths_for_flow("active_response", ["D:/folder"])

        self.assertEqual(window.active_response_application_no_edit.text(), "2026101841613")
        self.assertEqual(window.active_response_title_edit.text(), "Accepted Title")
        self.assertEqual(window.active_response_applicant_edit.text(), "Accepted Applicant")
        self.assertEqual(window.active_response_patent_type_combo.currentData(), "invention")
        self.assertEqual(window.active_response_notice_name_edit.text(), "")
        self.assertEqual(window.active_response_materials_table.rowCount(), 1)
        items = getattr(window, "_active_response_staged_import_items")
        self.assertEqual([item.source_path for item in items], ["D:/claims.docx"])
        self.assertIn("自动解析", window.active_response_status_label.text())
        self.assertIn("acceptance.pdf", window.active_response_status_label.text())

    def test_apply_parsed_notice_to_active_flow_prefills_non_empty_fields_only(self) -> None:
        window = self._make_window()
        window.active_response_application_no_edit.setText("2024000000000")
        window.active_response_title_edit.setText("Manual Title")
        window.active_response_applicant_edit.setText("Manual Applicant")
        window.active_response_patent_type_combo.setCurrentIndex(1)

        parsed = ParsedNotice(
            source_path="D:/acceptance.pdf",
            meta=NoticeMeta(
                application_no="2026101841613",
                invention_title="",
                applicant="",
                notice_name="专利申请受理通知书",
                notice_code="200101",
                issue_date="20260319",
                doc_serial="2026031900436760",
                patent_type="",
            ),
            meta_source="pdf_fallback",
        )

        window._apply_parsed_notice_to_flow(
            "active_response",
            parsed,
            source_path="D:/acceptance.pdf",
            status_text="active prefill",
        )

        self.assertEqual(window.active_response_application_no_edit.text(), "2026101841613")
        self.assertEqual(window.active_response_title_edit.text(), "Manual Title")
        self.assertEqual(window.active_response_applicant_edit.text(), "Manual Applicant")
        self.assertEqual(window.active_response_patent_type_combo.currentData(), "utility_model")
        self.assertEqual(window.active_response_notice_name_edit.text(), "")
        self.assertEqual(window.active_response_issue_date_edit.text(), "")
        self.assertEqual(window.active_response_doc_serial_edit.text(), "")

    def test_ingest_import_paths_ignores_comparison_materials_and_non_notice_pdf(self) -> None:
        window = self._make_window()

        with patch(
            "gui.main_window.mixins.response_correction_mixin.collect_response_correction_files",
            return_value=(["D:/修改对照页.docx", "D:/普通附件.pdf", "D:/claims.docx"], []),
        ), patch(
            "gui.main_window.mixins.response_correction_mixin.show_drop_ignored_message",
            return_value=None,
        ) as mocked_ignored:
            window._ingest_import_paths_for_flow("response", ["D:/folder"])

        items = getattr(window, "_response_staged_import_items")
        self.assertEqual([item.source_path for item in items], ["D:/claims.docx"])
        ignored_messages = mocked_ignored.call_args.args[2]
        self.assertEqual(len(ignored_messages), 1)
        self.assertTrue(any("普通附件.pdf" in text for text in ignored_messages))
        self.assertFalse(any("修改对照页" in text for text in ignored_messages))

    def test_remove_material_item_updates_single_table(self) -> None:
        window = self._make_window()
        setattr(
            window,
            "_response_staged_import_items",
            [
                StagedImportItem(source_path="D:/claims.docx", source_kind="word", selected_role="100001"),
                StagedImportItem(source_path="D:/description.docx", source_kind="word", selected_role="100002"),
            ],
        )

        window._remove_material_item_for_flow("response", 0)

        items = getattr(window, "_response_staged_import_items")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].source_path, "D:/description.docx")
        self.assertEqual(window.response_materials_table.rowCount(), 1)

    def test_validate_notice_for_flow_requires_issue_date_on_notice_flows(self) -> None:
        window = self._make_window()
        notice = NoticeMeta(
            application_no="2026101841613",
            invention_title="Example",
            applicant="Applicant",
            notice_name="审查意见通知书",
            notice_code="210401",
            issue_date="",
            doc_serial="2026031900436760",
            patent_type="invention",
        )

        with patch(
            "gui.main_window.mixins.response_correction_mixin.show_blocking_alert_modal",
            side_effect=lambda _parent, title, message, **_kwargs: window.alerts.append((title, message)),
        ):
            ok = window._validate_notice_for_flow("response", notice)

        self.assertFalse(ok)
        self.assertTrue(any("发文日" in message for _title, message in window.alerts))

    def test_validate_notice_for_flow_requires_doc_serial_on_notice_flows(self) -> None:
        window = self._make_window()
        notice = NoticeMeta(
            application_no="2026101841613",
            invention_title="Example",
            applicant="Applicant",
            notice_name="审查意见通知书",
            notice_code="210401",
            issue_date="20260319",
            doc_serial="",
            patent_type="invention",
        )

        with patch(
            "gui.main_window.mixins.response_correction_mixin.show_blocking_alert_modal",
            side_effect=lambda _parent, title, message, **_kwargs: window.alerts.append((title, message)),
        ):
            ok = window._validate_notice_for_flow("response", notice)

        self.assertFalse(ok)
        self.assertTrue(any("发文序号" in message for _title, message in window.alerts))

    def test_validate_notice_for_flow_allows_missing_doc_serial_on_active_response(self) -> None:
        window = self._make_window()
        notice = NoticeMeta(
            application_no="2026101841613",
            invention_title="Example",
            applicant="Applicant",
            notice_name="",
            notice_code="",
            issue_date="",
            doc_serial="",
            patent_type="invention",
        )

        with patch(
            "gui.main_window.mixins.response_correction_mixin.show_blocking_alert_modal",
            side_effect=lambda _parent, title, message, **_kwargs: window.alerts.append((title, message)),
        ):
            ok = window._validate_notice_for_flow("active_response", notice)

        self.assertTrue(ok)
        self.assertFalse(window.alerts)

    def test_on_response_confirm_imports_uses_background_worker(self) -> None:
        window = self._make_window()
        setattr(
            window,
            "_response_staged_import_items",
            [StagedImportItem(source_path="D:/claims.docx", source_kind="word", selected_role="100001")],
        )

        window.on_response_confirm_imports()

        self.assertEqual(window.worker_calls, [("response", "材料关联更新")])

    def test_handle_response_correction_success_allows_revealing_generated_package(self) -> None:
        window = self._make_window()
        result = PackageResult(
            outer_zip_path="D:/out/答复补正_20260410151515.zip",
            inner_zip_path="D:/out/10000021.zip",
            case_root="D:/out/response_correction_work_123/10000021",
        )
        revealed: list[str] = []

        with patch(
            "gui.main_window.mixins.response_correction_mixin.show_blocking_alert_modal",
            return_value="secondary",
        ), patch(
            "gui.main_window.mixins.response_correction_mixin.reveal_path_in_explorer",
            side_effect=lambda path: revealed.append(path) or True,
        ):
            window._handle_response_correction_success("response", "答复审查意见包", result)

        self.assertEqual(revealed, ["D:/out/答复补正_20260410151515.zip"])

    def test_collect_notice_for_flow_normalizes_dotted_application_no(self) -> None:
        window = self._make_window()
        window.response_application_no_edit.setText("202011435491.4")

        notice = window._collect_notice_for_flow("response")

        self.assertEqual(notice.application_no, "2020114354914")
        self.assertEqual(window.response_application_no_edit.text(), "2020114354914")

    def test_ingest_import_paths_failed_notice_parse_keeps_existing_notice_fields(self) -> None:
        window = self._make_window()
        window.response_notice_edit.setText("D:/existing-notice.zip")
        window.response_application_no_edit.setText("2024999999999")
        window.response_title_edit.setText("Old Title")
        window.response_applicant_edit.setText("Old Applicant")
        window.response_notice_name_edit.setText("审查意见通知书")
        window.response_issue_date_edit.setText("20240101")
        window.response_doc_serial_edit.setText("2024010100000000")
        setattr(
            window,
            "_response_notice_meta",
            NoticeMeta(
                application_no="2024999999999",
                invention_title="Old Title",
                applicant="Old Applicant",
                notice_name="审查意见通知书",
                notice_code="210401",
                issue_date="20240101",
                doc_serial="2024010100000000",
                patent_type="invention",
            ),
        )
        failed_notice = ParsedNotice(
            source_path="D:/new-notice.zip",
            meta=NoticeMeta(
                application_no="2026101841613",
                invention_title="New Title",
                applicant="New Applicant",
                notice_name="审查意见通知书",
                notice_code="210401",
                issue_date="20260319",
                doc_serial="2026031900436760",
                patent_type="invention",
            ),
            meta_source="list_xml",
            errors=("解析失败",),
        )

        with patch(
            "gui.main_window.mixins.response_correction_mixin.collect_response_correction_files",
            return_value=(["D:/new-notice.zip"], []),
        ), patch(
            "gui.main_window.mixins.response_correction_mixin.parse_notice_source",
            return_value=failed_notice,
        ), patch(
            "gui.main_window.mixins.response_correction_mixin.show_drop_ignored_message",
            return_value=None,
        ):
            window._ingest_import_paths_for_flow("response", ["D:/folder"])

        self.assertEqual(window.response_notice_edit.text(), "D:/existing-notice.zip")
        self.assertEqual(window.response_application_no_edit.text(), "2024999999999")
        self.assertIn("保留", window.response_status_label.text())


    def test_start_response_correction_worker_bridges_progress_to_overlay_and_status(self) -> None:
        window = _WorkerWindow()
        window.resize(640, 480)
        window.show()
        self._app.processEvents()
        success: dict[str, object] = {}

        def _task(*, progress_callback):
            progress_callback(12, "正在生成答复包", "共 2 个文件，正在处理第 1/2 个文件 | claims.docx | 第 1/5 段")
            time.sleep(0.15)
            progress_callback(56, "正在生成答复包", "共 2 个文件，正在处理第 1/2 个文件 | claims.docx | 第 3/5 段")
            time.sleep(0.15)
            return PackageResult(
                outer_zip_path="D:/out/result.zip",
                inner_zip_path="",
                case_root="",
                generated_files=("D:/out/result.zip",),
            )

        with patch("gui.main_window.mixins.response_correction_mixin.ensure_office_processes_ready", return_value=True), patch(
            "gui.main_window.mixins.response_correction_mixin.check_word_startup_health",
            return_value=_ok_word_health(),
        ):
            started = window._start_response_correction_worker(
                _task,
                flow="response",
                package_label="答复审查意见包",
                success_handler=lambda result: success.setdefault("result", result),
            )

            self.assertTrue(started)
            progressed = self._pump_until(lambda: window.progress_bar.value() >= 12 and window._processing_overlay is not None)
            self.assertTrue(progressed)
            self.assertIn("claims.docx", window.detail_label.text())
            self.assertIn("第 1/5 段", window.detail_label.text())
            overlay = window._processing_overlay
            self.assertIsNotNone(overlay)
            overlay_bar = overlay.findChild(QProgressBar, "processingBar")
            overlay_detail = overlay.findChild(QLabel, "processingFile")
            self.assertIsNotNone(overlay_bar)
            self.assertIsNotNone(overlay_detail)
            self.assertGreaterEqual(overlay_bar.value(), 12)
            self.assertIn("claims.docx", overlay_detail.text())

            finished = self._pump_until(
                lambda: "result" in success
                and window._processing_overlay is None
                and window._response_correction_worker is None
                and window._response_correction_worker_thread is None
            )
        self.assertTrue(finished)
        self.assertEqual(window.progress_bar.value(), 56)
        self.assertEqual(getattr(success["result"], "outer_zip_path", ""), "D:/out/result.zip")
        self.assertIsNone(window._response_correction_worker)
        self.assertIsNone(window._response_correction_worker_bridge)
        self.assertIsNone(window._response_correction_worker_thread)
        window.close()

    def test_start_response_correction_worker_retries_when_word_process_dialog_continues(self) -> None:
        window = _WorkerWindow()
        window.resize(640, 480)
        window.show()
        self._app.processEvents()
        success: dict[str, object] = {}
        attempts = {"count": 0}

        def _task(*, progress_callback):
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise WordComHijackedError("检测到系统中正在运行 Word/WPS 进程。")
            progress_callback(30, "正在生成答复包", "共 1 个文件，正在处理第 1/1 个文件 | claims.docx | 第 1/1 段")
            return PackageResult(
                outer_zip_path="D:/out/retried.zip",
                inner_zip_path="",
                case_root="",
                generated_files=("D:/out/retried.zip",),
            )

        with patch(
            "gui.main_window.mixins.response_correction_mixin.ask_continue_cancel",
            return_value=True,
        ) as mocked_confirm, patch(
            "gui.main_window.mixins.response_correction_mixin.ensure_office_processes_ready",
            return_value=True,
        ) as guard_mock, patch(
            "gui.main_window.mixins.response_correction_mixin.check_word_startup_health",
            return_value=_ok_word_health(),
        ):
            started = window._start_response_correction_worker(
                _task,
                flow="response",
                package_label="答复审查意见包",
                success_handler=lambda result: success.setdefault("result", result),
            )
            self.assertTrue(started)
            finished = self._pump_until(
                lambda: "result" in success
                and window._processing_overlay is None
                and window._response_correction_worker is None
                and window._response_correction_worker_thread is None
            )

        self.assertTrue(finished)
        self.assertEqual(attempts["count"], 2)
        self.assertEqual(mocked_confirm.call_count, 1)
        self.assertEqual(guard_mock.call_count, 2)
        self.assertEqual(getattr(success["result"], "outer_zip_path", ""), "D:/out/retried.zip")
        window.close()

    def test_start_response_correction_worker_runs_office_guard_before_worker(self) -> None:
        window = _WorkerWindow()
        started_task = {"value": False}

        def _task(*, progress_callback):
            started_task["value"] = True
            return PackageResult(outer_zip_path="D:/out/result.zip", inner_zip_path="", case_root="")

        with patch(
            "gui.main_window.mixins.response_correction_mixin.ensure_office_processes_ready",
            return_value=False,
        ) as guard_mock:
            started = window._start_response_correction_worker(
                _task,
                flow="response",
                package_label="答复审查意见包",
            )

        self.assertFalse(started)
        guard_mock.assert_called_once_with(window, context="response_correction_start")
        self.assertFalse(started_task["value"])
        self.assertFalse(getattr(window, "_response_correction_busy", False))
        self.assertIsNone(getattr(window, "_response_correction_worker", None))

    def test_start_response_correction_worker_runs_word_health_before_task(self) -> None:
        window = _WorkerWindow()
        started_task = {"value": False}
        success: dict[str, object] = {}

        def _task(*, progress_callback):
            started_task["value"] = True
            return PackageResult(outer_zip_path="D:/out/result.zip", inner_zip_path="", case_root="")

        with patch(
            "gui.main_window.mixins.response_correction_mixin.ensure_office_processes_ready",
            return_value=True,
        ) as guard_mock, patch(
            "gui.main_window.mixins.response_correction_mixin.check_word_startup_health",
            return_value=_ok_word_health(),
        ) as health_mock:
            started = window._start_response_correction_worker(
                _task,
                flow="response",
                package_label="答复审查意见包",
                success_handler=lambda result: success.setdefault("result", result),
            )
            self.assertTrue(started)
            finished = self._pump_until(
                lambda: "result" in success
                and window._response_correction_worker is None
                and window._response_correction_worker_thread is None
            )

        self.assertTrue(finished)
        self.assertTrue(started_task["value"])
        guard_mock.assert_called_once_with(window, context="response_correction_start")
        health_mock.assert_called_once()
        window.close()

    def test_start_response_correction_worker_resets_stale_kill_flag_before_word_health(self) -> None:
        window = _WorkerWindow()
        window._office_process_guard_killed = True
        success: dict[str, object] = {}

        def _task(*, progress_callback):
            return PackageResult(outer_zip_path="D:/out/result.zip", inner_zip_path="", case_root="")

        with patch(
            "gui.main_window.mixins.response_correction_mixin.ensure_office_processes_ready",
            return_value=True,
        ), patch(
            "gui.main_window.mixins.response_correction_mixin.check_word_startup_health",
            return_value=_ok_word_health(),
        ) as health_mock:
            started = window._start_response_correction_worker(
                _task,
                flow="response",
                package_label="答复审查意见包",
                success_handler=lambda result: success.setdefault("result", result),
            )
            self.assertTrue(started)
            finished = self._pump_until(
                lambda: "result" in success
                and window._response_correction_worker is None
                and window._response_correction_worker_thread is None
            )

        self.assertTrue(finished)
        self.assertFalse(getattr(window, "_office_process_guard_killed", True))
        health_mock.assert_called_once()
        self.assertFalse(health_mock.call_args.kwargs["killed_before_check"])
        window.close()

    def test_start_response_correction_worker_retries_health_after_unified_office_gate(self) -> None:
        window = _WorkerWindow()
        started_task = {"value": False}
        success: dict[str, object] = {}
        health_results = [_failed_word_health(), _ok_word_health()]

        def _task(*, progress_callback):
            started_task["value"] = True
            return PackageResult(outer_zip_path="D:/out/result.zip", inner_zip_path="", case_root="")

        with patch(
            "gui.main_window.mixins.response_correction_mixin.ensure_office_processes_ready",
            return_value=True,
        ) as guard_mock, patch(
            "gui.main_window.mixins.response_correction_mixin.check_word_startup_health",
            side_effect=health_results,
        ) as health_mock, patch(
            "gui.main_window.mixins.response_correction_mixin.show_blocking_alert_modal",
        ) as alert_mock:
            started = window._start_response_correction_worker(
                _task,
                flow="response",
                package_label="答复审查意见包",
                success_handler=lambda result: success.setdefault("result", result),
            )
            self.assertTrue(started)
            finished = self._pump_until(
                lambda: "result" in success
                and window._response_correction_worker is None
                and window._response_correction_worker_thread is None
            )

        self.assertTrue(finished)
        self.assertTrue(started_task["value"])
        self.assertEqual(2, guard_mock.call_count)
        self.assertEqual("response_correction_start", guard_mock.call_args_list[0].kwargs["context"])
        self.assertEqual("word_health_failure", guard_mock.call_args_list[1].kwargs["context"])
        self.assertEqual(2, health_mock.call_count)
        alert_mock.assert_not_called()
        window.close()


if __name__ == "__main__":
    unittest.main()
