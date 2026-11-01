from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QHeaderView, QWidget

    from gui.ui_layout_impl.response_correction_page import build_response_page

    _PYSIDE6_AVAILABLE = True
except Exception:
    QApplication = None  # type: ignore[assignment]
    QWidget = object  # type: ignore[assignment]
    build_response_page = None  # type: ignore[assignment]
    _PYSIDE6_AVAILABLE = False


class _PageHost(QWidget):
    def on_response_browse_notice(self) -> None:
        return None

    def on_toggle_notice_section(self, _flow: str, _checked: bool) -> None:
        return None

    def on_response_import_paths_dropped(self, _paths) -> None:
        return None

    def on_response_browse_import_files(self) -> None:
        return None

    def on_response_browse_import_folder(self) -> None:
        return None

    def on_response_clear_staged_files(self) -> None:
        return None

    def on_response_confirm_imports(self) -> None:
        return None

    def on_response_browse_output_dir(self) -> None:
        return None

    def on_response_start(self) -> None:
        return None


@unittest.skipUnless(_PYSIDE6_AVAILABLE, "PySide6 not installed")
class ResponseCorrectionPageRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_response_page_materials_table_and_fixed_output_runtime_shape(self) -> None:
        host = _PageHost()
        page = build_response_page(host)
        page.resize(1200, 900)
        page.show()
        self._app.processEvents()

        table = getattr(host, "response_materials_table")
        headers = [table.horizontalHeaderItem(index).text() for index in range(table.columnCount())]
        self.assertEqual(
            headers,
            ["原文件名", "操作", "建议映射", "当前映射", "上传状态", "上传时间", "处理结果"],
        )
        self.assertEqual(table.horizontalScrollMode().name, "ScrollPerPixel")
        header = table.horizontalHeader()
        self.assertTrue(all(header.sectionResizeMode(index) == QHeaderView.Interactive for index in range(table.columnCount())))
        pane = getattr(host, "response_processing_pane")
        output_box = getattr(host, "response_output_box")
        handle = getattr(host, "response_processing_handle")
        self.assertTrue(hasattr(pane, "set_upper_content_height"))
        self.assertTrue(hasattr(pane, "upper_content_height"))
        self.assertEqual(output_box.minimumHeight(), 160)
        self.assertEqual(output_box.maximumHeight(), 160)
        self.assertTrue(handle.isVisible())

        before = pane.upper_content_height()
        pane.set_upper_content_height(before + 60)
        self._app.processEvents()
        self.assertEqual(pane.upper_content_height(), before + 60)

        getattr(host, "response_notice_section_body").setVisible(True)
        self._app.processEvents()
        pane.set_upper_content_height(before + 100)
        self._app.processEvents()
        self.assertEqual(pane.upper_content_height(), before + 100)

        for index in range(table.columnCount()):
            table.setColumnWidth(index, 80)
        self._app.processEvents()
        self.assertGreaterEqual(
            sum(table.columnWidth(index) for index in range(table.columnCount())),
            table.viewport().width() - 2,
        )


if __name__ == "__main__":
    unittest.main()
