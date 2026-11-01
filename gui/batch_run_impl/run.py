import os
import shutil
import sys
import tempfile
import traceback

from core.config import sanitize_filename
from core.conversion import ConversionCancelled
from core.word_engine import WordComHijackedError
from gui.app_impl.image_overrides import get_effective_image_overrides
from gui.conversion_session import release_batch_run_session
from gui.dialog_utils import ask_continue_cancel, show_blocking_alert_modal

from .conversion_flow import execute_conversion_flow
from .finalize_flow import finalize_batch_zip
from .prevalidate import _prevalidate_batch_overview
from .request_form_flow import collect_request_form_settings
from .stage_precheck import precheck_headers


def run_batch_conversion(window, config_path=None, _in_fallback: bool = False) -> None:
    """执行批量转换。"""


    try:
        window._progress_scope = "batch"
    except Exception:
        pass

    target_files = window._get_batch_checked_files()
    if not target_files:
        show_blocking_alert_modal(
            window,
            "提示",
            "当前未勾选任何待处理文件，请至少勾选一个文件后再开始批量转换。",
            primary_text="关闭",
            secondary_text="关闭",
        )
        return

    try:
        batch_zip_name_raw = window.batch_zip_name_edit.text().strip()
    except Exception:
        batch_zip_name_raw = ""
    if not batch_zip_name_raw:
        show_blocking_alert_modal(window, "提示", "请输入批量案卷包的文件名。", primary_text="关闭", secondary_text="关闭")
        return

    safe_base = sanitize_filename(batch_zip_name_raw) or "batch_output"
    batch_zip_filename = safe_base if safe_base.lower().endswith(".zip") else (safe_base + ".zip")
    try:
        window._last_batch_zip_filename = batch_zip_filename
    except Exception:
        pass

    try:
        case_number = str(window.generate_case_number())
    except Exception:
        case_number = None

    try:
        if hasattr(window, "_batch_file_types"):
            window._batch_file_types.clear()
        if hasattr(window, "_batch_header_probe_map"):
            window._batch_header_probe_map.clear()
        if hasattr(window, "_batch_doc_meta_map"):
            window._batch_doc_meta_map.clear()
        if hasattr(window, "_batch_header_empty_files"):
            window._batch_header_empty_files.clear()
        if hasattr(window, "_batch_drawings_warn_files"):
            window._batch_drawings_warn_files.clear()
        if hasattr(window, "_last_batch_enabled_sections"):
            window._last_batch_enabled_sections = None
        if hasattr(window, "_batch_effective_enabled_sections_map"):
            window._batch_effective_enabled_sections_map.clear()
    except Exception:
        pass

    try:
        try:
            if hasattr(window, "_reset_cancel_state"):
                window._reset_cancel_state()
            else:
                window._cancel_requested = False
        except Exception:
            pass

        try:
            if hasattr(window, "_show_processing_overlay"):
                try:
                    window._last_batch_enabled_sections = window.get_enabled_sections()
                except Exception:
                    window._last_batch_enabled_sections = None
                window._show_processing_overlay("正在预检查页眉...", "")
        except Exception:
            pass

        try:
            status = precheck_headers(window, target_files, config_path=config_path, _in_fallback=_in_fallback)
        finally:
            try:
                if hasattr(window, "_hide_processing_overlay"):
                    window._hide_processing_overlay()
            except Exception:
                pass

        if status == "cancel":
            return
        if status == "retry":
            run_batch_conversion(window, config_path=config_path, _in_fallback=True)
            return

        try:
            enabled_sections_preview = window.get_enabled_sections()
        except Exception:
            enabled_sections_preview = {
                "claims": True,
                "description": True,
                "drawings": True,
                "abstract": True,
                "request_form": True,
            }

        if not _prevalidate_batch_overview(window, target_files, enabled_sections_preview):
            return

        try:
            enabled_sections = window.get_enabled_sections()
        except Exception:
            enabled_sections = {
                "claims": True,
                "description": True,
                "drawings": True,
                "abstract": True,
                "request_form": True,
            }

        try:
            window._last_batch_enabled_sections = enabled_sections
        except Exception:
            pass

        window.btn_run.setEnabled(False)
        total_files = len(target_files)
        window._batch_total_files = total_files
        window._batch_current_index = 0
        window.update_progress(0, "正在准备批量处理...", f"共 {total_files} 个文件")

        temp_batch_dir = tempfile.mkdtemp(prefix="batch_")

        per_file_settings = collect_request_form_settings(window, target_files, config_path, enabled_sections)
        if per_file_settings is None:
            window.btn_run.setEnabled(True)
            return

        overrides = get_effective_image_overrides(window)

        try:
            if hasattr(window, "_reset_cancel_state"):
                window._reset_cancel_state()
            else:
                window._cancel_requested = False
        except Exception:
            pass

        try:
            if hasattr(window, "_show_processing_overlay"):
                window._show_processing_overlay("正在批量处理...", "")
        except Exception:
            pass

        try:
            (
                individual_zips,
                success_count,
                fail_count,
                error_messages,
                table_warn_files,
                case_number,
                result_items,
            ) = execute_conversion_flow(
                window,
                target_files,
                config_path=config_path,
                enabled_sections=enabled_sections,
                per_file_settings=per_file_settings,
                case_number=case_number,
                temp_batch_dir=temp_batch_dir,
                image_processing_overrides=overrides,
            )
        finally:
            try:
                if hasattr(window, "_hide_processing_overlay"):
                    window._hide_processing_overlay()
            except Exception:
                pass

        finalize_batch_zip(
            window,
            batch_zip_filename=batch_zip_filename,
            individual_zips=individual_zips,
            enabled_sections=enabled_sections,
            success_count=success_count,
            fail_count=fail_count,
            error_messages=error_messages,
            table_warn_files=table_warn_files,
            result_items=result_items,
        )

    except WordComHijackedError as e:
        if _in_fallback:
            lbl_status = getattr(window, "status_label", None)
            if lbl_status is not None:
                try:
                    lbl_status.setText("状态：批量处理失败")
                except Exception:
                    pass
            show_blocking_alert_modal(window, "错误", str(e), primary_text="关闭", secondary_text="关闭")
            return

        msg = str(e).strip() or "无法正常连接或操作 Microsoft Word。"
        if not ask_continue_cancel(
            window,
            "Word 环境异常",
            msg,
            continue_text="我已修改/重试",
            cancel_text="取消",
            default_continue=True,
        ):
            lbl_status = getattr(window, "status_label", None)
            if lbl_status is not None:
                try:
                    lbl_status.setText("状态：已取消")
                except Exception:
                    pass
            return

        lbl_status = getattr(window, "status_label", None)
        if lbl_status is not None:
            try:
                lbl_status.setText("状态：正在重试")
            except Exception:
                pass
        run_batch_conversion(window, config_path=config_path, _in_fallback=True)
        return

    except ConversionCancelled:
        try:
            lbl_status = getattr(window, "status_label", None)
            if lbl_status is not None:
                try:
                    lbl_status.setText("状态：已取消")
                except Exception:
                    pass
        except Exception:
            pass
        try:
            if hasattr(window, "_hide_processing_overlay"):
                window._hide_processing_overlay()
        except Exception:
            pass
        return

    except Exception as e:
        lbl_status = getattr(window, "status_label", None)
        if lbl_status is not None:
            try:
                lbl_status.setText("状态：批量处理失败")
            except Exception:
                pass
        if not getattr(sys, "frozen", False):
            traceback.print_exc()
        show_blocking_alert_modal(window, "错误", f"批量处理过程中发生错误：{str(e)}", primary_text="关闭", secondary_text="关闭")

    finally:
        try:
            if "temp_batch_dir" in locals() and os.path.exists(temp_batch_dir):
                shutil.rmtree(temp_batch_dir)
        except Exception:
            pass
        release_batch_run_session(window)


__all__ = ["run_batch_conversion"]
