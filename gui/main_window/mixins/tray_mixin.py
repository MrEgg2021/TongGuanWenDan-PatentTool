import os

from PySide6.QtCore import QThread
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from core.paths_utils import get_resource_path


class TrayMixin:
    def _has_active_task(self) -> bool:
        if any(bool(getattr(self, name, False)) for name in (
            "_is_processing_conversion", "_single_run_in_progress",
            "_response_correction_busy", "_formal_review_busy", "_preview_in_progress",
        )):
            return True
        if getattr(self, "_processing_overlay", None) is not None:
            return True
        if getattr(self, "_progress_scope", None) in (
            "single", "batch", "preview", "official_docs", "response_correction", "word_health",
        ):
            return True
        warmup = getattr(self, "_preview_warmup_thread", None)
        return any(
            child is not warmup and child.isRunning()
            for child in self.children() if isinstance(child, QThread)
        )

    def _warn_active_task_before_exit(self) -> bool:
        if not self._has_active_task():
            return False
        QMessageBox.information(self, "任务正在运行", "当前任务尚未完成，请等待任务结束后再退出。")
        return True

    def _confirm_leave_settings_before_tray_action(self) -> bool:
        try:
            fn = getattr(self, "_confirm_leave_official_docs_if_dirty", None)
            if callable(fn):
                ok = bool(fn())
                if not ok:
                    return False
        except Exception:
            return True
        try:
            fn = getattr(self, "_confirm_leave_settings_if_dirty", None)
            if callable(fn):
                return bool(fn())
        except Exception:
            return True
        return True

    def _init_tray(self):
        """初始化系统托盘图标与菜单"""
        try:
            icon_path = get_resource_path(os.path.join("assets", "app_icon.ico"))
            icon = QIcon(icon_path) if icon_path and os.path.exists(icon_path) else self.windowIcon()
        except Exception:
            icon = self.windowIcon()

        self.tray_icon = QSystemTrayIcon(icon, self)
        menu = QMenu()

        action_show = QAction("显示主界面", self)
        action_show.triggered.connect(self._restore_window)
        menu.addAction(action_show)

        menu.addSeparator()

        action_single = QAction("单文件处理", self)
        action_single.triggered.connect(lambda: self._tray_switch_mode("single"))
        menu.addAction(action_single)

        action_batch = QAction("批量处理", self)
        action_batch.triggered.connect(lambda: self._tray_switch_mode("batch"))
        menu.addAction(action_batch)

        action_preview = QAction("PDF预览", self)
        action_preview.triggered.connect(lambda: self._tray_switch_mode("preview"))
        menu.addAction(action_preview)

        menu.addSeparator()

        action_exit = QAction("退出", self)
        action_exit.triggered.connect(self._tray_quit)
        menu.addAction(action_exit)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _on_tray_activated(self, reason):
        # 左键/双击恢复窗口
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self._restore_window()

    def _restore_window(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _tray_switch_mode(self, mode: str):
        self._restore_window()
        try:
            if not self._confirm_leave_settings_before_tray_action():
                return
        except Exception:
            pass
        if mode == "single":
            try:
                self._show_workflow_page()
            except Exception:
                pass
            try:
                self._processing_mode = "single"
            except Exception:
                pass
            self.on_mode_changed("single")
        elif mode == "batch":
            try:
                self._show_workflow_page()
            except Exception:
                pass
            try:
                self._processing_mode = "batch"
            except Exception:
                pass
            self.on_mode_changed("batch")
        elif mode == "preview":
            try:
                self._set_nav_checked("preview")
                self._show_preview_page()
            except Exception:
                pass

    def _tray_quit(self):
        try:
            self._restore_window()
        except Exception:
            pass
        if self._warn_active_task_before_exit():
            return
        try:
            if not self._confirm_leave_settings_before_tray_action():
                return
        except Exception:
            pass
        self._allow_close = True
        try:
            if self.tray_icon:
                self.tray_icon.hide()
                self.tray_icon.deleteLater()
        except Exception:
            pass
        # 确保事件循环退出
        QApplication.instance().quit()

    def closeEvent(self, event):
        """点击窗口关闭按钮时最小化到托盘，除非明确允许退出。"""
        try:
            if not getattr(self, "_allow_close", False):
                if not self._confirm_leave_settings_before_tray_action():
                    event.ignore()
                    return
        except Exception:
            pass
        if getattr(self, "_allow_close", False):
            if self._warn_active_task_before_exit():
                self._allow_close = False
                event.ignore()
                return
            try:
                if self.tray_icon:
                    self.tray_icon.hide()
                    self.tray_icon.deleteLater()
            except Exception:
                pass
            return super().closeEvent(event)
        event.ignore()
        self.hide()
        if self.tray_icon:
            try:
                self.tray_icon.show()
                self.tray_icon.showMessage("提示", "程序已最小化到托盘，右键图标可退出。", QSystemTrayIcon.Information, 3000)
            except Exception:
                pass
