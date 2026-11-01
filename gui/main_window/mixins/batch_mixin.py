
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu

from gui.batch_ui import (
    append_batch_files,
    batch_item_changed,
    batch_item_clicked,
    browse_files,
    browse_folder,
    clear_list,
    get_batch_checked_files,
)
from gui.dialog_utils import show_blocking_alert_modal


class BatchMixin:
    def _show_batch_pick_menu(self) -> None:
        menu = QMenu(self)
        act_files = QAction("选择多个文件", menu)
        act_folder = QAction("选择文件夹", menu)
        act_files.triggered.connect(self.on_browse_files)
        act_folder.triggered.connect(self.on_browse_folder)
        menu.addAction(act_files)
        menu.addAction(act_folder)

        anchor = None
        try:
            anchor = getattr(self, "batch_drop_zone", None)
        except Exception:
            anchor = None
        if anchor is not None:
            try:
                pos = anchor.mapToGlobal(anchor.rect().center())
                menu.exec(pos)
                return
            except Exception:
                pass
        try:
            menu.exec(self.mapToGlobal(self.rect().center()))
        except Exception:
            pass

    def _apply_batch_filter(self) -> None:
        lst = getattr(self, "file_list_widget", None)
        if lst is None:
            return
        text = ""
        try:
            text = str(getattr(self, "_batch_filter_text", "") or "").strip().lower()
        except Exception:
            text = ""

        try:
            total = int(lst.count())
        except Exception:
            total = 0

        for i in range(total):
            item = None
            try:
                item = lst.item(i)
            except Exception:
                item = None
            if item is None:
                continue

            if not text:
                try:
                    item.setHidden(False)
                except Exception:
                    pass
                continue

            fp = ""
            base = ""
            try:
                fp = item.data(Qt.UserRole) or ""
            except Exception:
                fp = ""
            try:
                base = item.data(Qt.UserRole + 1) or ""
            except Exception:
                base = ""
            cand = f"{base} {fp}".lower()
            show = (text in cand)
            try:
                item.setHidden(not show)
            except Exception:
                pass

    def on_batch_filter_changed(self, text: str) -> None:
        try:
            self._batch_filter_text = str(text or "")
        except Exception:
            self._batch_filter_text = ""
        try:
            self._apply_batch_filter()
        except Exception:
            pass

    def on_browse_files(self):
        """选择多个文件（薄壳，委托到 gui.batch_ui.browse_files）。"""
        browse_files(self)

    def on_browse_folder(self):
        """选择文件夹（薄壳，委托到 gui.batch_ui.browse_folder）。"""
        browse_folder(self)

    def on_batch_files_dropped(self, paths):
        if not paths:
            return
        if getattr(self, "_processing_mode", "single") != "batch":
            show_blocking_alert_modal(self, "提示", "请切换到批量模式后再拖拽文件。", primary_text="关闭", secondary_text="关闭")
            return
        docx_files, ignored = self._collect_docx_from_items(paths, include_directories=True)
        if not docx_files and ignored:
            self._show_drop_ignored_message("拖拽未添加", ignored)
            return
        added = append_batch_files(self, docx_files)
        summary = []
        if added:
            summary.append(f"🟢 已添加 {added} 个文件")
        skipped_count = len(docx_files) - added
        if skipped_count:
            summary.append(f"⚠ 有 {skipped_count} 个文件已存在或无效")
        if summary:
            self._set_status_hint("；".join(summary))
        if ignored:
            self._show_drop_ignored_message("部分条目未添加", ignored)

    def on_clear_list(self):
        """清空文件列表（薄壳，委托到 gui.batch_ui.clear_list）。"""
        clear_list(self)

    def on_batch_item_clicked(self, item):
        """点击批量列表某一行（薄壳，委托到 gui.batch_ui.batch_item_clicked）。"""
        batch_item_clicked(self, item)

    def on_batch_item_changed(self, item):
        """批量列表条目勾选状态变化（薄壳，委托到 gui.batch_ui.batch_item_changed）。"""
        batch_item_changed(self, item)


    def _get_batch_checked_files(self):
        """返回当前勾选的批量处理文件路径列表（薄壳，委托到 gui.batch_ui.get_batch_checked_files）。"""
        return get_batch_checked_files(self)
