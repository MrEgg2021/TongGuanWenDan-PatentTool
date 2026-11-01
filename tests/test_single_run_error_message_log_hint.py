from __future__ import annotations

import unittest
from unittest.mock import patch

from gui.single_run import _build_single_run_error_message


class SingleRunErrorMessageLogHintTests(unittest.TestCase):
    def test_corrupt_drawings_media_message_is_actionable(self) -> None:
        exc = RuntimeError(
            "源文件中的说明书附图内嵌图片数据已损坏，无法可靠恢复完整内容；为避免生成缺图或黑块，已停止转换。"
        )

        message = _build_single_run_error_message(exc)

        self.assertNotIn("DRAWINGS_SOURCE_MEDIA_CORRUPT", message)
        self.assertIn("重新插入原始图片", message)
        self.assertIn("本次转换已停止", message)
        self.assertNotIn("提供给技术支持", message)

    def test_message_omits_log_hint_when_log_path_unavailable(self) -> None:
        exc = RuntimeError("boom")
        exc.conversion_error_code = "ERR_NO_LOG"
        with (
            patch("gui.single_run.classify_conversion_error", return_value="ERR_NO_LOG"),
            patch("gui.single_run.get_conversion_log_path", return_value=""),
        ):
            message = _build_single_run_error_message(exc)

        self.assertIn("转换未完成", message)
        self.assertEqual(exc.conversion_error_code, "ERR_NO_LOG")
        self.assertNotIn("conversion.log", message)
        self.assertNotIn("日志路径", message)

    def test_message_keeps_log_hint_when_dev_log_path_exists(self) -> None:
        exc = RuntimeError("boom")
        exc.conversion_error_code = "ERR_WITH_LOG"
        with (
            patch("gui.single_run.classify_conversion_error", return_value="ERR_WITH_LOG"),
            patch("gui.single_run.get_conversion_log_path", return_value=r"D:\demo\conversion.log"),
        ):
            message = _build_single_run_error_message(exc)

        self.assertIn("查看程序日志", message)
        self.assertEqual(exc.conversion_error_code, "ERR_WITH_LOG")
        self.assertIn("conversion.log", message)
        self.assertIn(r"日志路径：D:\demo\conversion.log", message)


if __name__ == "__main__":
    unittest.main()
