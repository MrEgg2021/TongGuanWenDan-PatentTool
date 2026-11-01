from __future__ import annotations

import unittest
from pathlib import Path

from gui.update_log_dialog import _load_changelogs


class UpdateLogDialogTests(unittest.TestCase):
    def test_loads_new_project_initial_log_only(self) -> None:
        entries = _load_changelogs()

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0][0], "V1.0.0")
        self.assertNotIn("主程序、许可证生成工具、命令行入口和用户手册版本统一更新", entries[0][1])
        self.assertIn("无需激活", entries[0][1])

    def test_entry_is_inside_about_page_not_sidebar(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        about_source = (repo_root / "gui/about_ui.py").read_text(encoding="utf-8")
        sidebar_source = (repo_root / "gui/ui_layout_impl/modern_shell_impl.py").read_text(encoding="utf-8")

        self.assertIn('QPushButton("查看更新日志")', about_source)
        self.assertNotIn("nav_changelog", sidebar_source)

    def test_viewer_uses_expandable_sections_instead_of_version_dropdown(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        viewer_source = (repo_root / "gui/update_log_dialog.py").read_text(encoding="utf-8")

        self.assertIn("header.setCheckable(True)", viewer_source)
        self.assertIn("expanded=index == 0", viewer_source)
        self.assertNotIn("QComboBox", viewer_source)

    def test_user_logs_do_not_expose_internal_maintenance_language(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        log_dir = repo_root / "用户使用手册+更新日志" / "更新日志"
        forbidden = (
            "死代码",
            "死逻辑",
            "无效私有函数",
            "兼容入口",
            "冗余路径",
            "GUI 内部路径",
            "更新程序内显示版本",
            "升级",
            "重新启动软件",
            "关闭旧软件",
            "提供源码",
            "EXE 下载",
            "WAL 数据",
            "发卡台账",
            "图片队列",
            "JVM",
        )

        for path in log_dir.glob("v*.md"):
            text = path.read_text(encoding="utf-8")
            for phrase in forbidden:
                self.assertNotIn(phrase, text, f"{path.name} contains internal phrase: {phrase}")


if __name__ == "__main__":
    unittest.main()
