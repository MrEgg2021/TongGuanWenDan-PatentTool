from __future__ import annotations
import os
from types import SimpleNamespace
import unittest
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QPushButton, QTextBrowser, QWidget
from core.user_messages import user_error_text
from gui.dialog_utils import show_blocking_alert_modal
from gui.main_window.mixins.formal_review_ops.marker_ops import _build_marker_plan_summary_text
from gui.update_log_dialog import UpdateLogDialog

class UserFacingCopyTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_system_errors_are_actionable_and_original_is_preserved(self):
        cases = [("保存失败：[Errno 13] Permission denied: 'C:/demo/output.pdf'", '权限'), ('[WinError 32] The file is being used by another process', '占用'), ('FileNotFoundError: missing file', '找不到'), ('[Errno 28] No space left on device', '空间不足'), ("HTTPConnectionPool(host='127.0.0.1'): Max retries exceeded", '无法连接'), ('ReadTimeout: timed out', '超时'), ('官方渲染进程已退出：java.lang.OutOfMemoryError: Java heap space', '内存不足'), ('ModuleNotFoundError: No module named example', '组件无法加载')]
        for original, expected in cases:
            with self.subTest(original=original):
                result = user_error_text(original)
                self.assertIn(expected, result)
                self.assertNotIn(original, result)

    def test_business_failure_saved_outputs_and_filenames_are_preserved(self):
        for original in ('汇总 PDF 已保存；归档失败：目录只读。\nD:/案卷/summary.pdf', '无法保存 Error.docx，请确认原文件仍存在。', 'summary.pdf', 'C:/demo/Error.docx', 'http://127.0.0.1:8080/preview/example.pdf', '2026-10-14 12:30:00', '127.0.0.1:8080', '发现两个同名文件，请选择要保留的文件。', '已跳过：申请号为空。\n已跳过：申请号为空。'):
            with self.subTest(original=original):
                self.assertEqual(user_error_text(original), original)

    def test_plan_summary_uses_business_counts_and_preserves_full_plan(self):
        plan = SimpleNamespace(command_count=4, inserted_count=2, replaced_count=2, warnings=[])
        summary = _build_marker_plan_summary_text(None, plan, parser_warnings=[])
        self.assertIn('预计修改项：4', summary)
        self.assertIn('预计新增：2', summary)
        self.assertNotRegex(summary, 'strict|loose|projection|word_find|命令')

    def test_actual_changelog_widgets_do_not_show_internal_release_copy(self):
        dialog = UpdateLogDialog()
        self.app.processEvents()
        try:
            texts = [browser.toPlainText() for browser in dialog.findChildren(QTextBrowser)]
            self.assertTrue(texts)
            for text in texts:
                self.assertNotRegex(text, '提供源码|EXE 下载|发卡台账|WAL 数据|JVM|图片队列')
        finally:
            dialog.close()

    def test_real_modal_shows_translated_error_and_keeps_button_result(self):
        owner = QWidget()
        owner.resize(800, 600)
        owner.show()
        observed = []

        def click_close():
            body = owner.findChild(QTextBrowser, 'alertBody')
            observed.append(body.toPlainText() if body is not None else '')
            button = owner.findChild(QPushButton, 'alertPrimary')
            if button is not None:
                button.click()
        QTimer.singleShot(0, click_close)
        try:
            result = show_blocking_alert_modal(owner, '保存失败', '[Errno 13] Permission denied', primary_text='关闭', secondary_text='关闭')
            self.assertEqual(result, 'primary')
            self.assertIn('权限', observed[0])
            self.assertNotIn('Permission denied', observed[0])
        finally:
            owner.close()
if __name__ == '__main__':
    unittest.main()
