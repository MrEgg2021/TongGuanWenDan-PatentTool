import os

from PySide6.QtCore import QSignalBlocker
from PySide6.QtWidgets import QFileDialog

from core.cnipa_preview.runtime import get_default_runtime_manager
from core.app_preferences import get_pdf_preview_mode, set_pdf_preview_mode
from gui.dialog_utils import show_blocking_alert_modal
from gui.tools_ui import inspect_preview_case
from gui.tools_ui_impl.preview_impl.run import prewarm_full_preview
from gui.tools_ui_impl.preview_impl.runtime_setup import configure_installed_client
from gui.main_window.mixins.preview_case_list_ui import (
    refresh_preview_case_list_ui as _refresh_preview_case_list_ui,
    set_preview_selected_zip_path as _set_preview_selected_zip_path,
    toggle_preview_bundle_expanded as _toggle_preview_bundle_expanded,
    update_preview_case_item_selected_style as _update_preview_case_item_selected_style,
)
from gui.main_window.mixins.preview_cases import (
    add_preview_zip_cases as _add_preview_zip_cases,
    build_preview_case_nodes_from_zip as _build_preview_case_nodes_from_zip,
    get_preview_leaf_by_zip_path as _get_preview_leaf_by_zip_path,
    get_selected_preview_leaf as _get_selected_preview_leaf,
    iter_preview_leaf_cases as _iter_preview_leaf_cases,
    normalize_preview_zip_candidates as _normalize_preview_zip_candidates,
)
from gui.main_window.mixins.preview_temp import cleanup_preview_temp as _cleanup_preview_temp
from gui.main_window.mixins.preview_temp import ensure_preview_temp_root as _ensure_preview_temp_root


class PreviewMixin:
    def _apply_preview_mode_ui(self) -> None:
        try:
            from gui.main_window.mixins.preview_export_impl.ops_impl import apply_preview_mode_ui

            apply_preview_mode_ui(self)
        except Exception:
            pass

    def on_preview_mode_changed(self, mode: str) -> None:
        selected_mode = "full" if mode == "full" else "legacy"
        if selected_mode == "full":
            manager = get_default_runtime_manager()
            if (not manager.configured_path() or manager.configuration_error()) and getattr(self, "_preview_warmup_thread", None) is None:
                if not configure_installed_client(self, automatic=True):
                    button = getattr(self, "preview_legacy_mode_button", None)
                    if button is not None:
                        blocker = QSignalBlocker(button)
                        button.setChecked(True)
                        blocker.unblock()
                    set_pdf_preview_mode("legacy")
                    self._apply_preview_mode_ui()
                    return
        set_pdf_preview_mode(selected_mode)
        self._apply_preview_mode_ui()
        if selected_mode == "full":
            self._ensure_full_preview_prewarm()

    def _ensure_full_preview_prewarm(self) -> None:
        if get_pdf_preview_mode() != "full":
            return
        prewarm_full_preview(self)

    def _ensure_preview_temp_root(self) -> str:
        """确保预览导入用的临时目录存在，并返回目录路径。"""
        return _ensure_preview_temp_root(self)

    def _cleanup_preview_temp(self) -> None:
        """清理预览导入时产生的临时文件与临时目录。"""
        return _cleanup_preview_temp(self)

    def _iter_preview_leaf_cases(self):
        """遍历所有可预览的叶子案件（bundle 的子 ZIP + 单案件 ZIP）。"""
        yield from _iter_preview_leaf_cases(self)

    def _get_preview_leaf_by_zip_path(self, zip_path: str | None) -> tuple[dict | None, dict | None]:
        """根据 zip_path 查找对应的 (parent_bundle, leaf_case) 结构。"""
        return _get_preview_leaf_by_zip_path(self, zip_path)

    def _get_selected_preview_leaf(self) -> tuple[dict | None, dict | None]:
        """返回当前选中的案件叶子节点。"""
        return _get_selected_preview_leaf(self)

    def _get_default_preview_zip_path_for_dialog(self) -> str:
        """生成 ZIP 选择对话框的默认路径。"""
        last_saved = ""
        try:
            last_saved = getattr(self, "_last_single_saved_zip_path", "") or ""
        except Exception:
            last_saved = ""
        last_preview = ""
        try:
            last_preview = getattr(self, "_last_single_zip_for_preview", "") or ""
        except Exception:
            last_preview = ""

        for candidate in (last_saved, last_preview):
            if isinstance(candidate, str) and candidate and os.path.isfile(candidate):
                return candidate

        output_dir = ""
        try:
            output_dir = self.output_dir_edit.text().strip()
        except Exception:
            output_dir = ""
        if output_dir and os.path.isdir(output_dir):
            return output_dir

        try:
            home = os.path.expanduser("~")
            desktop = os.path.join(home, "Desktop")
            if os.path.isdir(desktop):
                return desktop
        except Exception:
            pass

        return os.getcwd()

    def _normalize_preview_zip_candidates(self, paths) -> list[str]:
        """将输入的路径集合规范为可导入的 zip 文件路径列表。"""
        return _normalize_preview_zip_candidates(paths)

    def _build_preview_case_nodes_from_zip(self, zip_path: str) -> dict | None:
        """将一个 ZIP 解析成预览案件节点（bundle 或单案件）。"""
        return _build_preview_case_nodes_from_zip(self, zip_path)

    def _add_preview_zip_cases(self, zip_paths: list[str]) -> int:
        """导入 ZIP 列表并追加到预览案件列表中，返回成功追加的数量。"""
        return _add_preview_zip_cases(self, zip_paths)

    def on_preview_import_zips(self) -> None:
        """预览页：点击导入 ZIP。"""
        default_path = self._get_default_preview_zip_path_for_dialog()
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "导入案卷 ZIP",
            default_path,
            "ZIP 文件 (*.zip)",
        )
        zip_paths = self._normalize_preview_zip_candidates(paths)
        if not zip_paths:
            return

        added = 0
        try:
            added = self._add_preview_zip_cases(zip_paths)
        except Exception:
            added = 0

        try:
            self._refresh_preview_case_list_ui(selected_path=getattr(self, "_preview_selected_zip_path", None))
        except Exception:
            pass

        if added <= 0:
            show_blocking_alert_modal(self, "提示", "未导入任何新案卷（可能已存在或文件无效）。", primary_text="关闭", secondary_text="关闭")

    def on_preview_zips_dropped(self, paths) -> None:
        """预览页：拖拽导入 ZIP。"""
        zip_paths = self._normalize_preview_zip_candidates(paths)
        if not zip_paths:
            show_blocking_alert_modal(self, "提示", "未识别到可导入的 ZIP 文件。", primary_text="关闭", secondary_text="关闭")
            return

        added = 0
        try:
            added = self._add_preview_zip_cases(zip_paths)
        except Exception:
            added = 0

        try:
            self._refresh_preview_case_list_ui(selected_path=getattr(self, "_preview_selected_zip_path", None))
        except Exception:
            pass

        if added <= 0:
            show_blocking_alert_modal(self, "提示", "未导入任何新案卷（可能已存在或文件无效）。", primary_text="关闭", secondary_text="关闭")

    def on_preview_clear_cases(self) -> None:
        """预览页：清空案件列表，并重置右侧导出区状态。"""
        try:
            self._preview_cases = []
            self._preview_selected_zip_path = None
            self._preview_case_filter_text = ""
            self._preview_bundle_expanded = {}
            self._preview_case_item_widgets = {}
        except Exception:
            pass

        try:
            self._cleanup_preview_temp()
        except Exception:
            pass

        try:
            cb = getattr(self, "_reset_preview_export_ui", None)
            if callable(cb):
                cb()
        except Exception:
            pass

        try:
            if hasattr(self, "preview_current_case_label"):
                self.preview_current_case_label.setText("未选择案件")
        except Exception:
            pass

        try:
            self._refresh_preview_case_list_ui(selected_path=None)
        except Exception:
            pass

    def on_preview_case_search_changed(self, text: str) -> None:
        try:
            self._preview_case_filter_text = str(text or "")
        except Exception:
            self._preview_case_filter_text = ""
        try:
            self._refresh_preview_case_list_ui(selected_path=getattr(self, "_preview_selected_zip_path", None))
        except Exception:
            pass

    def _toggle_preview_bundle_expanded(self, key: str) -> None:
        return _toggle_preview_bundle_expanded(self, key)

    def _update_preview_case_item_selected_style(self, zip_path: str | None, selected: bool) -> None:
        return _update_preview_case_item_selected_style(self, zip_path, selected)

    def _set_preview_selected_zip_path(self, zip_path: str | None) -> None:
        return _set_preview_selected_zip_path(self, zip_path)

    def _refresh_preview_case_list_ui(self, selected_path: str | None = None) -> None:
        return _refresh_preview_case_list_ui(self, selected_path)

    def on_preview_case_selection_changed(self) -> None:
        cur_zip = ""
        try:
            parent, leaf = self._get_selected_preview_leaf()
            name = "未选择案件"
            if leaf:
                if parent and isinstance(parent, dict) and parent.get("name"):
                    name = f"{parent.get('name')} / {leaf.get('name') or ''}".strip(" /")
                else:
                    name = str(leaf.get("name") or name)
            if hasattr(self, "preview_current_case_label"):
                self.preview_current_case_label.setText(name)
        except Exception:
            pass

        try:
            try:
                _p, lf = self._get_selected_preview_leaf()
                cur_zip = str((lf or {}).get("zip_path") or "")
            except Exception:
                cur_zip = ""
            if cur_zip and str(getattr(self, "_preview_last_zip_path", "") or "") != str(cur_zip):
                cb = getattr(self, "_reset_preview_export_ui", None)
                if callable(cb):
                    cb()
        except Exception:
            pass

        if (
            cur_zip
            and os.path.isfile(cur_zip)
            and str(getattr(self, "_preview_last_zip_path", "") or "") != cur_zip
            and not bool(getattr(self, "_preview_in_progress", False))
            and get_pdf_preview_mode() == "full"
        ):
            try:
                inspect_preview_case(self, cur_zip)
            except Exception:
                pass
        elif cur_zip and os.path.isfile(cur_zip) and get_pdf_preview_mode() == "legacy":
            try:
                from gui.main_window.mixins.preview_export_impl.ops_impl import prepare_legacy_preview_case

                prepare_legacy_preview_case(self, cur_zip)
            except Exception:
                pass
