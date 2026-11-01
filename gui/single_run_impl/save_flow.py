import os
import shutil
import sys
import traceback

from PySide6.QtWidgets import QFileDialog

from core.config import sanitize_filename
from core.logging_utils import logger
from gui.dialog_utils import show_blocking_alert_modal


def _resolve_collision_path(dest_path: str) -> str:
    try:
        if not dest_path:
            return dest_path
        dest_path = os.path.normpath(dest_path)
        if not os.path.exists(dest_path):
            return dest_path
        base, ext = os.path.splitext(dest_path)
        idx = 2
        while True:
            cand = f"{base}_{idx}{ext}"
            if not os.path.exists(cand):
                return cand
            idx += 1
    except Exception:
        return dest_path


def _select_zip_for_preview_from_result(result) -> str | None:
    try:
        outer_zip = result.get("outer_zip_path")
    except Exception:
        outer_zip = None
    try:
        inner_zip = result.get("inner_zip_path")
    except Exception:
        inner_zip = None

    if isinstance(outer_zip, str) and outer_zip and os.path.exists(outer_zip):
        return outer_zip
    if isinstance(inner_zip, str) and inner_zip and os.path.exists(inner_zip):
        return inner_zip
    return None


def _update_preview_zip_state(window, zip_path) -> None:
    try:
        if hasattr(window, "_last_single_zip_for_preview"):
            window._last_single_zip_for_preview = zip_path
    except Exception:
        pass


def _build_single_zip_filename(input_path: str, result, enabled_sections: dict, patent_type: str) -> str:
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    core_title = None
    try:
        core_title = result.get("invention_title")
    except Exception:
        core_title = None

    if not core_title:
        try:
            core_title = base_name or result.get("case_id") or "output"
        except Exception:
            core_title = base_name or "output"

    if isinstance(enabled_sections, dict) and enabled_sections.get("request_form", True):
        if patent_type == "utility_model":
            type_label = "实用新型"
        else:
            type_label = "发明"
        title = f"{type_label}-{core_title}"
    else:
        title = core_title

    return sanitize_filename(title) + ".zip"


def _get_output_dir_from_window(window) -> str:
    output_dir = ""
    try:
        if hasattr(window, "output_dir_edit"):
            output_dir = window.output_dir_edit.text().strip()
    except Exception:
        output_dir = ""
    return output_dir


def _build_default_save_path(window, input_path: str, safe_name: str) -> str:
    try:
        base_dir = os.path.dirname(os.path.abspath(input_path))
    except Exception:
        base_dir = ""

    if base_dir and os.path.isdir(base_dir):
        return os.path.join(base_dir, safe_name)

    last_dir = ""
    try:
        last_saved = getattr(window, "_last_single_saved_zip_path", "") or ""
        if last_saved:
            last_dir = os.path.dirname(os.path.abspath(last_saved))
    except Exception:
        last_dir = ""
    if last_dir and os.path.isdir(last_dir):
        return os.path.join(last_dir, safe_name)
    return safe_name


def save_single_zip_from_result(
    window,
    *,
    input_path: str,
    result,
    enabled_sections: dict,
    patent_type: str,
) -> tuple[bool, list[tuple[str, str]]]:
    saved_single = False
    result_items: list[tuple[str, str]] = []

    if not isinstance(result, dict) or not (result.get("outer_zip_path") or result.get("inner_zip_path")):
        result_items.append((os.path.basename(input_path), "fail"))
        return saved_single, result_items

    dest_zip_for_preview = _select_zip_for_preview_from_result(result)

    inner_zip = dest_zip_for_preview
    if not dest_zip_for_preview:
        inner_zip = None

    _update_preview_zip_state(window, inner_zip)

    safe_name = _build_single_zip_filename(input_path, result, enabled_sections, patent_type)

    dest_path = ""
    output_dir = _get_output_dir_from_window(window)

    if output_dir:
        try:
            os.makedirs(output_dir, exist_ok=True)
            dest_path = os.path.join(output_dir, safe_name)
            dest_path = _resolve_collision_path(dest_path)
        except Exception:
            dest_path = ""
            if not getattr(sys, "frozen", False):
                traceback.print_exc()
            show_blocking_alert_modal(window, "提示", f"创建输出目录失败：{output_dir}\n将改为手动选择保存位置。", primary_text="关闭", secondary_text="关闭")

    if not dest_path:
        default_path = _build_default_save_path(window, input_path, safe_name)
        dest_path, _ = QFileDialog.getSaveFileName(
            window,
            "保存案卷 ZIP",
            default_path,
            "ZIP 文件 (*.zip)",
        )

    if dest_path:
        dest_path = _resolve_collision_path(dest_path)
        try:
            shutil.copy(inner_zip, dest_path)
            saved_single = True
            result_items.append((os.path.basename(input_path), "success"))
            logger.info("[SINGLE_RUN_SAVE] status=success source=%s dest=%s", str(input_path), str(dest_path))
            try:
                setattr(window, "_last_single_saved_zip_path", dest_path)
            except Exception:
                pass
        except Exception as e:
            logger.error("[SINGLE_RUN_SAVE] status=failed source=%s dest=%s error=%s", str(input_path), str(dest_path), str(e), exc_info=True)
            if not getattr(sys, "frozen", False):
                traceback.print_exc()
            show_blocking_alert_modal(window, "提示", f"案卷 ZIP 复制失败：{e}", primary_text="关闭", secondary_text="关闭")
            result_items.append((os.path.basename(input_path), "fail"))
    else:
        saved_single = False
        logger.info("[SINGLE_RUN_SAVE] status=cancelled source=%s", str(input_path))
        result_items.append((os.path.basename(input_path), "fail"))

    return saved_single, result_items
