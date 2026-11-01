import os

from PySide6.QtWidgets import QFileDialog

from gui.dialog_utils import show_blocking_alert_modal


class SingleFileMixin:
    def on_browse_single(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 DOC/DOCX 文件",
            os.getcwd(),
            "Word 文档 (*.doc *.docx)",
        )
        if file_path:
            self.path_edit.setText(file_path)

    def _refresh_single_file_card(self) -> None:
        card = getattr(self, "single_file_card", None)
        if not card:
            return
        try:
            file_path = self.path_edit.text().strip() if hasattr(self, "path_edit") else ""
        except Exception:
            file_path = ""

        if not file_path:
            try:
                card.setVisible(False)
            except Exception:
                pass
            return

        name = ""
        try:
            name = os.path.basename(file_path)
        except Exception:
            name = file_path

        try:
            if hasattr(self, "single_file_name_label") and self.single_file_name_label:
                self.single_file_name_label.setText(name)
        except Exception:
            pass
        try:
            if hasattr(self, "single_file_path_label") and self.single_file_path_label:
                self.single_file_path_label.setText(file_path)
                self.single_file_path_label.setToolTip(file_path)
        except Exception:
            pass

        try:
            card.setVisible(True)
        except Exception:
            pass

    def on_clear_single(self) -> None:
        try:
            if hasattr(self, "path_edit") and self.path_edit:
                self.path_edit.setText("")
                self.path_edit.setFocus()
        except Exception:
            pass
        try:
            if hasattr(self, "status_label") and self.status_label:
                self.status_label.setText("🔵 状态：空闲")
        except Exception:
            pass

    def on_single_files_dropped(self, paths):
        if not paths:
            return
        if getattr(self, "_processing_mode", "single") != "single":
            show_blocking_alert_modal(self, "提示", "请切换到单文档模式后再拖拽文件。", primary_text="关闭", secondary_text="关闭")
            return
        valid_files, ignored = self._collect_docx_from_items(paths, include_directories=False)
        file_path = valid_files[0] if valid_files else None
        if not file_path:
            if ignored:
                self._show_drop_ignored_message("拖拽未添加", ignored)
            return
        self.path_edit.setText(file_path)
        self._set_status_hint(f"🟢 已拖入文件：{os.path.basename(file_path)}")
        if ignored:
            self._show_drop_ignored_message("部分条目未添加", ignored)
