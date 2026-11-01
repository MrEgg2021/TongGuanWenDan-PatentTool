from __future__ import annotations

import json
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock


from core import manual_illustration_sync


class ManualIllustrationSyncTests(unittest.TestCase):
    def test_manual_shot_context_includes_fields_needed_to_debug_hangs(self) -> None:
        spec = manual_illustration_sync.ManualShotSpec(
            shot_id="response-upload-table",
            heading="5.5 文件夹扫描",
            relative_path="shots/response_correction/response-upload-table.png",
            caption="上传文件表格",
            capture="page",
            action="_nav_to_response",
        )

        context = manual_illustration_sync._format_manual_shot_context(spec)

        self.assertIn("shot_id=response-upload-table", context)
        self.assertIn("action=_nav_to_response", context)
        self.assertIn("capture=page", context)
        self.assertIn("path=shots/response_correction/response-upload-table.png", context)

    def test_manual_shot_timeout_handler_dumps_context_and_exits(self) -> None:
        spec = manual_illustration_sync.ManualShotSpec(
            shot_id="official-docs-processing-overlay",
            heading="8.5 开始处理",
            relative_path="shots/official_docs/official-docs-processing-overlay.png",
            caption="官文处理进度遮罩",
            capture="page",
            action="_nav_to_official_docs",
        )
        stderr = io.StringIO()

        def exit_func(code: int) -> None:
            raise SystemExit(code)

        with mock.patch.object(manual_illustration_sync.faulthandler, "dump_traceback") as dump_traceback:
            with self.assertRaises(SystemExit) as raised:
                manual_illustration_sync._handle_manual_shot_timeout(
                    spec,
                    timeout_seconds=12.0,
                    stderr=stderr,
                    exit_func=exit_func,
                )

        self.assertEqual(124, raised.exception.code)
        output = stderr.getvalue()
        self.assertIn("手册截图生成超时", output)
        self.assertIn("12.0s", output)
        self.assertIn("shot_id=official-docs-processing-overlay", output)
        self.assertIn("action=_nav_to_official_docs", output)
        self.assertIn("path=shots/official_docs/official-docs-processing-overlay.png", output)
        dump_traceback.assert_called_once()

    def test_manual_shot_watchdog_starts_and_cancels_timer(self) -> None:
        spec = manual_illustration_sync.ManualShotSpec(
            shot_id="settings-page",
            heading="10.1 设置页",
            relative_path="shots/settings/settings-page.png",
            caption="设置页",
            capture="page",
            action="_nav_to_settings",
        )
        timers = []

        class FakeTimer:
            def __init__(self, timeout_seconds, callback):
                self.timeout_seconds = timeout_seconds
                self.callback = callback
                self.daemon = False
                self.started = False
                self.cancelled = False
                timers.append(self)

            def start(self):
                self.started = True

            def cancel(self):
                self.cancelled = True

        with manual_illustration_sync._manual_shot_watchdog(spec, 9.0, timer_factory=FakeTimer):
            self.assertEqual(1, len(timers))
            self.assertTrue(timers[0].started)
            self.assertTrue(timers[0].daemon)
            self.assertFalse(timers[0].cancelled)

        self.assertTrue(timers[0].cancelled)

    def test_manual_capture_runtime_preserves_and_restores_preferences(self) -> None:
        from core import app_preferences, user_prefs
        original_save = user_prefs.save_prefs
        with mock.patch.object(user_prefs, "save_prefs", side_effect=AssertionError("must not write prefs")):
            with manual_illustration_sync._manual_screenshot_demo_runtime():
                app_preferences.set_main_window_geometry_v1("demo")
                self.assertIsNone(app_preferences.get_main_window_geometry_v1())
        self.assertIs(original_save, user_prefs.save_prefs)

    def test_manual_capture_runtime_suppresses_startup_env_alert(self) -> None:
        from gui.main_window.mixins.settings_mixin import SettingsMixin

        calls = []

        def fail_env_check(_window):
            calls.append("env_check")
            raise AssertionError("manual screenshot runtime must not open startup env alerts")

        with mock.patch(
            "gui.main_window.mixins.settings_mixin.auto_env_check_and_alert_if_needed",
            side_effect=fail_env_check,
        ):
            with manual_illustration_sync._manual_screenshot_demo_runtime():
                SettingsMixin._auto_env_check_and_alert_if_needed(object())

        self.assertEqual([], calls)

    def test_set_checkbox_state_blocks_demo_signals(self) -> None:
        from PySide6.QtWidgets import QApplication, QCheckBox

        app = QApplication.instance() or QApplication([])
        checkbox = QCheckBox()
        calls = []
        checkbox.toggled.connect(lambda checked: calls.append(bool(checked)))

        manual_illustration_sync._set_checkbox_state(checkbox, True)
        app.processEvents()

        self.assertTrue(checkbox.isChecked())
        self.assertEqual([], calls)

    def test_save_capture_pixmap_flattens_transparent_background(self) -> None:
        from PIL import Image
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QColor, QPainter, QPixmap
        from PySide6.QtWidgets import QApplication

        QApplication.instance() or QApplication([])
        pixmap = QPixmap(20, 20)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.fillRect(5, 5, 10, 10, QColor("black"))
        painter.end()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "flattened.png"
            manual_illustration_sync._save_capture_pixmap(pixmap, output_path)
            image = Image.open(output_path).convert("RGBA")

        self.assertEqual((255, 255, 255, 255), image.getpixel((0, 0)))
        self.assertEqual((0, 0, 0, 255), image.getpixel((10, 10)))

    def test_capture_manual_screenshots_reports_failing_shot_context(self) -> None:
        source_markdown_path = Path(tempfile.gettempdir()) / "manual-illustration-sync-source.md"
        source_markdown_path.write_text("# 标题\n", encoding="utf-8")

        spec = manual_illustration_sync.ManualShotSpec(
            shot_id="broken-shot",
            heading="6.3 页面上的主要控件",
            relative_path="shots/preview/broken-shot.png",
            caption="预览页总览",
            capture="page",
            action="_nav_to_preview",
            variant="overview",
            scenario_key="preview",
        )

        class _FakeMainWindow:
            def resize(self, *_args) -> None:
                return None

            def show(self) -> None:
                return None

            def hide(self) -> None:
                return None

            def deleteLater(self) -> None:
                return None

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "shots"
            with (
                mock.patch.object(manual_illustration_sync, "build_default_manual_shot_specs", return_value=[spec]),
                mock.patch.object(manual_illustration_sync, "_prepare_capture_fonts"),
                mock.patch.object(manual_illustration_sync, "_drain_events"),
                mock.patch.object(manual_illustration_sync, "_capture_window_page", side_effect=RuntimeError("boom")),
                mock.patch("gui_app.MainWindow", _FakeMainWindow),
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    r"shot_id=broken-shot.*action=_nav_to_preview.*capture=page.*path=shots/preview/broken-shot\.png",
                ):
                    manual_illustration_sync.capture_manual_screenshots(source_markdown_path, output_dir)

    def test_dialog_capture_cleanup_deletes_without_close_or_hide(self) -> None:
        source_markdown_path = Path(tempfile.gettempdir()) / "manual-illustration-sync-source.md"
        source_markdown_path.write_text("# 标题\n", encoding="utf-8")

        spec = manual_illustration_sync.ManualShotSpec(
            shot_id="batch-continue-error-dialog",
            heading="Word 转 XML / 案卷包",
            relative_path="shots/navigation/batch-continue-error-dialog.png",
            caption="批量处理中断提示",
            capture="dialog",
            action="batch_continue_error",
            variant="overview",
            scenario_key="navigation",
        )

        class _FakePixmap:
            def isNull(self) -> bool:
                return False

            def save(self, path: str, _fmt: str) -> bool:
                Path(path).write_bytes(b"png")
                return True

        class _FakeTarget:
            def __init__(self) -> None:
                self.close_called = False
                self.hide_called = False
                self.delete_later_called = False

            def grab(self):
                return _FakePixmap()

            def close(self) -> None:
                self.close_called = True

            def hide(self) -> None:
                self.hide_called = True

            def deleteLater(self) -> None:
                self.delete_later_called = True

        class _FakeMainWindow:
            def resize(self, *_args) -> None:
                return None

            def show(self) -> None:
                return None

            def hide(self) -> None:
                return None

            def deleteLater(self) -> None:
                return None

        target = _FakeTarget()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "shots"
            with (
                mock.patch.object(manual_illustration_sync, "build_default_manual_shot_specs", return_value=[spec]),
                mock.patch.object(manual_illustration_sync, "_prepare_capture_fonts"),
                mock.patch.object(manual_illustration_sync, "_drain_events"),
                mock.patch.object(manual_illustration_sync, "_build_blocking_alert_overlay", return_value=target),
                mock.patch.object(manual_illustration_sync, "_apply_shot_specific_adjustments"),
                mock.patch.object(manual_illustration_sync, "_sanitize_widget_tree"),
                mock.patch("gui_app.MainWindow", _FakeMainWindow),
            ):
                manual_illustration_sync.capture_manual_screenshots(source_markdown_path, output_dir)

        self.assertTrue(target.delete_later_called)
        self.assertFalse(target.close_called)
        self.assertFalse(target.hide_called)

    def test_load_manual_shot_specs_reads_module_output_dirs_and_scenario_keys(self) -> None:
        config = {
            "modules": [
                {
                    "module_id": "preview",
                    "output_dir": "preview",
                    "shots": [
                        {
                            "shot_id": "preview-page",
                            "heading": "6.3 页面上的主要控件",
                            "chapter_anchor": "6.3 页面上的主要控件",
                            "caption": "预览页总览",
                            "capture": "page",
                            "action": "_nav_to_preview",
                            "variant": "overview",
                            "purpose": "overview",
                            "priority": "high",
                            "ui_state": "page_overview",
                            "enabled": True,
                            "scenario_key": "preview",
                        }
                    ],
                }
            ]
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "manual_shots.json"
            config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

            specs = manual_illustration_sync.load_manual_shot_specs(config_path)

        self.assertEqual(1, len(specs))
        self.assertEqual("preview-page", specs[0].shot_id)
        self.assertEqual("shots/preview/preview-page.png", specs[0].relative_path)
        self.assertEqual("preview", specs[0].scenario_key)

    def test_default_manual_shot_specs_always_use_module_subdirectories(self) -> None:
        specs = manual_illustration_sync.load_manual_shot_specs()

        self.assertTrue(specs)
        for spec in specs:
            self.assertRegex(spec.relative_path, r"^shots/[^/]+/[^/]+\.png$")

    def test_load_manual_shot_specs_rejects_duplicate_shot_ids(self) -> None:
        config = {
            "modules": [
                {
                    "module_id": "preview",
                    "output_dir": "preview",
                    "shots": [
                        {
                            "shot_id": "preview-page",
                            "heading": "6.3 页面上的主要控件",
                            "chapter_anchor": "6.3 页面上的主要控件",
                            "caption": "预览页总览",
                            "capture": "page",
                            "action": "_nav_to_preview",
                            "variant": "overview",
                            "purpose": "overview",
                            "priority": "high",
                            "ui_state": "page_overview",
                            "enabled": True,
                            "scenario_key": "preview",
                        },
                        {
                            "shot_id": "preview-page",
                            "heading": "6.4 基本操作步骤",
                            "chapter_anchor": "6.4 基本操作步骤",
                            "caption": "预览页列表",
                            "capture": "page",
                            "action": "_nav_to_preview",
                            "variant": "bundle",
                            "purpose": "workflow",
                            "priority": "high",
                            "ui_state": "bundle_expanded",
                            "enabled": True,
                            "scenario_key": "preview",
                        },
                    ],
                }
            ]
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "manual_shots.json"
            config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

            with self.assertRaises(ValueError):
                manual_illustration_sync.load_manual_shot_specs(config_path)

    def test_load_manual_shot_specs_rejects_duplicate_relative_paths_case_insensitively(self) -> None:
        config = {
            "modules": [
                {
                    "module_id": "preview",
                    "output_dir": "preview",
                    "shots": [
                        {
                            "shot_id": "Preview-Page",
                            "heading": "6.3 页面上的主要控件",
                            "chapter_anchor": "6.3 页面上的主要控件",
                            "caption": "预览页总览",
                            "capture": "page",
                            "action": "_nav_to_preview",
                            "variant": "overview",
                            "purpose": "overview",
                            "priority": "high",
                            "ui_state": "page_overview",
                            "enabled": True,
                            "scenario_key": "preview",
                        }
                    ],
                },
                {
                    "module_id": "preview_dup",
                    "output_dir": "preview",
                    "shots": [
                        {
                            "shot_id": "preview-page",
                            "heading": "6.4 基本操作步骤",
                            "chapter_anchor": "6.4 基本操作步骤",
                            "caption": "预览页列表",
                            "capture": "page",
                            "action": "_nav_to_preview",
                            "variant": "bundle",
                            "purpose": "workflow",
                            "priority": "high",
                            "ui_state": "bundle_expanded",
                            "enabled": True,
                            "scenario_key": "preview",
                        }
                    ],
                },
            ]
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "manual_shots.json"
            config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

            with self.assertRaises(ValueError):
                manual_illustration_sync.load_manual_shot_specs(config_path)

    def test_load_manual_shot_specs_rejects_parent_traversal_output_dir(self) -> None:
        config = {
            "modules": [
                {
                    "module_id": "preview",
                    "output_dir": "../preview",
                    "shots": [
                        {
                            "shot_id": "preview-page",
                            "heading": "6.3 页面上的主要控件",
                            "chapter_anchor": "6.3 页面上的主要控件",
                            "caption": "预览页总览",
                            "capture": "page",
                            "action": "_nav_to_preview",
                            "variant": "overview",
                            "purpose": "overview",
                            "priority": "high",
                            "ui_state": "page_overview",
                            "enabled": True,
                            "scenario_key": "preview",
                        }
                    ],
                }
            ]
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "manual_shots.json"
            config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

            with self.assertRaises(ValueError):
                manual_illustration_sync.load_manual_shot_specs(config_path)

    def test_load_manual_shot_specs_rejects_unknown_scenario_key(self) -> None:
        config = {
            "modules": [
                {
                    "module_id": "preview",
                    "output_dir": "preview",
                    "shots": [
                        {
                            "shot_id": "preview-page",
                            "heading": "6.3 页面上的主要控件",
                            "chapter_anchor": "6.3 页面上的主要控件",
                            "caption": "预览页总览",
                            "capture": "page",
                            "action": "_nav_to_preview",
                            "variant": "overview",
                            "purpose": "overview",
                            "priority": "high",
                            "ui_state": "page_overview",
                            "enabled": True,
                            "scenario_key": "preview_unknown",
                        }
                    ],
                }
            ]
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "manual_shots.json"
            config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

            with self.assertRaises(ValueError):
                manual_illustration_sync.load_manual_shot_specs(config_path)

    def test_build_default_manual_shot_specs_expands_complex_module_coverage(self) -> None:
        specs = {item.shot_id: item for item in manual_illustration_sync.build_default_manual_shot_specs()}

        self.assertIn("sidebar-expanded", specs)
        self.assertIn("batch-page-filled", specs)
        self.assertIn("batch-request-form-dialog", specs)
        self.assertIn("batch-error-continue-dialog", specs)
        self.assertIn("response-upload-table", specs)
        self.assertIn("preview-export-options", specs)
        self.assertIn("preview-processing-overlay", specs)
        self.assertIn("preview-export-overlay", specs)
        self.assertIn("data-management-manager-facts", specs)
        self.assertIn("data-management-import-overlay", specs)
        self.assertIn("official-docs-pdf-parse-tab", specs)
        self.assertIn("official-docs-processing-overlay", specs)
        self.assertIn("official-docs-archive-consent-dialog", specs)
        self.assertIn("official-docs-pdf-parse-warning-dialog", specs)
        self.assertIn("official-docs-result-dialog", specs)
        self.assertIn("formal-review-processing-overlay", specs)
        self.assertIn("formal-review-busy-dialog", specs)
        self.assertIn("formal-review-settings-dialog", specs)
        self.assertIn("settings-env-check", specs)
        self.assertIn("settings-env-status-menu", specs)
        self.assertIn("settings-env-help-dialog", specs)
        self.assertIn("single-document-preview-option", specs)
        self.assertGreaterEqual(len(specs), 69)
        self.assertEqual("_nav_to_official_docs", specs["official-docs-page"].action)
        self.assertEqual("_nav_to_settings", specs["settings-page"].action)
        self.assertEqual("_nav_to_data_management", specs["data-management-page"].action)
        self.assertEqual("_nav_to_formal_review", specs["formal-review-page"].action)
        self.assertEqual("_nav_to_about", specs["about-page"].action)
        self.assertEqual("high", specs["response-upload-table"].priority)
        self.assertEqual("upload_state", specs["response-upload-table"].ui_state)
        self.assertEqual("tab_state", specs["official-docs-pdf-parse-tab"].purpose)
        self.assertEqual("运行前准备", specs["sidebar-expanded"].heading)
        self.assertEqual("运行前准备", specs["sidebar-expanded"].chapter_anchor)
        self.assertEqual("Word 转 XML / 案卷包", specs["single-document-page"].heading)
        self.assertEqual("Word 转 XML / 案卷包", specs["single-document-preview-option"].heading)
        self.assertEqual('请求书与常用信息', specs["data-management-manager-agency"].heading)
        self.assertEqual("官文处理", specs["official-docs-result-dialog"].heading)
        self.assertEqual("设置与关于", specs["settings-env-help-dialog"].heading)

        guide = (Path(__file__).resolve().parents[1] / "docs/USER_GUIDE.md").read_text(encoding="utf-8")
        headings = {line[3:].strip() for line in guide.splitlines() if line.startswith("## ")}
        self.assertTrue(all(spec.heading in headings for spec in specs.values()))
        self.assertTrue(all(spec.action not in {"agreement", "feature_gate"} for spec in specs.values()))

    def test_apply_manual_illustrations_inserts_generated_blocks_once_per_section(self) -> None:
        markdown = """## 2. 界面认识与导航
### 2.1 当前侧边栏结构
这里先解释界面布局。

### 2.2 侧边栏可以收起
这里解释侧边栏收起。
"""
        illustrations = [
            manual_illustration_sync.ManualIllustration(
                shot_id="sidebar-structure",
                heading="2.1 当前侧边栏结构",
                relative_path="shots/sidebar-structure.png",
                caption="当前侧边栏结构与主界面总览",
            )
        ]

        first = manual_illustration_sync.apply_manual_illustrations(markdown, illustrations)
        second = manual_illustration_sync.apply_manual_illustrations(first, illustrations)

        self.assertEqual(first, second)
        self.assertIn("<!-- AUTO-SHOT:sidebar-structure:start -->", first)
        self.assertIn("![当前侧边栏结构与主界面总览](shots/sidebar-structure.png)", first)
        section_text = first.split("### 2.1 当前侧边栏结构", 1)[1].split("### 2.2", 1)[0]
        self.assertEqual(1, section_text.count("AUTO-SHOT:sidebar-structure:start"))

    def test_apply_manual_illustrations_preserves_order_for_multiple_images_in_same_section(self) -> None:
        markdown = """## 2. 界面认识与导航
### 2.1 当前侧边栏结构
这里先解释界面布局。

### 2.2 侧边栏可以收起
这里解释侧边栏收起。
"""
        illustrations = [
            manual_illustration_sync.ManualIllustration(
                shot_id="sidebar-structure",
                heading="2.1 当前侧边栏结构",
                relative_path="shots/sidebar-structure.png",
                caption="侧边栏默认收起态",
            ),
            manual_illustration_sync.ManualIllustration(
                shot_id="sidebar-expanded",
                heading="2.1 当前侧边栏结构",
                relative_path="shots/sidebar-expanded.png",
                caption="侧边栏分组展开态",
            ),
        ]

        rendered = manual_illustration_sync.apply_manual_illustrations(markdown, illustrations)
        section_text = rendered.split("### 2.1 当前侧边栏结构", 1)[1].split("### 2.2", 1)[0]

        self.assertLess(section_text.index("sidebar-structure"), section_text.index("sidebar-expanded"))

    def test_apply_manual_illustrations_keeps_nested_relative_path_targets(self) -> None:
        markdown = """## 6. 预览 / 导出 PDF
### 6.3 页面上的主要控件
这里先解释页面布局。
"""
        illustrations = [
            manual_illustration_sync.ManualIllustration(
                shot_id="preview-page",
                heading="6.3 页面上的主要控件",
                relative_path="shots/preview/preview-page.png",
                caption="预览页总览",
            )
        ]

        rendered = manual_illustration_sync.apply_manual_illustrations(markdown, illustrations)

        self.assertIn("![预览页总览](shots/preview/preview-page.png)", rendered)

    def test_apply_manual_illustrations_removes_stale_auto_blocks_not_present_in_current_specs(self) -> None:
        markdown = """## 2. 界面认识与导航
### 2.1 当前侧边栏结构
这里先解释界面布局。

<!-- AUTO-SHOT:legacy-shot:start -->
![旧图](shots/legacy.png)
*图：旧图*
<!-- AUTO-SHOT:legacy-shot:end -->

### 2.2 侧边栏可以收起
这里解释侧边栏收起。
"""
        illustrations = [
            manual_illustration_sync.ManualIllustration(
                shot_id="sidebar-structure",
                heading="2.1 当前侧边栏结构",
                relative_path="shots/sidebar-structure.png",
                caption="侧边栏默认收起态",
            )
        ]

        rendered = manual_illustration_sync.apply_manual_illustrations(markdown, illustrations)

        self.assertNotIn("legacy-shot", rendered)
        self.assertIn("sidebar-structure", rendered)

    def test_split_markdown_for_sequential_media_preserves_text_and_local_image_order(self) -> None:
        markdown = """## 3. 单文档处理
第一段说明。

![主界面](shots/single-home.png)

第二段说明。
![远程图](https://example.com/remote.png)
![请求书弹窗](shots/request-form.png)
结尾说明。
"""

        segments = manual_illustration_sync.split_markdown_for_sequential_media(markdown)

        self.assertEqual(["text", "image", "text", "image", "text"], [item.kind for item in segments])
        self.assertIn("第一段说明", segments[0].content)
        self.assertEqual("shots/single-home.png", segments[1].raw_target)
        self.assertIn("![远程图](https://example.com/remote.png)", segments[2].content)
        self.assertEqual("shots/request-form.png", segments[3].raw_target)
        self.assertIn("结尾说明", segments[4].content)

    def test_write_screenshot_manifest_includes_shots_and_coverage_summary(self) -> None:
        illustrations = [
            manual_illustration_sync.ManualIllustration(
                shot_id="settings-page",
                heading="10.2 当前页里有哪些设置项",
                relative_path="shots/settings/settings-page.png",
                caption="其他设置页面总览",
                chapter_anchor="10.2 当前页里有哪些设置项",
                variant="overview",
                purpose="overview",
                priority="medium",
                ui_state="page_overview",
            )
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "manual.md"
            source.write_text(
                "## 10. 其他设置\n### 10.2 当前页里有哪些设置项\n正文\n\n### 10.5 环境检测会检查什么\n正文\n",
                encoding="utf-8",
            )
            manifest_path = manual_illustration_sync.write_screenshot_manifest(
                illustrations,
                Path(tmpdir),
                source_markdown_path=source,
            )
            payload = manifest_path.read_text(encoding="utf-8")

        data = json.loads(payload)
        self.assertEqual(1, data["shot_count"])
        self.assertEqual("settings-page", data["shots"][0]["shot_id"])
        self.assertEqual("shots/settings/settings-page.png", data["shots"][0]["relative_path"])
        self.assertEqual("overview", data["shots"][0]["variant"])
        self.assertEqual(2, data["coverage"]["heading_count"])
        self.assertEqual(1, data["coverage"]["covered_heading_count"])
        self.assertEqual(["10.5 环境检测会检查什么"], data["coverage"]["missing_headings"])

    def test_capture_manual_screenshots_preserves_nested_relative_output_paths(self) -> None:
        source_markdown_path = Path(tempfile.gettempdir()) / "manual-illustration-sync-source.md"
        source_markdown_path.write_text("# 标题\n", encoding="utf-8")

        spec = manual_illustration_sync.ManualShotSpec(
            shot_id="preview-page",
            heading="6.3 页面上的主要控件",
            relative_path="shots/preview/preview-page.png",
            caption="预览页总览",
            capture="page",
            action="_nav_to_preview",
            variant="overview",
            scenario_key="preview",
        )

        class _FakePixmap:
            def isNull(self) -> bool:
                return False

            def save(self, path: str, _fmt: str) -> bool:
                Path(path).write_bytes(b"png")
                return True

        class _FakeTarget:
            def grab(self):
                return _FakePixmap()

        class _FakeMainWindow:
            def resize(self, *_args) -> None:
                return None

            def show(self) -> None:
                return None

            def hide(self) -> None:
                return None

            def deleteLater(self) -> None:
                return None

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "shots"
            with (
                mock.patch.object(manual_illustration_sync, "build_default_manual_shot_specs", return_value=[spec]),
                mock.patch.object(manual_illustration_sync, "_prepare_capture_fonts"),
                mock.patch.object(manual_illustration_sync, "_drain_events"),
                mock.patch.object(manual_illustration_sync, "_capture_window_page", return_value=object()),
                mock.patch.object(manual_illustration_sync, "_resolve_capture_target", return_value=_FakeTarget()),
                mock.patch.object(manual_illustration_sync, "_apply_shot_specific_adjustments"),
                mock.patch.object(manual_illustration_sync, "_sanitize_widget_tree"),
                mock.patch("gui_app.MainWindow", _FakeMainWindow),
            ):
                illustrations = manual_illustration_sync.capture_manual_screenshots(source_markdown_path, output_dir)
            saved_exists = (output_dir / "preview" / "preview-page.png").exists()

        self.assertEqual("shots/preview/preview-page.png", illustrations[0].relative_path)
        self.assertTrue(saved_exists)

    def test_should_preserve_real_text_for_about_page_contact_fields(self) -> None:
        self.assertTrue(
            manual_illustration_sync.should_preserve_real_text(
                "邮箱：1649251313@qq.com",
                preserve_real_contact=True,
            )
        )
        self.assertTrue(
            manual_illustration_sync.should_preserve_real_text(
                "微信：MrEgg208",
                preserve_real_contact=True,
            )
        )
        self.assertFalse(
            manual_illustration_sync.should_preserve_real_text(
                "联系人邮箱：demo@example.com",
                preserve_real_contact=False,
            )
        )

    def test_apply_shot_specific_adjustments_routes_single_document_processing_variants(self) -> None:
        window = object()
        target = object()

        with mock.patch.object(manual_illustration_sync, "_populate_single_document_demo", create=True) as populate_single:
            for variant in (
                "overview",
                "preview_option",
                "header_check_overlay",
                "conversion_overlay",
            ):
                spec = manual_illustration_sync.ManualShotSpec(
                    shot_id=f"single-document-{variant}",
                    heading="",
                    relative_path="",
                    caption="",
                    capture="page",
                    action="_nav_to_home",
                    variant=variant,
                    scenario_key="single_document",
                )
                manual_illustration_sync._apply_shot_specific_adjustments(spec, target, window)

            self.assertEqual(
                [
                    mock.call(window, "overview"),
                    mock.call(window, "preview_option"),
                    mock.call(window, "header_check_overlay"),
                    mock.call(window, "conversion_overlay"),
                ],
                populate_single.call_args_list,
            )

    def test_apply_shot_specific_adjustments_routes_batch_processing_variants(self) -> None:
        window = object()
        target = object()

        with mock.patch.object(manual_illustration_sync, "_populate_batch_demo") as populate_batch:
            for variant in (
                "overview",
                "filled",
                "header_check_overlay",
                "processing_overlay",
            ):
                spec = manual_illustration_sync.ManualShotSpec(
                    shot_id=f"batch-{variant}",
                    heading="",
                    relative_path="",
                    caption="",
                    capture="page",
                    action="_nav_to_batch",
                    variant=variant,
                    scenario_key="batch",
                )
                manual_illustration_sync._apply_shot_specific_adjustments(spec, target, window)

            self.assertEqual(
                [
                    mock.call(window, "overview"),
                    mock.call(window, "filled"),
                    mock.call(window, "header_check_overlay"),
                    mock.call(window, "processing_overlay"),
                ],
                populate_batch.call_args_list,
            )

    def test_apply_shot_specific_adjustments_routes_response_variants_by_action_and_variant(self) -> None:
        window = object()
        target = object()

        with mock.patch.object(manual_illustration_sync, "_populate_response_demo") as populate_response:
            scenarios = (
                ("_nav_to_response", "entry", "response"),
                ("_nav_to_correction", "upload", "correction"),
                ("_nav_to_active_response", "fields", "active_response"),
                ("_nav_to_active_correction", "table", "active_correction"),
            )
            for action, variant, _expected_prefix in scenarios:
                spec = manual_illustration_sync.ManualShotSpec(
                    shot_id=f"{action}-{variant}",
                    heading="",
                    relative_path="",
                    caption="",
                    capture="page",
                    action=action,
                    variant=variant,
                    scenario_key="response",
                )
                manual_illustration_sync._apply_shot_specific_adjustments(spec, target, window)

            self.assertEqual(
                [
                    mock.call(window, "response", "entry"),
                    mock.call(window, "correction", "upload"),
                    mock.call(window, "active_response", "fields"),
                    mock.call(window, "active_correction", "table"),
                ],
                populate_response.call_args_list,
            )

    def test_apply_shot_specific_adjustments_routes_processing_overlay_variants_for_other_modules(self) -> None:
        window = object()
        target = object()

        with (
            mock.patch.object(manual_illustration_sync, "_populate_preview_demo") as populate_preview,
            mock.patch.object(manual_illustration_sync, "_populate_data_management_demo") as populate_data,
            mock.patch.object(manual_illustration_sync, "_populate_official_docs_demo") as populate_official,
            mock.patch.object(manual_illustration_sync, "_populate_formal_review_demo") as populate_formal,
        ):
            scenarios = (
                ("preview", "processing_overlay", populate_preview),
                ("preview", "export_overlay", populate_preview),
                ("preview", "fetch_pdf_overlay", populate_preview),
                ("data_management", "overview", populate_data),
                ("data_management", "zip_controls", populate_data),
                ("data_management", "import_overlay", populate_data),
                ("data_management", "excel_controls", populate_data),
                ("official_docs", "processing_overlay", populate_official),
                ("formal_review", "processing_overlay", populate_formal),
            )
            for scenario_key, variant, _patched in scenarios:
                spec = manual_illustration_sync.ManualShotSpec(
                    shot_id=f"{scenario_key}-{variant}",
                    heading="",
                    relative_path="",
                    caption="",
                    capture="page",
                    action="_nav_to_placeholder",
                    variant=variant,
                    scenario_key=scenario_key,
                )
                manual_illustration_sync._apply_shot_specific_adjustments(spec, target, window)

            self.assertEqual(
                [
                    mock.call(window, "processing_overlay"),
                    mock.call(window, "export_overlay"),
                    mock.call(window, "fetch_pdf_overlay"),
                ],
                populate_preview.call_args_list,
            )
            self.assertEqual(
                [
                    mock.call(window, "overview"),
                    mock.call(window, "zip_controls"),
                    mock.call(window, "import_overlay"),
                    mock.call(window, "excel_controls"),
                ],
                populate_data.call_args_list,
            )
            self.assertEqual([mock.call(window, "processing_overlay")], populate_official.call_args_list)
            self.assertEqual([mock.call(window, "processing_overlay")], populate_formal.call_args_list)

    def test_apply_shot_specific_adjustments_routes_navigation(self) -> None:
        spec = manual_illustration_sync.ManualShotSpec(
            shot_id="sidebar-expanded", heading="", relative_path="", caption="",
            capture="page", action="sidebar_expanded", variant="expanded", scenario_key="navigation",
        )
        window = object()
        with mock.patch.object(manual_illustration_sync, "_populate_navigation_demo") as populate:
            manual_illustration_sync._apply_shot_specific_adjustments(spec, object(), window)
        populate.assert_called_once_with(window, "expanded")


    def test_populate_data_management_demo_forces_guide_visibility_by_variant(self) -> None:
        for variant, expected_visible in (
            ("overview", True),
            ("zip_controls", False),
            ("excel_controls", False),
            ("import_overlay", False),
        ):
            guide_visibility = mock.Mock()
            zip_drop_zone = mock.Mock()
            zip_pick_button = mock.Mock()
            window = type(
                "FakeWindow",
                (),
                {
                    "_tgd_dm_set_guide_visible": guide_visibility,
                    "tgd_request_zip_drop_zone": zip_drop_zone,
                    "tgd_request_zip_pick_folder_button": zip_pick_button,
                },
            )()

            manual_illustration_sync._populate_data_management_demo(window, variant)

            self.assertEqual(
                [mock.call(expected_visible)],
                guide_visibility.call_args_list,
                f"variant={variant}",
            )

    def test_window_capture_with_sidebar_groups_requires_sidebar(self) -> None:
        class _WindowWithoutSidebar:
            pass

        with mock.patch.object(manual_illustration_sync, "_capture_window_page", return_value=object()):
            with self.assertRaises(RuntimeError):
                manual_illustration_sync._capture_window_page_with_sidebar_groups(
                    _WindowWithoutSidebar(),
                    "_nav_to_home",
                    domestic_expanded=True,
                    response_expanded=False,
                )


if __name__ == "__main__":
    unittest.main()
