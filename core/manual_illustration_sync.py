from __future__ import annotations

import faulthandler
import json
import os
import re
import sys
import threading
import time
from contextlib import ExitStack, contextmanager
from dataclasses import asdict
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Callable, TextIO

from .manual_illustration_sync_parts import specs as _shot_specs

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget


_HEADING_RE = re.compile(r"^(?P<indent>\s{0,3})(?P<marks>#{1,6})\s+(?P<title>.+?)\s*$")
_IMAGE_RE = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<target>[^)\s]+)(?:\s+\"[^\"]*\")?\)")
_ANY_AUTO_BLOCK_RE = re.compile(r"\n?<!-- AUTO-SHOT:[^:\n]+:start -->.*?<!-- AUTO-SHOT:[^:\n]+:end -->\n?", re.DOTALL)


ManualIllustration = _shot_specs.ManualIllustration
MarkdownSyncSegment = _shot_specs.MarkdownSyncSegment
ManualShotSpec = _shot_specs.ManualShotSpec
_KNOWN_SCENARIO_KEYS = _shot_specs._KNOWN_SCENARIO_KEYS


def get_default_manual_shot_config_path() -> Path:
    return _shot_specs.get_default_manual_shot_config_path()


def _normalize_posix_fragment(value: str, *, field_name: str) -> str:
    return _shot_specs._normalize_posix_fragment(value, field_name=field_name)


def _build_relative_shot_path(output_dir: str, shot_id: str) -> str:
    return _shot_specs._build_relative_shot_path(output_dir, shot_id)


def load_manual_shot_specs(config_path: Path | None = None) -> list[ManualShotSpec]:
    return _shot_specs.load_manual_shot_specs(config_path)


def build_default_manual_shot_specs() -> list[ManualShotSpec]:
    return _shot_specs.build_default_manual_shot_specs()


_CURRENT_MANUAL_CAPTURE_SPEC: ManualShotSpec | None = None
_DEFAULT_MANUAL_SHOT_TIMEOUT_SECONDS = 180.0
_MANUAL_SHOT_TIMEOUT_ENV = "MANUAL_SCREENSHOT_SHOT_TIMEOUT_SECONDS"
_MANUAL_SHOT_PROGRESS_ENV = "MANUAL_SCREENSHOT_PROGRESS"


def _format_manual_shot_context(spec: ManualShotSpec) -> str:
    return (
        f"shot_id={spec.shot_id}, "
        f"action={spec.action}, "
        f"capture={spec.capture}, "
        f"path={spec.relative_path}"
    )


def _manual_shot_timeout_seconds() -> float:
    raw_value = os.environ.get(_MANUAL_SHOT_TIMEOUT_ENV, "").strip()
    if not raw_value:
        return _DEFAULT_MANUAL_SHOT_TIMEOUT_SECONDS
    try:
        return float(raw_value)
    except ValueError as exc:
        raise ValueError(f"{_MANUAL_SHOT_TIMEOUT_ENV} 必须是数字秒数: {raw_value}") from exc


def _manual_shot_progress_enabled() -> bool:
    raw_value = os.environ.get(_MANUAL_SHOT_PROGRESS_ENV, "").strip().lower()
    return raw_value not in {"0", "false", "no", "off"}


def _log_manual_shot_progress(
    stage: str,
    *,
    index: int,
    total: int,
    spec: ManualShotSpec,
    elapsed_seconds: float | None = None,
    stderr: TextIO = sys.stderr,
) -> None:
    if not _manual_shot_progress_enabled():
        return
    elapsed = "" if elapsed_seconds is None else f", elapsed={elapsed_seconds:.1f}s"
    print(
        f"[manual-screenshot] {stage} {index}/{total}: {_format_manual_shot_context(spec)}{elapsed}",
        file=stderr,
        flush=True,
    )


def _handle_manual_shot_timeout(
    spec: ManualShotSpec,
    timeout_seconds: float,
    *,
    stderr: TextIO = sys.stderr,
    exit_func: Callable[[int], object] = os._exit,
) -> None:
    print(
        "[manual-screenshot] 手册截图生成超时: "
        f"timeout={timeout_seconds:.1f}s, {_format_manual_shot_context(spec)}",
        file=stderr,
        flush=True,
    )
    faulthandler.dump_traceback(file=stderr, all_threads=True)
    try:
        stderr.flush()
    except Exception:
        pass
    exit_func(124)


@contextmanager
def _manual_shot_watchdog(
    spec: ManualShotSpec,
    timeout_seconds: float,
    *,
    timer_factory: Callable[[float, Callable[[], None]], object] = threading.Timer,
):
    if timeout_seconds <= 0:
        yield
        return

    timer = timer_factory(
        timeout_seconds,
        lambda: _handle_manual_shot_timeout(spec, timeout_seconds),
    )
    setattr(timer, "daemon", True)
    timer.start()
    try:
        yield
    finally:
        timer.cancel()


def build_generated_figure_block(illustration: ManualIllustration) -> str:
    return (
        f"<!-- AUTO-SHOT:{illustration.shot_id}:start -->\n"
        f"![{illustration.caption}]({illustration.relative_path})\n"
        f"*图：{illustration.caption}*\n"
        f"<!-- AUTO-SHOT:{illustration.shot_id}:end -->"
    )


def apply_manual_illustrations(markdown_text: str, illustrations: list[ManualIllustration]) -> str:
    text = str(markdown_text or "")
    text = _ANY_AUTO_BLOCK_RE.sub("\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    lines = text.splitlines()
    headings = _collect_headings(lines)
    grouped: dict[str, list[ManualIllustration]] = {}
    for illustration in illustrations:
        grouped.setdefault(illustration.heading, []).append(illustration)

    insertions: list[tuple[int, list[ManualIllustration]]] = []
    for heading_title, group in grouped.items():
        match = _find_heading(headings, heading_title)
        if match is None:
            continue
        _, level, _ = match
        end_index = _find_section_end(headings, match, len(lines), level)
        insertions.append((end_index, group))

    for end_index, group in sorted(insertions, key=lambda item: item[0], reverse=True):
        block_lines: list[str] = [""]
        for illustration in group:
            block_lines.extend(build_generated_figure_block(illustration).splitlines())
            block_lines.append("")
        lines[end_index:end_index] = block_lines

    rendered = "\n".join(lines)
    rendered = re.sub(r"\n{3,}", "\n\n", rendered)
    return rendered.strip() + "\n"


def split_markdown_for_sequential_media(markdown_text: str) -> list[MarkdownSyncSegment]:
    text = str(markdown_text or "")
    segments: list[MarkdownSyncSegment] = []
    cursor = 0
    for match in _IMAGE_RE.finditer(text):
        target = match.group("target").strip()
        if _is_remote_target(target):
            continue
        if match.start() > cursor:
            segments.append(MarkdownSyncSegment(kind="text", content=text[cursor:match.start()]))
        segments.append(
            MarkdownSyncSegment(
                kind="image",
                alt_text=match.group("alt").strip(),
                raw_target=target,
            )
        )
        cursor = match.end()
    if cursor < len(text):
        segments.append(MarkdownSyncSegment(kind="text", content=text[cursor:]))

    merged: list[MarkdownSyncSegment] = []
    for segment in segments:
        if segment.kind == "text":
            if not segment.content:
                continue
            if merged and merged[-1].kind == "text":
                merged[-1] = MarkdownSyncSegment(kind="text", content=merged[-1].content + segment.content)
            else:
                merged.append(segment)
            continue
        merged.append(segment)
    return merged


def write_screenshot_manifest(
    illustrations: list[ManualIllustration],
    output_dir: Path,
    *,
    source_markdown_path: Path | None = None,
) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "manifest.json"
    payload = {
        "shot_count": len(illustrations),
        "shots": [asdict(item) for item in illustrations],
        "coverage": build_manual_coverage_report(source_markdown_path, illustrations),
    }
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def _resolve_shot_output_path(output_dir: Path, relative_path: str) -> Path:
    output_root = Path(output_dir).resolve()
    relative = PurePosixPath(str(relative_path or "").replace("\\", "/").strip())
    if not relative.parts or relative.parts[0] != "shots":
        raise ValueError(f"relative_path 必须以 shots/ 开头: {relative_path}")
    inner_parts = relative.parts[1:]
    if not inner_parts or any(part in {"", ".", ".."} for part in inner_parts):
        raise ValueError(f"relative_path 非法: {relative_path}")
    shot_path = output_root.joinpath(*inner_parts)
    shot_path.parent.mkdir(parents=True, exist_ok=True)
    return shot_path


@contextmanager
def _manual_screenshot_demo_runtime():
    """Isolate ordinary preferences while capturing manual screenshots."""
    from core import app_preferences
    from core import user_prefs

    def get_demo_pref(_key, default=None):
        return default

    def noop(*_args, **_kwargs):
        return None

    def get_demo_window_state() -> dict:
        return {}

    def noop_env_check(_self) -> None:
        return None

    patches: list[tuple[object, str, object]] = []

    def patch_attr(owner: object | None, name: str, value: object) -> None:
        if owner is None or not hasattr(owner, name):
            return
        patches.append((owner, name, getattr(owner, name)))
        setattr(owner, name, value)

    try:
        patch_attr(user_prefs, "get_pref", get_demo_pref)
        patch_attr(user_prefs, "set_pref", noop)
        patch_attr(user_prefs, "pop_pref", noop)
        patch_attr(user_prefs, "save_prefs", noop)

        patch_attr(app_preferences, "get_pref", get_demo_pref)
        patch_attr(app_preferences, "set_pref", noop)
        patch_attr(app_preferences, "pop_pref", noop)
        patch_attr(app_preferences, "set_main_window_geometry_v1", noop)
        patch_attr(app_preferences, "set_main_window_state_v1", noop)
        patch_attr(app_preferences, "get_main_window_geometry_v1", lambda: None)
        patch_attr(app_preferences, "get_main_window_state_v1", get_demo_window_state)

        window_state_module = sys.modules.get("gui.windowing.window_state_controller")
        patch_attr(window_state_module, "set_main_window_geometry_v1", noop)
        patch_attr(window_state_module, "set_main_window_state_v1", noop)
        patch_attr(window_state_module, "get_main_window_geometry_v1", lambda: None)
        patch_attr(window_state_module, "get_main_window_state_v1", get_demo_window_state)

        try:
            from gui.main_window.mixins import settings_mixin
            from gui.main_window.mixins.settings_env_impl import ops as settings_env_ops
            from gui.main_window.mixins.settings_env_impl.ops_impl import actions_ops as settings_env_actions
        except Exception:
            settings_mixin = None
            settings_env_ops = None
            settings_env_actions = None
        patch_attr(settings_env_ops, "auto_env_check_and_alert_if_needed", noop)
        patch_attr(settings_env_actions, "auto_env_check_and_alert_if_needed", noop)
        patch_attr(settings_mixin, "auto_env_check_and_alert_if_needed", noop)
        patch_attr(getattr(settings_mixin, "SettingsMixin", None), "_auto_env_check_and_alert_if_needed", noop_env_check)

        yield
    finally:
        for owner, name, old_value in reversed(patches):
            setattr(owner, name, old_value)


def capture_manual_screenshots(source_markdown_path: Path, output_dir: Path) -> list[ManualIllustration]:
    global _CURRENT_MANUAL_CAPTURE_SPEC
    try:
        with _manual_screenshot_demo_runtime():
            return _capture_manual_screenshots_impl(source_markdown_path, output_dir)
    except Exception as exc:
        spec = _CURRENT_MANUAL_CAPTURE_SPEC
        if spec is not None:
            raise RuntimeError(
                "手册截图生成失败: "
                f"shot_id={spec.shot_id}, "
                f"action={spec.action}, "
                f"capture={spec.capture}, "
                f"path={spec.relative_path}"
            ) from exc
        raise
    finally:
        _CURRENT_MANUAL_CAPTURE_SPEC = None


def _capture_manual_screenshots_impl(source_markdown_path: Path, output_dir: Path) -> list[ManualIllustration]:
    source_markdown_path = Path(source_markdown_path).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from core.formal_review.wordlists import load_wordlist_profile_store
    from gui.main_window.mixins.formal_review_ops.shared import _RULE_OPTIONS
    from gui.widgets_impl.formal_review import FormalReviewSettingsDialog
    from gui.widgets_impl.request_form.dialog_impl.import_result_dialog import ImportResultDialog
    from gui.widgets_impl.request_form.dialog_impl.main_dialog_impl.dialog import RequestFormDialog
    from gui.widgets_impl.tgd_zip_import_review_dialog_impl.main_dialog_impl.dialog import (
        TgdZipImportReviewDialog,
    )
    from gui_app import MainWindow

    app = QApplication.instance() or QApplication([])
    _prepare_capture_fonts(app)

    specs = build_default_manual_shot_specs()
    illustrations: list[ManualIllustration] = []

    page_captures: dict[str, Callable[[QWidget], QWidget]] = {
        "_nav_to_home": lambda owner: _capture_window_page(owner, "_nav_to_home"),
        "_nav_to_batch": lambda owner: _capture_window_page(owner, "_nav_to_batch"),
        "_nav_to_response": lambda owner: _capture_window_page(owner, "_nav_to_response"),
        "_nav_to_correction": lambda owner: _capture_window_page(owner, "_nav_to_correction"),
        "_nav_to_active_response": lambda owner: _capture_window_page(owner, "_nav_to_active_response"),
        "_nav_to_active_correction": lambda owner: _capture_window_page(owner, "_nav_to_active_correction"),
        "_nav_to_preview": lambda owner: _capture_window_page(owner, "_nav_to_preview"),
        "_nav_to_data_management": lambda owner: _capture_window_page(owner, "_nav_to_data_management"),
        "_nav_to_official_docs": lambda owner: _capture_window_page(owner, "_nav_to_official_docs"),
        "_nav_to_formal_review": lambda owner: _capture_window_page(owner, "_nav_to_formal_review"),
        "_nav_to_settings": lambda owner: _capture_window_page(owner, "_nav_to_settings"),
        "_nav_to_about": lambda owner: _capture_window_page(owner, "_nav_to_about"),
        "sidebar_collapsed": lambda owner: _capture_sidebar_group_state(owner, domestic_expanded=False, response_expanded=False),
        "sidebar_expanded": lambda owner: _capture_sidebar_group_state(owner, domestic_expanded=True, response_expanded=True),
        "home_with_expanded_nav": lambda owner: _capture_window_page_with_sidebar_groups(
            owner,
            "_nav_to_home",
            domestic_expanded=True,
            response_expanded=False,
        ),
    }

    dialog_captures: dict[str, Callable[[QWidget], QWidget]] = {
        "request_form": lambda owner: _build_request_form_dialog(owner, RequestFormDialog),
        "batch_request_form": lambda owner: _build_batch_request_form_dialog(owner, RequestFormDialog),
        "batch_continue_error": lambda owner: _build_blocking_alert_overlay(
            owner,
            title="批量处理出错",
            body="在批量处理中，文件：\nCN202610002_一种示例系统.docx\n\n发生错误：\n请求书信息不完整\n\n是否继续处理剩余文件？",
            primary_text="继续",
            secondary_text="取消",
        ),
        "preview_service_help": lambda owner: _build_blocking_alert_overlay(
            owner,
            title="轻量预览服务未启动",
            body="未检测到官方轻量预览服务。请确认预览插件已启动；如果实际端口不是 8080，可修改端口后重试。",
            primary_text="修改端口",
            secondary_text="取消",
        ),
        "import_result": lambda owner: _build_import_result_dialog(owner, ImportResultDialog),
        "zip_import_review": lambda owner: _build_zip_import_dialog(owner, TgdZipImportReviewDialog),
        "official_docs_archive_consent": lambda owner: _build_official_docs_archive_consent_dialog(owner),
        "official_docs_pdf_parse_notice": lambda owner: _build_official_docs_pdf_parse_notice_dialog(owner),
        "official_docs_result": lambda owner: _build_official_docs_result_dialog(owner),
        "formal_review_busy": lambda owner: _build_formal_review_busy_dialog(owner),
        "formal_review_settings": lambda owner: _build_formal_review_settings_dialog(
            owner,
            FormalReviewSettingsDialog,
            load_wordlist_profile_store=load_wordlist_profile_store,
            rule_options=_RULE_OPTIONS,
        ),
        "settings_env_menu": lambda owner: _build_settings_env_menu(owner),
        "settings_env_help": lambda owner: _build_settings_env_help_dialog(owner),
    }

    global _CURRENT_MANUAL_CAPTURE_SPEC
    shot_timeout_seconds = _manual_shot_timeout_seconds()
    total_specs = len(specs)
    for index, spec in enumerate(specs, start=1):
        _CURRENT_MANUAL_CAPTURE_SPEC = spec
        started_at = time.monotonic()
        _log_manual_shot_progress("start", index=index, total=total_specs, spec=spec)
        window = None
        try:
            with _manual_shot_watchdog(spec, shot_timeout_seconds):
                window = MainWindow()
                window.resize(1440, 1024)
                window.show()
                _drain_events(app)
                base_widget = (
                    dialog_captures[spec.action](window)
                    if spec.capture == "dialog"
                    else page_captures[spec.action](window)
                )
                try:
                    target_widget = _resolve_capture_target(window, spec, base_widget)
                    _apply_shot_specific_adjustments(spec, target_widget, window)
                    target_widget = _resolve_capture_target(window, spec, target_widget)
                    _sanitize_widget_tree(target_widget, preserve_real_contact=spec.scenario_key == "about")
                    _drain_events(app)
                    shot_path = _resolve_shot_output_path(output_dir, spec.relative_path)
                    pixmap = target_widget.grab()
                    if pixmap.isNull():
                        raise RuntimeError(f"截图为空: {spec.shot_id}")
                    _save_capture_pixmap(pixmap, shot_path)
                    illustrations.append(
                        ManualIllustration(
                            shot_id=spec.shot_id,
                            heading=spec.heading,
                            relative_path=spec.relative_path,
                            caption=spec.caption,
                            chapter_anchor=spec.chapter_anchor or spec.heading,
                            variant=spec.variant,
                            purpose=spec.purpose,
                            priority=spec.priority,
                            ui_state=spec.ui_state,
                        )
                    )
                finally:
                    if spec.capture == "dialog":
                        try:
                            target_widget.deleteLater()
                        except Exception:
                            pass
                        _drain_events(app)
            _log_manual_shot_progress(
                "done",
                index=index,
                total=total_specs,
                spec=spec,
                elapsed_seconds=time.monotonic() - started_at,
            )
        finally:
            if window is not None:
                try:
                    window.hide()
                except Exception:
                    pass
                try:
                    window.deleteLater()
                except Exception:
                    pass
                _drain_events(app)
    return illustrations


def _capture_window_page(window: QWidget, action_name: str) -> QWidget:
    from PySide6.QtWidgets import QApplication

    action = getattr(window, action_name, None)
    if not callable(action):
        raise AttributeError(f"未找到页面切换方法: {action_name}")
    action()
    app = QApplication.instance()
    if app is not None:
        _drain_events(app)
    return window


def _capture_sidebar_group_state(window: QWidget, *, domestic_expanded: bool, response_expanded: bool) -> QWidget:
    from PySide6.QtWidgets import QApplication
    from gui.ui_layout_impl.modern_shell_impl import _sync_all_sidebar_groups

    nav_home = getattr(window, "_nav_to_home", None)
    if callable(nav_home):
        nav_home()
    shell = getattr(window, "_modern_shell", None)
    sidebar = getattr(shell, "sidebar", None)
    if sidebar is None:
        raise RuntimeError("未找到现代侧边栏容器，无法截图侧边栏分组状态")
    setattr(sidebar, "_domestic_conversion_expanded", bool(domestic_expanded))
    setattr(sidebar, "_response_correction_expanded", bool(response_expanded))
    _sync_all_sidebar_groups(sidebar)
    app = QApplication.instance()
    if app is not None:
        _drain_events(app)
    return sidebar


def _capture_window_page_with_sidebar_groups(
    window: QWidget,
    action_name: str,
    *,
    domestic_expanded: bool,
    response_expanded: bool,
) -> QWidget:
    """切换页面后展开指定侧边栏分组，返回窗口以截取整窗。"""
    from PySide6.QtWidgets import QApplication
    from gui.ui_layout_impl.modern_shell_impl import _sync_all_sidebar_groups

    _capture_window_page(window, action_name)
    shell = getattr(window, "_modern_shell", None)
    sidebar = getattr(shell, "sidebar", None)
    if sidebar is None:
        raise RuntimeError("未找到现代侧边栏容器，无法展开侧边栏分组")
    setattr(sidebar, "_domestic_conversion_expanded", bool(domestic_expanded))
    setattr(sidebar, "_response_correction_expanded", bool(response_expanded))
    _sync_all_sidebar_groups(sidebar)
    app = QApplication.instance()
    if app is not None:
        _drain_events(app)
    return window


def _build_request_form_dialog(owner: QWidget, dialog_type) -> QWidget:
    from PySide6.QtCore import QSize

    dialog = dialog_type(owner, embedded=True)
    try:
        dialog.resize(QSize(1180, 860))
    except Exception:
        dialog.resize(1180, 860)
    try:
        dialog.set_target_file_name("示例交底书.docx")
    except Exception:
        pass
    _fill_demo_text_fields(
        dialog,
        {
            "edit_title": "一种用于示例演示的处理方法",
            "fact_contact_name": "演示联系人",
            "fact_contact_phone": "13800000000",
            "fact_contact_email": "demo@example.com",
        },
    )
    dialog.show()
    return dialog


def _build_batch_request_form_dialog(owner: QWidget, dialog_type) -> QWidget:
    dialog = _build_request_form_dialog(owner, dialog_type)
    try:
        dialog.btn_ok.setText("确定（进入下一个）")
        dialog.btn_cancel.setText("取消（回到上一个）")
        btn_back = getattr(dialog, "btn_back", None)
        if btn_back is not None:
            btn_back.setText("取消（终止批量）")
        btn_save = getattr(dialog, "btn_save", None)
        if btn_save is not None:
            btn_save.setVisible(False)
    except Exception:
        pass
    return dialog


def _build_blocking_alert_overlay(
    owner: QWidget,
    *,
    title: str,
    body: str,
    primary_text: str,
    secondary_text: str,
    body_variant: str | None = None,
) -> QWidget:
    from gui.ui_modals import build_blocking_alert
    from gui.dialog_utils import resolve_modal_owner

    resolved_owner = resolve_modal_owner(owner)
    overlay = build_blocking_alert(
        resolved_owner,
        title_text=title,
        body_text=body,
        primary_text=primary_text,
        secondary_text=secondary_text,
        body_variant=body_variant,
    )
    try:
        overlay.setParent(resolved_owner)
    except Exception:
        pass
    try:
        if resolved_owner is not None:
            overlay.resize(resolved_owner.size())
    except Exception:
        pass
    try:
        if resolved_owner is not None:
            overlay.setGeometry(resolved_owner.rect())
    except Exception:
        pass
    overlay.show()
    try:
        overlay.raise_()
    except Exception:
        pass
    return overlay


def _capture_dialog_from_exec(builder: Callable[[], object]) -> QWidget:
    from PySide6.QtWidgets import QDialog
    from unittest.mock import patch

    captured: list[QDialog] = []

    def _fake_exec(self):
        captured.append(self)
        return int(QDialog.Rejected)

    with patch.object(QDialog, "exec", _fake_exec):
        builder()

    if not captured:
        raise RuntimeError("未捕获到对话框实例")
    dialog = captured[-1]
    dialog.show()
    return dialog


def _prepare_capture_fonts(app) -> None:
    try:
        from PySide6.QtGui import QFont, QFontDatabase
    except Exception:
        return

    font_candidates = [
        Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\msyhbd.ttc"),
        Path(r"C:\Windows\Fonts\msyhl.ttc"),
        Path(r"C:\Windows\Fonts\simsun.ttc"),
    ]
    loaded_families: list[str] = []
    for candidate in font_candidates:
        if not candidate.exists():
            continue
        try:
            font_id = QFontDatabase.addApplicationFont(str(candidate))
        except Exception:
            continue
        if font_id < 0:
            continue
        try:
            loaded_families.extend(QFontDatabase.applicationFontFamilies(font_id) or [])
        except Exception:
            continue

    preferred_family = ""
    for family in loaded_families:
        if any(keyword in family for keyword in ("YaHei", "微软雅黑", "SimSun", "宋体")):
            preferred_family = family
            break
    if not preferred_family and loaded_families:
        preferred_family = loaded_families[0]
    if not preferred_family:
        return

    try:
        current_font = app.font()
        point_size = current_font.pointSize() if current_font.pointSize() > 0 else 10
    except Exception:
        point_size = 10
    try:
        app.setFont(QFont(preferred_family, point_size))
    except Exception:
        pass


def _build_import_result_dialog(owner: QWidget, dialog_type) -> QWidget:
    dialog = dialog_type(
        owner,
        {
            "processed_count": 6,
            "new_records": [
                {"applicant": "演示申请人 A", "inventor": "演示发明人 A", "source": "case-a.zip"},
                {"applicant": "演示申请人 B", "inventor": "演示发明人 B", "source": "case-b.zip"},
            ],
            "dup_records": [
                {"applicant": "演示申请人 C", "inventor": "演示发明人 C", "source": "case-c.zip"},
            ],
            "skipped_count": 1,
            "errors": ["case-d.zip: 缺少请求书字段", "case-e.zip: 重复条目已跳过"],
        },
    )
    dialog.show()
    return dialog


def _build_zip_import_dialog(owner: QWidget, dialog_type) -> QWidget:
    from unittest.mock import patch

    with ExitStack() as stack:
        for attr_name in (
            "_setup_candidate_completers",
            "_setup_agency_table_candidate_delegate",
            "_load_from_request_info",
        ):
            original = getattr(dialog_type, attr_name, None)
            if callable(original):
                stack.enter_context(patch.object(dialog_type, attr_name, lambda self: None))
        dialog = dialog_type(
            owner,
            embedded=True,
            initial_request_info={},
            source_path=r"D:\demo\批量导入\case-demo.zip",
        )
    try:
        dialog.resize(1240, 900)
    except Exception:
        dialog.resize(1240, 900)
    try:
        dialog.file_label.setText("当前文件：case-demo.zip")
    except Exception:
        pass
    _fill_demo_text_fields(
        dialog,
        {
            "fact_applicant_name": "演示申请人",
            "fact_inventor_name": "演示发明人",
            "fact_contact_name": "演示联系人",
            "fact_contact_phone": "13800000000",
            "fact_contact_email": "demo@example.com",
            "fact_agency_name": "演示代理机构",
            "fact_agency_code": "A00001",
        },
    )
    dialog.show()
    return dialog


def _fill_demo_text_fields(widget: QWidget, mapping: dict[str, str]) -> None:
    for attr_name, value in mapping.items():
        target = getattr(widget, attr_name, None)
        if target is None:
            continue
        try:
            if hasattr(target, "setText"):
                target.setText(value)
        except Exception:
            continue


def _resolve_capture_target(window: QWidget, spec: ManualShotSpec, fallback: QWidget) -> QWidget:
    from PySide6.QtWidgets import QWidget as QtWidget

    target_attr = str(getattr(spec, "target_attr", "") or "").strip()
    if not target_attr:
        return fallback
    target = getattr(window, target_attr, None)
    return target if isinstance(target, QtWidget) else fallback


def _build_formal_review_settings_dialog(owner: QWidget, dialog_type, *, load_wordlist_profile_store, rule_options) -> QWidget:
    active_profile, profiles = load_wordlist_profile_store()
    profiles = dict(profiles or {})
    if not profiles:
        profiles = {
            "精简默认": {
                "claims": {"forbidden": [], "sensitive": []},
                "description": {
                    "forbidden": ["其特征在于", "其特征是", "其特征为", "如权利要求", "根据权利要求", "权利要求书"],
                    "sensitive": [],
                },
            },
            "严格预设（旧版）": {
                "claims": {"forbidden": ["最佳", "唯一"], "sensitive": ["大约", "左右"]},
                "description": {"forbidden": ["必须", "所有"], "sensitive": ["优选", "进一步"]},
            },
        }
        active_profile = "精简默认"
    ensure_state = getattr(owner, "_ensure_formal_review_state", None)
    if callable(ensure_state):
        try:
            ensure_state()
        except Exception:
            pass
    dialog = dialog_type(
        owner,
        wordlist_profiles=profiles,
        active_wordlist_profile=str(active_profile or "精简默认"),
        rule_params=dict(getattr(owner, "_formal_review_rule_params", {}) or {}),
        comment_author=str(getattr(owner, "_formal_review_comment_author", "") or "通官文旦-专利工具"),
        highlight_colors=dict(getattr(owner, "_formal_review_highlight_colors", {}) or {}),
        rule_enabled=dict(getattr(owner, "_formal_review_rule_enabled", {}) or {}),
        rule_options=rule_options,
    )
    try:
        dialog.resize(1100, 760)
    except Exception:
        pass
    dialog.show()
    return dialog


def _build_official_docs_archive_consent_dialog(owner: QWidget) -> QWidget:
    from gui.official_docs_dialogs_impl import show_official_docs_archive_consent_dialog

    return _capture_dialog_from_exec(lambda: show_official_docs_archive_consent_dialog(owner, doc_version=1))


def _build_official_docs_pdf_parse_notice_dialog(owner: QWidget) -> QWidget:
    from gui.official_docs_dialogs_impl import show_official_docs_pdf_parse_enable_notice_dialog

    return _capture_dialog_from_exec(lambda: show_official_docs_pdf_parse_enable_notice_dialog(owner))


def _build_official_docs_result_dialog(owner: QWidget) -> QWidget:
    from gui.official_docs_dialogs_impl import show_official_docs_done_dialog

    items = [
        {
            "display_name": "第一次审查意见通知书",
            "status": "success",
            "source_zip_path": r"D:\demo\official_docs\CN202610001.zip",
            "summary_pdf_path": r"D:\demo\official_docs\summary\CN202610001_第一次审查意见通知书.pdf",
            "archive_pdf_path": r"D:\demo\official_docs\archive\CN202610001\CN202610001_第一次审查意见通知书.pdf",
            "output_pdf_name": "CN202610001_第一次审查意见通知书.pdf",
        },
        {
            "display_name": "补正通知书",
            "status": "skip",
            "source_zip_path": r"D:\demo\official_docs\CN202610002.zip",
            "summary_pdf_path": "",
            "archive_pdf_path": "",
            "output_pdf_name": "跳过：同名冲突",
        },
        {
            "display_name": "驳回决定",
            "status": "fail",
            "source_zip_path": r"D:\demo\official_docs\CN202610003.zip",
            "summary_pdf_path": "",
            "archive_pdf_path": "",
            "output_pdf_name": "失败：PDF 解析字段缺失",
        },
    ]
    return _capture_dialog_from_exec(
        lambda: show_official_docs_done_dialog(
            owner,
            total=3,
            success=1,
            skipped=1,
            failed=1,
            items=items,
            open_dirs=[r"D:\demo\official_docs\summary"],
            excel_path=r"D:\demo\official_docs\summary\处理结果.xlsx",
            run_dir=r"D:\demo\official_docs\summary",
        )
    )


def _build_formal_review_busy_dialog(owner: QWidget) -> QWidget:
    from PySide6.QtWidgets import QMessageBox

    dialog = QMessageBox(QMessageBox.Information, "形式审查", "当前任务正在执行，请稍后重试。", QMessageBox.Ok, owner)
    dialog.show()
    return dialog


def _build_settings_env_menu(owner: QWidget) -> QWidget:
    from PySide6.QtWidgets import QMenu

    menu = QMenu(owner)
    menu.addAction("重新检测")
    try:
        if bool(getattr(owner, "_env_last_show_help", True)):
            menu.addAction("查看处理建议")
    except Exception:
        menu.addAction("查看处理建议")
    menu.adjustSize()
    menu.show()
    return menu


def _build_settings_env_help_dialog(owner: QWidget) -> QWidget:
    from gui.main_window.mixins.settings_env_impl.ops_impl.word_env_ops import build_hijack_help_text

    detail = (
        "检测到 Word 后台端口被挟持。\n\n"
        + build_hijack_help_text(hijacked=True, detail="")
        + "\n如预览服务端口被占用，可先点击“修改检测端口”后重新检测。"
    )
    return _build_blocking_alert_overlay(
        owner,
        title="检测到 Word 后台端口被挟持",
        body=detail,
        primary_text="关闭",
        secondary_text="关闭",
    )


def _set_combo_value(combo, *, data=None, text: str = "") -> None:
    if combo is None:
        return
    try:
        index = -1
        if data is not None and hasattr(combo, "findData"):
            index = int(combo.findData(data))
        if index < 0 and text and hasattr(combo, "findText"):
            index = int(combo.findText(text))
        if index >= 0 and hasattr(combo, "setCurrentIndex"):
            combo.setCurrentIndex(index)
    except Exception:
        return


def _set_checkbox_state(widget, checked: bool) -> None:
    if widget is None or not hasattr(widget, "setChecked"):
        return
    try:
        from PySide6.QtCore import QSignalBlocker

        with QSignalBlocker(widget):
            widget.setChecked(bool(checked))
    except Exception:
        try:
            widget.setChecked(bool(checked))
        except Exception:
            pass


def _save_capture_pixmap(pixmap, path: Path) -> None:
    from PySide6.QtGui import QColor, QPainter, QPixmap

    output_path = Path(path)
    to_save = pixmap
    try:
        has_alpha = bool(pixmap.hasAlphaChannel())
    except Exception:
        has_alpha = False
    if has_alpha:
        canvas = QPixmap(pixmap.size())
        canvas.fill(QColor("white"))
        painter = QPainter(canvas)
        try:
            painter.drawPixmap(0, 0, pixmap)
        finally:
            painter.end()
        to_save = canvas
    if not to_save.save(str(output_path), "PNG"):
        raise RuntimeError(f"截图保存失败: {output_path}")


def _fill_table(table, rows: list[list[str]]) -> None:
    if table is None:
        return
    from PySide6.QtWidgets import QTableWidgetItem

    try:
        table.clearContents()
        table.setRowCount(len(rows))
    except Exception:
        return
    for row_index, row in enumerate(rows):
        for col_index, value in enumerate(row):
            try:
                if col_index >= int(table.columnCount()):
                    break
                table.setItem(row_index, col_index, QTableWidgetItem(str(value)))
            except Exception:
                continue


def _fill_list_widget(widget, items: list[str]) -> None:
    if widget is None:
        return
    from PySide6.QtWidgets import QListWidgetItem

    try:
        widget.clear()
    except Exception:
        return
    for item in items:
        try:
            widget.addItem(QListWidgetItem(str(item)))
        except Exception:
            continue


def _show_processing_overlay_for_demo(
    window: QWidget,
    *,
    scope: str,
    status: str,
    file_text: str,
    percent: int = 0,
    primary_text: str | None = None,
    detail_text: str | None = None,
    batch_info: str | None = None,
    hide_cancel: bool = False,
    warn_text: str = "",
) -> None:
    try:
        window._progress_scope = scope
    except Exception:
        pass
    try:
        window._show_processing_overlay(status, file_text)
    except Exception:
        return

    overlay = getattr(window, "_processing_overlay", None)
    if overlay is None:
        return

    if hide_cancel:
        try:
            from PySide6.QtWidgets import QPushButton

            cancel_button = overlay.findChild(QPushButton, "processingCancelButton")
            if cancel_button is not None:
                cancel_button.setEnabled(False)
                cancel_button.setVisible(False)
        except Exception:
            pass
    if warn_text:
        try:
            from PySide6.QtWidgets import QLabel

            warn_label = overlay.findChild(QLabel, "processingWarnLabel")
            if warn_label is not None:
                warn_label.setText(str(warn_text))
        except Exception:
            pass
    if primary_text is not None or detail_text is not None or percent:
        try:
            window._update_processing_overlay(int(percent), primary_text, detail_text, batch_info)
        except Exception:
            pass


def _populate_navigation_demo(window: QWidget, variant: str) -> None:
    _populate_settings_demo(window)

def _populate_single_document_demo(window: QWidget, variant: str) -> None:
    demo_input = r"D:\demo\single\CN202610001_一种示例装置.docx"
    demo_output = r"D:\demo\single\output"
    _fill_demo_text_fields(
        window,
        {
            "path_edit": demo_input,
            "output_dir_edit": demo_output,
        },
    )
    try:
        refresh = getattr(window, "_refresh_single_file_card", None)
        if callable(refresh):
            refresh()
    except Exception:
        pass
    try:
        set_current = getattr(window, "_set_current_file_label", None)
        if callable(set_current):
            set_current(demo_input)
    except Exception:
        pass
    _set_checkbox_state(getattr(window, "chk_claims", None), True)
    _set_checkbox_state(getattr(window, "chk_description", None), True)
    _set_checkbox_state(getattr(window, "chk_drawings", None), True)
    _set_checkbox_state(getattr(window, "chk_abstract", None), True)
    _set_checkbox_state(getattr(window, "chk_request_form", None), True)
    _set_checkbox_state(getattr(window, "chk_auto_open_preview", None), True)
    _set_checkbox_state(getattr(window, "radio_invention", None), True)
    _set_checkbox_state(getattr(window, "radio_utility_model", None), False)
    try:
        window._last_single_patent_type = "invention"
    except Exception:
        pass
    try:
        window.status_label.setText("🔵 状态：空闲")
    except Exception:
        pass
    _populate_settings_demo(window)

    if variant == "overview":
        return

    header_summary = "页眉检测：申请信息确认页✓  权利要求书✓  说明书✓  说明书摘要✓  说明书附图✓"
    try:
        window._header_precheck_summary = header_summary
    except Exception:
        pass

    if variant == "header_check_overlay":
        try:
            window._header_precheck_stage = "步骤 2/2：页眉扫描"
        except Exception:
            pass
        _show_processing_overlay_for_demo(
            window,
            scope="single",
            status="正在预检查页眉…",
            file_text=os.path.basename(demo_input),
            percent=0,
            primary_text="正在预检查页眉…",
            detail_text="步骤 2/2：正在后台扫描页眉并分析章节结构与必需页眉结果，请稍候…",
        )
        return

    if variant == "conversion_overlay":
        try:
            window._header_precheck_stage = "预检查完成"
        except Exception:
            pass
        _show_processing_overlay_for_demo(
            window,
            scope="single",
            status="正在准备转换...",
            file_text=os.path.basename(demo_input),
            percent=1,
            primary_text="正在启动转换...",
            detail_text="正在后台启动 Word 并加载配置...",
        )


def _populate_batch_demo(window: QWidget, variant: str) -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QListWidgetItem

    demo_files = [
        r"D:\demo\batch\一种示例装置.docx",
        r"D:\demo\batch\一种示例方法.docx",
        r"D:\demo\batch\一种示例系统.docx",
    ]
    file_list = getattr(window, "file_list_widget", None)
    if file_list is not None:
        try:
            file_list.clear()
            if variant != "overview":
                for path in demo_files:
                    item = QListWidgetItem(os.path.basename(path))
                    item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                    item.setCheckState(Qt.Checked)
                    file_list.addItem(item)
        except Exception:
            pass
    _fill_demo_text_fields(
        window,
        {
            "batch_zip_name_edit": "" if variant == "overview" else "20260409批量案卷",
            "batch_filter_edit": "",
        },
    )
    _set_checkbox_state(getattr(window, "batch_chk_confirm_req", None), variant != "overview")
    try:
        window.batch_stats_label.setVisible(variant != "overview")
        window.batch_stats_label.setText("共3个文件  已选中3个" if variant != "overview" else "")
    except Exception:
        pass
    try:
        window.batch_type_toolbar_label.setText("已选中 (3)" if variant != "overview" else "已选中 (0)")
    except Exception:
        pass
    try:
        window.status_label.setText("🔵 状态：空闲")
    except Exception:
        pass
    try:
        window._batch_file_types = {
            demo_files[0]: "invention",
            demo_files[1]: "invention",
            demo_files[2]: "utility_model",
        }
    except Exception:
        pass
    try:
        set_current = getattr(window, "_set_current_file_label", None)
        if callable(set_current) and variant != "overview":
            set_current(demo_files[0])
    except Exception:
        pass
    _populate_settings_demo(window)

    if variant in {"overview", "filled"}:
        return

    if variant == "header_check_overlay":
        try:
            window._header_precheck_stage = "步骤 2/2：结果分析 (1/3)"
            window._header_precheck_summary = "页眉检测：申请信息确认页✅  权利要求书✅  说明书✅  说明书摘要✅  说明书附图✅"
        except Exception:
            pass
        _show_processing_overlay_for_demo(
            window,
            scope="batch",
            status="正在预检查页眉...",
            file_text=os.path.basename(demo_files[0]),
            percent=0,
            primary_text="正在预检查页眉...",
            detail_text="步骤 2/2：已在后台完成页眉扫描，正在分析章节结构和必需页眉结果 (1/3)...",
        )
        return

    if variant == "processing_overlay":
        _show_processing_overlay_for_demo(
            window,
            scope="batch",
            status="正在批量处理...",
            file_text="",
            percent=0,
            primary_text="正在处理...",
            detail_text="正在准备处理当前文件...",
            batch_info="第 1/3 个文件 | 成功：0 | 失败：0",
        )


def _populate_response_demo(window: QWidget, prefix: str, variant: str) -> None:
    base_fields = {
        f"{prefix}_application_no_edit": "202610000001.X",
        f"{prefix}_title_edit": "一种用于手册演示的处理系统",
        f"{prefix}_applicant_edit": "演示申请人有限公司",
        f"{prefix}_document_path_edit": rf"D:\demo\{prefix}\100001_权利要求书.docx",
        f"{prefix}_output_dir_edit": rf"D:\demo\output\{prefix}",
    }
    if prefix in {"response", "correction"}:
        base_fields.update(
            {
                f"{prefix}_notice_edit": rf"D:\demo\{prefix}\通知书.zip",
                f"{prefix}_notice_name_edit": "第一次审查意见通知书",
                f"{prefix}_issue_date_edit": "2026-04-09",
                f"{prefix}_doc_serial_edit": "20260409001",
            }
        )
    if prefix in {"response", "active_response"}:
        base_fields[f"{prefix}_opinion_edit"] = rf"D:\demo\{prefix}\意见陈述书.docx"
    _fill_demo_text_fields(window, base_fields)
    _set_combo_value(getattr(window, f"{prefix}_patent_type_combo", None), data="invention")
    _set_combo_value(getattr(window, f"{prefix}_document_type_combo", None), data="100001")

    upload_rows: list[list[str]] = []
    if prefix in {"response", "active_response"}:
        upload_rows.append(["意见陈述书", "意见陈述书.docx", "意见陈述书", "Word", "2026-04-09 09:10", "已更新"])
    upload_rows.extend(
        [
            ["权利要求书", "100001_权利要求书.docx", "四书文档", "Word", "2026-04-09 09:11", "已更新"],
            ["说明书", "100002_说明书.zip", "XML案卷包", "XML案卷包", "2026-04-09 09:12", "已更新"],
            ["说明书附图", "100003_说明书附图.docx", "四书文档", "Word", "2026-04-09 09:13", "已更新"],
        ]
    )
    if variant in {"upload", "upload_result", "output_ready", "table"}:
        _fill_table(getattr(window, f"{prefix}_uploaded_files_table", None), upload_rows)

    if prefix in {"correction", "active_correction"} and variant in {"table", "output_ready", "upload"}:
        correction_rows = [
            ["说明书", "第 12 段", "通信模块相连", "通信模块电连接"],
            ["权利要求书", "权利要求 1", "包含 A", "包括 A 和 B"],
        ]
        _fill_table(getattr(window, f"{prefix}_items_table", None), correction_rows)

    status_label = getattr(window, f"{prefix}_status_label", None)
    if status_label is not None:
        try:
            if variant == "output_ready":
                status_label.setText("材料列表已更新；如需同步到实际打包内容，请再次点击“上传/更新已关联材料”。")
            elif variant in {"upload_result", "table"}:
                status_label.setText("已同步当前材料关联状态。")
            else:
                status_label.setText("等待开始")
        except Exception:
            pass


def _populate_preview_demo(window: QWidget, variant: str) -> None:
    from PySide6.QtWidgets import QAbstractItemView

    from core.cnipa_preview.models import PreviewDocument
    from gui.ui_layout_impl.preview_page import rebuild_preview_document_rows

    preview_documents = (
        PreviewDocument("5:110101:request.xml", "110101", "发明专利请求书", "request.xml"),
        PreviewDocument("6:110401:substantive.xml", "110401", "实质审查请求书", "substantive.xml"),
        PreviewDocument("4:100004:abstract.xml", "100004", "说明书摘要", "abstract.xml"),
        PreviewDocument("1:100001:claims.xml", "100001", "权利要求书", "claims.xml"),
        PreviewDocument("2:100002:description.xml", "100002", "说明书", "description.xml"),
        PreviewDocument("3:100003:drawings.xml", "100003", "说明书附图", "drawings.xml"),
    )

    bundle_source = r"D:\demo\preview\批量总包.zip"
    selected_zip = r"D:\demo\preview\批量总包\CN202610001.zip"
    window._preview_cases = [
        {
            "kind": "bundle",
            "name": "批量总包.zip",
            "source_path": bundle_source,
            "children": [
                {"name": "CN202610001", "zip_path": selected_zip},
                {"name": "CN202610002", "zip_path": r"D:\demo\preview\批量总包\CN202610002.zip"},
            ],
        },
        {"kind": "single", "name": "CN202610099 单案.zip", "zip_path": r"D:\demo\preview\CN202610099.zip"},
    ]
    window._preview_bundle_expanded = {bundle_source: True}
    window._preview_case_filter_text = ""
    refresh = getattr(window, "_refresh_preview_case_list_ui", None)
    if callable(refresh):
        try:
            refresh(selected_path=selected_zip if variant != "overview" else None)
        except Exception:
            pass

    if variant == "overview":
        # The page opens in lightweight mode for first-time users.  The normal
        # UI applies this asynchronously, while the screenshot is captured
        # immediately after page construction.
        try:
            window.preview_start_button.setText("开始轻量预览")
            window.preview_action_summary_label.setText(
                "选择案件后先识别文件；无 list.xml 的四书 ZIP 也可预览。"
            )
        except Exception:
            pass
        return

    # This demonstration includes the dynamic six-document manifest, so the
    # visible mode must match the full-preview behavior it is illustrating.
    for button, checked in (
        (getattr(window, "preview_legacy_mode_button", None), False),
        (getattr(window, "preview_full_mode_button", None), True),
    ):
        if button is not None:
            button.setChecked(checked)
    try:
        window.preview_subtitle_label.setText(
            "全量预览：需安装专利业务办理系统客户端（CNIPA），支持预览和导出案卷内全部文件。"
        )
        window.preview_document_list.setDragDropMode(QAbstractItemView.InternalMove)
    except Exception:
        pass

    try:
        window._preview_selected_zip_path = selected_zip
        window.on_preview_case_selection_changed()
    except Exception:
        pass

    window._preview_documents = preview_documents
    rebuild_preview_document_rows(window, preview_documents)

    from PySide6.QtCore import QSignalBlocker, Qt
    from gui.ui_layout_impl.preview_page import _PREVIEW_STATUS_ROLE, _PREVIEW_STATUS_TONE_ROLE

    window._preview_last_zip_path = selected_zip
    window._preview_merged_temp_pdf_path = r"D:\demo\preview\CN202610001_预览.pdf"
    pending = variant in {"bundle", "processing_overlay"}
    retry = variant in {"retry", "fetch_pdf_overlay"}
    blocker = QSignalBlocker(window.preview_document_list)
    for document in preview_documents:
        item = window.preview_doc_items[document.id]
        failed = retry and document.code == "100002"
        item.setCheckState(Qt.Checked)
        item.setData(_PREVIEW_STATUS_ROLE, "待生成" if pending else "渲染失败" if failed else "已渲染")
        item.setData(_PREVIEW_STATUS_TONE_ROLE, "pending" if pending else "error" if failed else "success")
    del blocker
    window.preview_start_button.setText("生成并打开预览 PDF" if pending or retry else "打开预览 PDF")
    window.preview_export_button.setText("另存预览 PDF…")
    window.preview_export_button.setEnabled(not pending and not retry)
    window.preview_action_summary_label.setText(
        "已选 6 项，其中 1 项尚未生成 PDF；点击“生成并打开预览 PDF”。" if retry else
        "已选 6 项，其中 6 项尚未生成 PDF；点击“生成并打开预览 PDF”。" if pending else
        "已就绪：CN202610001_预览.pdf。打开或另存直接使用此 PDF；调整勾选和顺序后无需重复渲染已完成的文件。"
    )
    if variant == "bundle":
        return
    if variant == "processing_overlay":
        _show_processing_overlay_for_demo(
            window,
            scope="preview",
            status="正在生成 PDF 预览...",
            file_text=os.path.basename(selected_zip),
            percent=2,
            primary_text="正在生成 PDF 预览...",
            detail_text="",
        )
        return
    if variant == "export_overlay":
        window.preview_action_summary_label.setText(
            "预览 PDF 已保存到：D:\\demo\\preview\\导出\\CN202610001_预览.pdf"
        )
        return
    if variant == "fetch_pdf_overlay":
        _show_processing_overlay_for_demo(
            window,
            scope="preview",
            status="正在获取官方预览 PDF...",
            file_text="",
            percent=35,
            primary_text="正在获取官方预览 PDF...",
            detail_text="正在获取 100002.pdf ...",
        )


def _populate_data_management_demo(window: QWidget, variant: str) -> None:
    set_guide_visible = getattr(window, "_tgd_dm_set_guide_visible", None)
    if callable(set_guide_visible):
        try:
            set_guide_visible(variant == "overview")
        except Exception:
            pass
    _set_checkbox_state(getattr(window, "tgd_request_zip_confirm_each_checkbox", None), variant != "excel_controls")
    _set_checkbox_state(getattr(window, "tgd_request_zip_parse_poa_checkbox", None), True)
    zip_drop_zone = getattr(window, "tgd_request_zip_drop_zone", None)
    zip_pick_button = getattr(window, "tgd_request_zip_pick_folder_button", None)
    zip_manual_button = getattr(window, "tgd_request_zip_manual_entry_button", None)
    excel_buttons = (
        getattr(window, "tgd_excel_export_template_button", None),
        getattr(window, "tgd_excel_import_button", None),
        getattr(window, "tgd_excel_export_button", None),
        getattr(window, "tgd_excel_export_masked_button", None),
    )
    try:
        if zip_drop_zone is not None:
            zip_drop_zone.setVisible(variant != "excel_controls")
    except Exception:
        pass
    for control in (zip_pick_button, zip_manual_button):
        try:
            if control is not None:
                control.setVisible(variant != "excel_controls")
        except Exception:
            pass
    for control in excel_buttons:
        try:
            if control is not None:
                control.setEnabled(True)
        except Exception:
            pass
    if variant == "import_overlay":
        _show_processing_overlay_for_demo(
            window,
            scope="data_management",
            status="正在批量导入...",
            file_text="准备开始...",
            percent=34,
            primary_text="正在导入 (2/6)",
            detail_text="正在处理：case-demo-02.zip",
        )
        return
    if variant in {"overview", "zip_controls", "excel_controls"}:
        return
    if variant in {"facts", "agency", "linkage", "manager_facts", "manager_agency", "manager_linkage"}:
        show_manager = getattr(window, "_tgd_dm_show_fact_manager", None)
        if callable(show_manager):
            try:
                show_manager()
            except Exception:
                pass
        manager = getattr(window, "tgd_fact_record_manager_dialog", None)
        if manager is None:
            return
        try:
            manager.set_write_enabled(True)
        except Exception:
            pass
        try:
            manager._dirty = False
        except Exception:
            pass
        tabs = getattr(manager, "tabs", None)
        if tabs is not None:
            try:
                tabs.setCurrentIndex(1 if variant in {"agency", "manager_agency"} else 0)
            except Exception:
                pass
        _fill_table(
            getattr(manager, "fact_table_left", None),
            [
                ["☑", "演示申请人有限公司", "张三", "演示联系人", "13800000000", "A 组"],
                ["☐", "示例科技有限公司", "李四", "项目联系人", "13900000000", "B 组"],
            ],
        )
        _fill_table(
            getattr(manager, "fact_table_right", None),
            [
                ["☑", "CN202610001.X", "POA-2026-001", "北京市海淀区", "演示摘要"],
                ["☐", "CN202610002.X", "POA-2026-002", "上海市浦东新区", "另一条摘要"],
            ],
        )
        _fill_table(
            getattr(manager, "agency_table", None),
            [
                ["☑", "北京示例代理事务所", "A00001", "王代理", "ZL2026001", "010-88886666"],
                ["☐", "上海示例代理事务所", "A00002", "赵代理", "ZL2026002", "021-66668888"],
            ],
        )
        if variant in {"linkage", "manager_linkage"}:
            _fill_table(
                getattr(manager, "fact_table_left", None),
                [
                    ["☑", "演示申请人有限公司", "张三", "演示联系人", "13800000000", "请求书-A"],
                    ["☐", "演示申请人有限公司", "李四", "演示联系人", "13800000000", "请求书-B"],
                ],
            )
            _fill_table(
                getattr(manager, "fact_table_right", None),
                [
                    ["☑", "CN202610001.X", "POA-2026-001", "申请人×发明人组合", "写回请求书候选"],
                    ["☐", "CN202610002.X", "POA-2026-002", "申请人×发明人组合", "历史记录候选"],
                ],
            )
        return


def _populate_official_docs_demo(window: QWidget, variant: str) -> None:
    from PySide6.QtWidgets import QListWidgetItem, QTableWidgetItem, QTreeWidgetItem

    tree = getattr(window, "official_docs_tree", None)
    if tree is not None:
        try:
            tree.clear()
            bundle = QTreeWidgetItem(["批量通知书总包 (2/2)"])
            child_one = QTreeWidgetItem(["CN202610001_第一次审查意见通知书.zip"])
            child_two = QTreeWidgetItem(["CN202610002_补正通知书.zip"])
            bundle.addChild(child_one)
            bundle.addChild(child_two)
            tree.addTopLevelItem(bundle)
            bundle.setExpanded(True)
            tree.setCurrentItem(child_two if variant == "output_detail" else child_one)
        except Exception:
            pass
    try:
        window.official_docs_list_count_label.setText("2 项")
        if variant == "output_detail":
            window.official_docs_current_label.setText("CN202610002_补正通知书.zip")
            window.official_docs_meta_label.setText(
                "申请号: CN202610002.X\n通知书名称: 补正通知书\n发文日: 2026-04-02\n内部编号: -\n通知书代码: -"
            )
            window.official_docs_output_preview.setText(
                "预计信息\n预计输出 PDF 名称: CN202610002_补正通知书.pdf\n预计汇总路径: D:\\demo\\official_docs\\summary\n预计归档路径: D:\\demo\\official_docs\\archive\n\n"
                "实际输出 PDF 名称: CN202610002_补正通知书.pdf\n实际汇总路径: D:\\demo\\official_docs\\summary\\汇总.pdf\n实际归档路径: D:\\demo\\official_docs\\archive\\CN202610002"
            )
        else:
            window.official_docs_current_label.setText("CN202610001_第一次审查意见通知书.zip")
            window.official_docs_meta_label.setText(
                "申请号: CN202610001.X\n通知书名称: 第一次审查意见通知书\n发文日: 2026-04-02\n内部编号: -\n通知书代码: -"
            )
            window.official_docs_output_preview.setText(
                "预计信息\n预计输出 PDF 名称: CN202610001_第一次审查意见通知书.pdf\n预计汇总路径: D:\\demo\\official_docs\\summary\n预计归档路径: D:\\demo\\official_docs\\archive"
            )
        window.official_docs_validation_error.setText("")
    except Exception:
        pass

    tabs = getattr(window, "official_docs_tabs", None)
    if tabs is not None:
        try:
            tabs.setCurrentIndex({"overview": 0, "task_expanded": 0, "output_detail": 0, "naming": 1, "custom_naming": 1, "pdf_parse": 2}.get(variant, 0))
        except Exception:
            pass
    toggle = getattr(window, "_set_official_docs_list_detail_visible", None)
    if callable(toggle):
        try:
            toggle(variant in {"task_expanded", "output_detail"})
        except Exception:
            pass

    if variant in {"naming", "custom_naming", "pdf_parse"}:
        type_list = getattr(window, "official_docs_settings_type_list", None)
        if type_list is not None:
            try:
                type_list.clear()
                for text in ("第一次审查意见通知书", "补正通知书", "驳回决定"):
                    type_list.addItem(QListWidgetItem(text))
                type_list.setCurrentRow(0)
            except Exception:
                pass
        _fill_list_widget(
            getattr(window, "official_docs_filename_fields_list", None),
            ["专利类型", "发明名称", "申请号", "通知书名称", "发文日"],
        )
        try:
            window.official_docs_settings_type_search_edit.setText("")
            window.official_docs_settings_line_preview.setText(
                "文件名预览：发明_一种用于演示的处理系统_CN202610001_第一次审查意见通知书_2026-04-09"
            )
        except Exception:
            pass
        alias_table = getattr(window, "official_docs_alias_table", None)
        if alias_table is not None:
            try:
                alias_table.clearContents()
                alias_table.setRowCount(2)
                alias_table.setItem(0, 0, QTableWidgetItem("第一次审查意见通知书"))
                alias_table.setItem(0, 1, QTableWidgetItem("一通"))
                alias_table.setItem(1, 0, QTableWidgetItem("补正通知书"))
                alias_table.setItem(1, 1, QTableWidgetItem("补正"))
            except Exception:
                pass

    if variant == "custom_naming":
        _set_combo_value(getattr(window, "official_docs_naming_mode_combo", None), data="custom")
    else:
        _set_combo_value(getattr(window, "official_docs_naming_mode_combo", None), data="default")

    if variant == "pdf_parse":
        _set_checkbox_state(getattr(window, "official_docs_chk_exam_pdf_parse", None), True)
        set_checks = getattr(window, "_set_pdf_parse_field_checks_enabled", None)
        if callable(set_checks):
            try:
                set_checks(True)
            except Exception:
                pass
        for key, checkbox in (getattr(window, "official_docs_pdf_parse_field_checks", {}) or {}).items():
            _set_checkbox_state(checkbox, key in {"applicant", "inventor", "examiner", "reject_reason", "prior_art"})
    if variant == "processing_overlay":
        _set_checkbox_state(getattr(window, "official_docs_chk_exam_pdf_parse", None), True)
        _show_processing_overlay_for_demo(
            window,
            scope="official_docs",
            status="正在处理官文（已启用PDF解析）...",
            file_text="CN202610001.zip",
            percent=45,
            primary_text="正在处理官文 (1/3)",
            detail_text="正在解析：第一次审查意见通知书",
            warn_text="已启用PDF解析，处理耗时较久且可能存在误差，请在处理完成后自行检查核对。",
        )
    try:
        window._official_docs_dirty = False
    except Exception:
        pass


def _populate_formal_review_demo(window: QWidget, variant: str) -> None:
    from PySide6.QtWidgets import QTreeWidgetItem

    ensure_state = getattr(window, "_ensure_formal_review_state", None)
    if callable(ensure_state):
        try:
            ensure_state()
        except Exception:
            pass

    text_mapping = {
        "formal_review_file_edit": r"D:\demo\formal_review\一种示例装置.docx",
    }
    _fill_demo_text_fields(window, text_mapping)
    try:
        window.formal_review_word_state_label.setText("Word状态：已连接（一种示例装置.docx）")
        window.formal_review_dirty_state_label.setText("文档变更：否")
        window.formal_review_sync_digest_label.setText(
            "最近同步：开始审查｜写入 3｜跳过 0｜失败 0｜清旧 2｜清高亮 2｜原因 -｜副本 一种示例装置.docx"
        )
    except Exception:
        pass
    if variant == "overview":
        try:
            window.formal_review_word_state_label.setText("Word状态：未连接")
            window.formal_review_dirty_state_label.setText("文档变更：未知")
            window.formal_review_sync_digest_label.setText("最近同步：暂无")
        except Exception:
            pass

    _set_checkbox_state(getattr(window, "formal_review_mode_plain_radio", None), variant == "plain_mode")
    _set_checkbox_state(getattr(window, "formal_review_mode_word_radio", None), variant != "plain_mode")
    _set_combo_value(getattr(window, "formal_review_wordlist_profile_combo", None), text="精简默认")
    try:
        window.formal_review_claims_input_text.setPlainText(
            "1.一种示例装置，其特征在于，包括壳体、控制器和通信模块。\n2.根据权利要求1所述的示例装置，其特征在于通信模块与控制器电连接。"
        )
        window.formal_review_description_text.setPlainText("本发明涉及一种示例装置，用于说明形式审查页面的真实布局。")
        window.formal_review_abstract_text.setPlainText("本发明公开了一种用于演示的示例装置。")
        window.formal_review_drawings_text.setPlainText("图1 为系统结构示意图。\n图2 为控制流程示意图。")
        window.formal_review_marker_edit.setPlainText("1、壳体；2、控制器；3、通信模块")
    except Exception:
        pass

    tabs = getattr(window, "formal_review_tabs", None)
    tab_index = {
        "claims_tab": 0,
        "description_tab": 1,
        "abstract_tab": 2,
        "drawings_tab": 3,
    }.get(variant, 0)
    if tabs is not None:
        try:
            tabs.setCurrentIndex(tab_index)
        except Exception:
            pass

    tree = getattr(window, "formal_review_results_tree", None)
    if tree is not None:
        try:
            tree.clear()
            root_one = QTreeWidgetItem(["附图图号核对（1）", "", "", ""])
            child_one = QTreeWidgetItem(["权1", "警告", "附图图号未在实施方式内覆盖：3", ""])
            root_two = QTreeWidgetItem(["连续重复词语（1）", "", "", ""])
            child_two = QTreeWidgetItem(["权2", "提醒", "检测到相邻重复词语：连接连接", ""])
            root_one.addChild(child_one)
            root_two.addChild(child_two)
            tree.addTopLevelItem(root_one)
            tree.addTopLevelItem(root_two)
            root_one.setExpanded(True)
            root_two.setExpanded(True)
            tree.setCurrentItem(child_one)
        except Exception:
            pass

    try:
        window.formal_review_issue_meta_label.setText(
            "附图图号核对\n权1\n附图图号未在实施方式内覆盖：3"
        )
        window.formal_review_issue_ignore_toggle.setChecked(variant == "actions")
        window.formal_review_issue_context_before.setPlainText("……包括壳体、控制器和通信模块")
        window.formal_review_issue_context_hit.setPlainText("3")
        window.formal_review_issue_context_after.setPlainText("，其特征在于通信模块与控制器电连接。")
    except Exception:
        pass
    if variant == "results":
        try:
            window.formal_review_issue_meta_label.setText(
                "连续重复词语\n权2\n检测到相邻重复词语：连接连接"
            )
            window.formal_review_issue_context_hit.setPlainText("连接连接")
            window.formal_review_issue_context_after.setPlainText("，以实现稳定通信。")
        except Exception:
            pass
    if variant == "actions":
        try:
            window.formal_review_issue_meta_label.setText(
                "连续重复词语（已忽略）\n权2\n检测到相邻重复词语：连接连接"
            )
            window.formal_review_issue_context_hit.setPlainText("连接连接")
            window.formal_review_issue_context_after.setPlainText("，以实现稳定通信。")
        except Exception:
            pass

    _fill_table(
        getattr(window, "formal_review_summary_table", None),
        [["权利要求书", "2", "1", "1"], ["说明书", "1", "1", "0"]],
    )
    _fill_table(
        getattr(window, "formal_review_claims_table", None),
        [["权利要求1", "18 字", "0"], ["权利要求2", "26 字", "1"]],
    )
    _fill_table(
        getattr(window, "formal_review_claims_rule_table", None),
        [["术语一致性", "警告", "命中 1 次"]],
    )
    _fill_table(
        getattr(window, "formal_review_description_rule_table", None),
        [["绝对化用语", "提醒", "命中 1 次"]],
    )
    _fill_table(
        getattr(window, "formal_review_abstract_rule_table", None),
        [["摘要长度", "合规", "248/300"]],
    )
    if variant == "processing_overlay":
        overlay_title = "正在执行形式审查并同步批注，请不要编辑 Word 文档，请稍等。"
        overlay_file = os.path.basename(r"D:\demo\formal_review\一种示例装置.docx")
        show_overlay = getattr(window, "_show_formal_review_overlay", None)
        update_overlay = getattr(window, "_update_formal_review_overlay", None)
        if callable(show_overlay):
            try:
                show_overlay(overlay_title, overlay_file)
            except Exception:
                pass
            if callable(update_overlay):
                try:
                    update_overlay(84, "正在执行规则审查，请稍等。", overlay_file)
                except Exception:
                    pass
            return
        _show_processing_overlay_for_demo(
            window,
            scope="formal_review",
            status=overlay_title,
            file_text=overlay_file,
            percent=84,
            primary_text="正在执行规则审查，请稍等。",
            detail_text=overlay_file,
            hide_cancel=True,
            warn_text="⚠ 形式审查进行中：请勿手动编辑 Word 正文或切换窗口，避免定位偏差。",
        )


def _populate_settings_demo(window: QWidget) -> None:
    _set_checkbox_state(getattr(window, "settings_req_form_skip_tip", None), True)
    _set_checkbox_state(getattr(window, "settings_opt_center", None), True)
    _set_checkbox_state(getattr(window, "settings_table_img_center", None), True)
    _set_checkbox_state(getattr(window, "settings_id_validation_cn", None), True)
    _set_checkbox_state(getattr(window, "settings_id_validation_uscc", None), True)
    _set_combo_value(getattr(window, "settings_desc_split_mode", None), text="智能分段")
    try:
        window.settings_scale_ratio.setValue(0.8)
        window.settings_env_legacy_preview_status.setText("已连接（127.0.0.1:8080）")
        window.settings_env_preview_status.setText("官方渲染组件：已就绪，可复用")
        window.settings_env_runtime_status.setText("正常")
        window.settings_env_word_status.setText("Word 16+")
        window.settings_env_wps_status.setText("正常")
        window.settings_env_pdf_export_status.setText("正常")
    except Exception:
        pass
    try:
        collect = getattr(window, "_collect_settings_snapshot", None)
        if callable(collect):
            window._settings_saved_snapshot = collect()
    except Exception:
        pass



def _response_action_to_prefix(action: str) -> str:
    return {
        "_nav_to_response": "response",
        "_nav_to_correction": "correction",
        "_nav_to_active_response": "active_response",
        "_nav_to_active_correction": "active_correction",
    }.get(str(action or "").strip(), "response")


def _apply_shot_specific_adjustments(spec: ManualShotSpec, widget: QWidget, window: QWidget) -> None:
    scenario_key = str(spec.scenario_key or "").strip()
    variant = str(spec.variant or "").strip()

    if scenario_key == "navigation":
        _populate_navigation_demo(window, variant or "overview")
        return

    if scenario_key == "single_document":
        _populate_single_document_demo(window, variant or "overview")
        return

    if scenario_key == "batch":
        _populate_batch_demo(window, variant or "overview")
        return

    if scenario_key == "response":
        _populate_response_demo(window, _response_action_to_prefix(spec.action), variant or "entry")
        return

    if scenario_key == "preview":
        preview_variant = {"bundle_list": "bundle"}.get(variant, variant or "overview")
        _populate_preview_demo(window, preview_variant)
        return

    if scenario_key == "data_management":
        _populate_data_management_demo(window, variant or "overview")
        return

    if scenario_key == "official_docs":
        _populate_official_docs_demo(window, variant or "overview")
        return

    if scenario_key == "formal_review":
        _populate_formal_review_demo(window, variant or "overview")
        return

    if scenario_key == "settings":
        _populate_settings_demo(window)


def _sanitize_widget_tree(widget: QWidget, *, preserve_real_contact: bool = False) -> None:
    from PySide6.QtWidgets import QComboBox, QLabel, QLineEdit, QPlainTextEdit, QTextEdit

    for line_edit in widget.findChildren(QLineEdit) or []:
        try:
            if not line_edit.isVisible():
                continue
            text = str(line_edit.text() or "")
            if _looks_sensitive(text) and not should_preserve_real_text(text, preserve_real_contact=preserve_real_contact):
                line_edit.setText(_sanitize_text(text))
        except Exception:
            pass

    for label in widget.findChildren(QLabel) or []:
        try:
            if not label.isVisible():
                continue
            text = str(label.text() or "")
            if _looks_sensitive(text) and not should_preserve_real_text(text, preserve_real_contact=preserve_real_contact):
                label.setText(_sanitize_text(text))
        except Exception:
            pass

    for plain_text in widget.findChildren(QPlainTextEdit) or []:
        try:
            if not plain_text.isVisible():
                continue
            text = str(plain_text.toPlainText() or "")
            if _looks_sensitive(text) and not should_preserve_real_text(text, preserve_real_contact=preserve_real_contact):
                plain_text.setPlainText(_sanitize_text(text))
        except Exception:
            pass

    for text_edit in widget.findChildren(QTextEdit) or []:
        try:
            if not text_edit.isVisible():
                continue
            text = str(text_edit.toPlainText() or "")
            if _looks_sensitive(text) and not should_preserve_real_text(text, preserve_real_contact=preserve_real_contact):
                text_edit.setPlainText(_sanitize_text(text))
        except Exception:
            pass

    for combo in widget.findChildren(QComboBox) or []:
        try:
            if not combo.isVisible() or not combo.isEditable() or combo.lineEdit() is None:
                continue
            text = str(combo.currentText() or "")
            if _looks_sensitive(text) and not should_preserve_real_text(text, preserve_real_contact=preserve_real_contact):
                combo.lineEdit().setText(_sanitize_text(text))
        except Exception:
            pass


def should_preserve_real_text(text: str, *, preserve_real_contact: bool = False) -> bool:
    if not preserve_real_contact:
        return False
    content = str(text or "")
    return any(
        token in content
        for token in (
            "通官文旦-专利工具",
            "是旦不是蛋",
            "1649251313@qq.com",
            "MrEgg208",
            "公众号",
        )
    )


def _looks_sensitive(text: str) -> bool:
    content = str(text or "").strip()
    if not content:
        return False
    if ":\\" in content or content.startswith("\\\\"):
        return True
    if "@" in content:
        return True
    if re.search(r"\d{6,}", content):
        return True
    if any(keyword in content for keyword in ("许可证", "machine", "机器码", "AppData", "Users\\")):
        return True
    return False


def _sanitize_text(text: str) -> str:
    content = str(text or "")
    content = re.sub(r"[A-Za-z]:\\[^\\\n\r\t ]+", r"D:\\demo\\示例", content)
    content = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "demo@example.com", content)
    content = re.sub(r"\b1\d{10}\b", "13800000000", content)
    content = re.sub(r"\d{6,}", "******", content)
    return content


def _drain_events(app, cycles: int = 4) -> None:
    for _ in range(max(1, cycles)):
        try:
            app.processEvents()
        except Exception:
            return


def _collect_headings(lines: list[str]) -> list[tuple[int, int, str]]:
    headings: list[tuple[int, int, str]] = []
    for index, line in enumerate(lines):
        match = _HEADING_RE.match(line)
        if not match:
            continue
        headings.append((index, len(match.group("marks")), match.group("title").strip()))
    return headings


def _find_heading(headings: list[tuple[int, int, str]], title: str) -> tuple[int, int, str] | None:
    needle = str(title or "").strip()
    for item in headings:
        if item[2] == needle:
            return item
    return None


def _find_section_end(
    headings: list[tuple[int, int, str]],
    current: tuple[int, int, str],
    total_lines: int,
    level: int,
) -> int:
    current_index = headings.index(current)
    for next_heading in headings[current_index + 1 :]:
        if next_heading[1] <= level:
            return next_heading[0]
    return total_lines


def build_manual_coverage_report(
    source_markdown_path: Path | None,
    illustrations: list[ManualIllustration],
) -> dict[str, object]:
    source = Path(source_markdown_path).resolve() if source_markdown_path else None
    by_heading: dict[str, list[ManualIllustration]] = {}
    for illustration in illustrations:
        anchor = str(illustration.chapter_anchor or illustration.heading or "").strip()
        if not anchor:
            continue
        by_heading.setdefault(anchor, []).append(illustration)

    if source is None or not source.exists():
        covered = sorted(by_heading)
        return {
            "source_markdown_path": str(source) if source else "",
            "heading_count": 0,
            "covered_heading_count": len(covered),
            "missing_headings": [],
            "headings": [],
            "covered_headings": covered,
        }

    lines = source.read_text(encoding="utf-8").splitlines()
    headings = [
        {"title": title, "level": level, "line_no": line_no + 1, "shot_ids": [item.shot_id for item in by_heading.get(title, [])]}
        for line_no, level, title in _collect_headings(lines)
        if level in {3, 4}
    ]
    missing = [item["title"] for item in headings if not item["shot_ids"]]
    return {
        "source_markdown_path": str(source),
        "heading_count": len(headings),
        "covered_heading_count": len(headings) - len(missing),
        "missing_headings": missing,
        "covered_headings": [item["title"] for item in headings if item["shot_ids"]],
        "headings": headings,
    }


def _is_remote_target(target: str) -> bool:
    lowered = str(target or "").strip().lower()
    return lowered.startswith(("http://", "https://", "data:", "file://"))
