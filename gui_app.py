import os
import sys

from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QFileDialog,
    QMessageBox,
)
from PySide6.QtCore import QTimer, QLockFile
from PySide6.QtGui import QIcon

from core.logging_utils import logger
from core.config import get_app_display_title
from core.cnipa_preview.runtime import shutdown_default_runtime_manager
from core.paths_utils import get_resource_path
from core.qt_i18n import install_qt_zh_translator
from core.tgd_data_management_impl.infra import get_app_lock_path
from core.app_preferences import get_desc_para_split_mode
from gui.batch_run import run_batch_conversion as run_batch_conversion_impl
from gui.ui_layout import setup_mainwindow_ui
from gui.main_window.mixins.preview_mixin import PreviewMixin
from gui.main_window.mixins.preview_export_mixin import PreviewExportMixin
from gui.main_window.mixins.tray_mixin import TrayMixin
from gui.main_window.mixins.navigation_mixin import NavigationMixin
from gui.main_window.mixins.tgd_data_management_mixin import TgdDataManagementMixin
from gui.main_window.mixins.official_docs_mixin import OfficialDocsMixin
from gui.main_window.mixins.response_correction_mixin import ResponseCorrectionMixin
from gui.main_window.mixins.formal_review_mixin import FormalReviewMixin
from gui.main_window.mixins.settings_mixin import SettingsMixin
from gui.main_window.mixins.batch_mixin import BatchMixin
from gui.main_window.mixins.single_file_mixin import SingleFileMixin
from gui.main_window.mixins.progress_mixin import ProgressMixin
from gui.header_check import check_required_headers_single, check_required_headers_batch
from gui.app_impl.image_overrides import init_advanced_image_overrides
from gui.request_form_ui import build_request_form_initial_info
from gui.run_dispatch import handle_run_clicked
from gui.tools_ui import open_output_dir, export_word_template
from gui.app_impl import (
    clear_system_clipboard_safely,
    on_mode_changed,
    get_enabled_sections_safe,
    show_request_form_skip_tip,
    on_request_form_toggled_safe,
    collect_docx_from_items,
    show_drop_ignored_message,
    generate_case_number,
    bind_layout_splitter_prefs,
    bind_workflow_home_splitter_prefs,
    bind_workflow_footer_splitter_prefs,
)
from gui.windowing.high_dpi import configure_high_dpi_before_app
from gui.windowing import overlay_controller as overlay_controller_api
from gui.windowing import window_state_controller as window_state_controller_api

__all__ = ["MainWindow", "main"]


class MainWindow(
    TrayMixin,
    NavigationMixin,
    TgdDataManagementMixin,
    OfficialDocsMixin,
    ResponseCorrectionMixin,
    FormalReviewMixin,
    SettingsMixin,
    BatchMixin,
    SingleFileMixin,
    PreviewMixin,
    PreviewExportMixin,
    ProgressMixin,
    QWidget,
):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(get_app_display_title())
        icon_path = get_resource_path(os.path.join("assets", "app_icon.ico"))
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self._last_single_zip_for_preview = None
        self._allow_close = False  # 控制是否真正退出
        self.tray_icon = None
        self._processing_overlay = None
        self._result_overlay = None
        self._last_single_saved_zip_path = None
        self._last_batch_saved_path = None
        self._preview_cases = []
        self._preview_temp_root = None
        self._preview_temp_files = []
        self._preview_selected_zip_path = None
        self._preview_case_filter_text = ""
        self._preview_bundle_expanded = {}
        self._preview_case_item_widgets = {}
        self._preview_pdf_map = {}
        self._preview_pdf_errors = {}
        self._preview_manifest_errors = {}
        self._preview_documents = ()
        self._preview_merged_temp_pdf_path = ""
        self._preview_last_zip_path = None
        self._preview_export_selections = {}
        self._preview_document_orders = {}
        self._preview_reorder_refresh_pending = False
        self._preview_render_worker = None
        self._preview_render_bridge = None
        self._preview_render_thread = None
        self._preview_manifest_worker = None
        self._preview_manifest_bridge = None
        self._preview_manifest_thread = None
        self._window_screen_bind_attempts = 0
        self._window_screen_handle_bound = False
        self._window_bound_screen = None
        self._has_run_conversion = False
        self._selected_files = []
        self._batch_file_types = {}
        self._suppress_batch_item_changed = False
        self._processing_mode = "single"
        init_advanced_image_overrides(self)
        self._setup_ui()
        self._init_windowing_runtime()
        self._init_tray()
        from gui.tools_ui_impl.preview_impl.service_status import start_preview_services

        QTimer.singleShot(0, lambda: start_preview_services(self))
        QTimer.singleShot(0, self._auto_env_check_and_alert_if_needed)

    def _setup_ui(self):
        setup_mainwindow_ui(self)
        bind_layout_splitter_prefs(self)
        bind_workflow_home_splitter_prefs(self)
        bind_workflow_footer_splitter_prefs(self)
        self._apply_persisted_preferences()
        self._modern_shell.nav_group.setExclusive(True)

    def _init_windowing_runtime(self) -> None:
        window_state_controller_api.bind(self)
        window_state_controller_api.restore(self)
        QTimer.singleShot(0, self._bind_window_screen_signals)
        overlay_controller_api.reconcile_sidebar_toggle(self)

    def _disconnect_window_screen_metrics(self) -> None:
        screen = self._window_bound_screen
        if screen is None:
            return
        try:
            for signal in (
                screen.geometryChanged,
                screen.availableGeometryChanged,
                screen.logicalDotsPerInchChanged,
                screen.physicalDotsPerInchChanged,
            ):
                signal.disconnect(self._on_window_screen_metrics_changed)
        except RuntimeError:
            # Qt may already have destroyed a disconnected monitor's QScreen.
            pass
        self._window_bound_screen = None

    def _bind_window_screen_signals(self) -> None:
        handle = self.windowHandle()
        if handle is None:
            self._window_screen_bind_attempts += 1
            if self._window_screen_bind_attempts <= 20:
                QTimer.singleShot(100, self._bind_window_screen_signals)
            return
        if not self._window_screen_handle_bound:
            handle.screenChanged.connect(self._on_window_screen_changed)
            self._window_screen_handle_bound = True
        self._on_window_screen_changed(handle.screen())

    def _on_window_screen_changed(self, screen) -> None:
        self._disconnect_window_screen_metrics()
        if screen is None:
            overlay_controller_api.relayout("all", reason="screen_missing")
            return
        for signal in (
            screen.geometryChanged,
            screen.availableGeometryChanged,
            screen.logicalDotsPerInchChanged,
            screen.physicalDotsPerInchChanged,
        ):
            signal.connect(self._on_window_screen_metrics_changed)
        self._window_bound_screen = screen
        overlay_controller_api.relayout("all", reason="screen_changed")

    def _on_window_screen_metrics_changed(self, *_args) -> None:
        overlay_controller_api.relayout("all", reason="screen_metrics_changed")
        window_state_controller_api.save_now(self)

    def _clear_system_clipboard_safely(self):
        clear_system_clipboard_safely()

    def generate_case_number(self):
        """生成默认案件号（日期+序号）"""
        return generate_case_number()
    
    def _check_required_headers_single(self, input_path: str, config_path=None) -> bool:
        return check_required_headers_single(self, input_path, config_path=config_path)

    def _check_required_headers_batch(self, file_path: str, config_path=None) -> bool:
        return check_required_headers_batch(self, file_path, config_path=config_path)
    
    def get_enabled_sections(self) -> dict:
        """返回当前 GUI 五书勾选状态，用于控制后续输出生成哪些文书。"""
        return get_enabled_sections_safe(self)

    def get_description_paragraph_split_mode(self) -> str:
        return get_desc_para_split_mode() or "word_period_end"
    
    def _show_request_form_skip_tip(self, mode: str = "single") -> None:
        """提示未勾选请求书时的导入方式差异。"""
        show_request_form_skip_tip(self, mode)
    
    def on_request_form_toggled(self, checked: bool) -> None:
        """勾选/取消“请求书”时的即时提示。"""
        on_request_form_toggled_safe(self, checked)
    
    def on_mode_changed(self, mode: str | None = None):
        """切换处理模式"""
        on_mode_changed(self, mode)

    def _build_request_form_initial_info(self, parsed_info, current_patent_type):
        return build_request_form_initial_info(parsed_info, current_patent_type)

    def on_run(self):
        """处理转换按钮点击，支持单文档和批量模式"""
        handle_run_clicked(self)

    def run_batch_conversion(self):
        """执行批量转换"""
        run_batch_conversion_impl(self)

    def on_open_output(self):
        """打开配置中定义的输出目录（薄壳，委托到 gui.tools_ui.open_output_dir）。"""
        open_output_dir(self)

    def on_export_template(self):
        """导出发明专利 Word 模板（薄壳，委托到 gui.tools_ui.export_word_template）。"""
        export_word_template(self)

    def on_browse_output_dir(self):
        """选择案卷压缩包输出目录。"""
        base_dir = self.output_dir_edit.text().strip() or os.getcwd()

        dir_path = QFileDialog.getExistingDirectory(
            self,
            "选择案卷压缩包输出目录",
            base_dir,
        )
        if dir_path:
            self.output_dir_edit.setText(dir_path)

    def _collect_docx_from_items(self, paths, include_directories=True):
        return collect_docx_from_items(paths, include_directories=include_directories)

    def _show_drop_ignored_message(self, title, ignored_items):
        show_drop_ignored_message(self, title, ignored_items)

    def _set_status_hint(self, text: str) -> None:
        try:
            if hasattr(self, "status_label") and isinstance(text, str):
                self.status_label.setText(text)
        except Exception:
            pass


def main():
    configure_high_dpi_before_app()
    app = QApplication(sys.argv)
    install_qt_zh_translator(app, logger=logger)
    app.setApplicationName("通官文旦-专利工具")
    app.setApplicationDisplayName(get_app_display_title())
    app.aboutToQuit.connect(shutdown_default_runtime_manager)
    lock = QLockFile(get_app_lock_path())
    if not lock.tryLock(0):
        QMessageBox.information(None, "提示", "程序已在运行中，请勿重复打开")
        return 1
    win = MainWindow()
    win.show()
    exit_code = int(app.exec())
    logger.info("[APP_EXIT] app_exec_return_code=%s", exit_code)
    sys.exit(exit_code)


if __name__ == "__main__":
    sys.exit(main())
