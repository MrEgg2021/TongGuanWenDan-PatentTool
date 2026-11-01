from __future__ import annotations

import os
import sys
import traceback

from core.conversion import ConversionCancelled, classify_conversion_error, run_conversion
from core.logging_utils import get_conversion_log_path, logger
from core.word_engine import WordComHijackedError
from gui.app_impl.image_overrides import get_effective_image_overrides
from gui.conversion_session import begin_single_run_session, release_single_run_session
from gui.dialog_utils import ask_continue_cancel, show_blocking_alert_modal
from gui.single_run_impl.postprocess_flow import postprocess_single_run
from gui.single_run_impl.preflight_flow import prepare_single_run_context
from gui.single_run_impl.save_flow import save_single_zip_from_result


def _build_single_run_error_message(exc: BaseException) -> str:
    try:
        error_code = str(getattr(exc, "conversion_error_code", "") or "").strip()
    except Exception:
        error_code = ""
    if not error_code:
        error_code = classify_conversion_error(exc)

    if error_code == "DRAWINGS_SOURCE_MEDIA_CORRUPT":
        return (
            "检测到说明书附图中的内嵌图片数据已损坏，程序无法可靠恢复完整内容。\n"
            "为避免生成缺图或黑块，本次转换已停止。请在 Word 中删除该图片，重新插入原始图片后再转换。\n"
        )

    try:
        log_path = str(get_conversion_log_path() or "").strip()
    except Exception:
        log_path = ""

    lines = ["转换未完成，请核对原始 Word 文件和 Word 环境。"]
    if log_path:
        lines.append("如问题持续，可查看程序日志了解详情。")
    else:
        lines.append("请核对原始文件并重试。")
    if log_path:
        lines.append(f"日志路径：{log_path}")
    return "\n".join(lines)


def _handle_word_com_error(window, exc: BaseException, *, input_path: str, config_path=None, in_fallback: bool) -> bool:
    message = str(exc).strip() or "无法正常连接或操作 Microsoft Word。"
    if in_fallback:
        try:
            status_label = getattr(window, "status_label", None)
            if status_label is not None:
                status_label.setText("状态：转换失败")
        except Exception:
            pass
        show_blocking_alert_modal(window, "错误", message)
        try:
            if hasattr(window, "_hide_processing_overlay"):
                window._hide_processing_overlay()
        except Exception:
            pass
        return False

    if not ask_continue_cancel(
        window,
        "Word 环境异常",
        message,
        continue_text="我已修复/重试",
        cancel_text="取消",
        default_continue=True,
    ):
        try:
            status_label = getattr(window, "status_label", None)
            if status_label is not None:
                status_label.setText("状态：已取消")
        except Exception:
            pass
        try:
            if hasattr(window, "_hide_processing_overlay"):
                window._hide_processing_overlay()
        except Exception:
            pass
        return False

    try:
        status_label = getattr(window, "status_label", None)
        if status_label is not None:
            status_label.setText("状态：正在重试")
    except Exception:
        pass
    run_single_conversion(window, input_path, config_path, _in_fallback=True)
    return True


def _update_single_header_summary(window) -> None:
    try:
        probe = getattr(window, "_last_header_probe_single", None)
    except Exception:
        probe = None
    if not isinstance(probe, dict):
        return

    mapping = [
        ("申请信息确认页", bool(probe.get("request_meta"))),
        ("权利要求书", bool(probe.get("claims"))),
        ("说明书", bool(probe.get("description"))),
        ("说明书摘要", bool(probe.get("abstract"))),
        ("说明书附图", bool(probe.get("drawings"))),
    ]
    try:
        window._header_precheck_summary = "页眉检测：" + "  ".join(f"{name}{'✓' if ok else '✗'}" for name, ok in mapping)
    except Exception:
        pass


def run_single_conversion(
    window,
    input_path: str,
    config_path=None,
    _in_fallback: bool = False,
) -> None:

    if not begin_single_run_session(window, fallback=_in_fallback):
        show_blocking_alert_modal(
            window,
            "提示",
            "当前已有单文档转换正在进行，请勿重复启动。",
            primary_text="关闭",
            secondary_text="关闭",
        )
        return


    overrides = get_effective_image_overrides(window)

    try:
        window._progress_scope = "single"
    except Exception:
        pass

    try:
        if hasattr(window, "_last_single_zip_for_preview"):
            window._last_single_zip_for_preview = None
        if hasattr(window, "_last_single_patent_type"):
            window._last_single_patent_type = None
        if hasattr(window, "_last_single_enabled_sections"):
            try:
                window._last_single_enabled_sections = window.get_enabled_sections()
            except Exception:
                window._last_single_enabled_sections = None
        if hasattr(window, "_last_single_effective_enabled_sections"):
            window._last_single_effective_enabled_sections = None
    except Exception:
        pass

    try:
        if hasattr(window, "_show_processing_overlay"):
            window._show_processing_overlay("正在预检查页眉…", os.path.basename(input_path))
    except Exception:
        pass

    try:
        window._header_precheck_stage = "步骤 1/2：检查环境"
        window._header_precheck_summary = ""
    except Exception:
        pass

    try:
        window._set_current_file_label(input_path)
    except Exception:
        pass


    try:
        window.update_progress(0, "正在预检查页眉…", "步骤 1/2：正在后台检查运行环境并清理残留 Word 进程，请稍候…")
    except Exception:
        pass

    try:
        window._header_precheck_stage = "步骤 2/2：页眉扫描"
    except Exception:
        pass
    try:
        window.update_progress(0, "正在预检查页眉…", "步骤 2/2：正在后台扫描页眉并分析章节结构与必需页眉结果，请稍候…")
    except Exception:
        pass

    try:
        try:
            if not window._check_required_headers_single(input_path, config_path=config_path):
                try:
                    if hasattr(window, "_hide_processing_overlay"):
                        window._hide_processing_overlay()
                except Exception:
                    pass
                return
        except WordComHijackedError as exc:
            if _handle_word_com_error(window, exc, input_path=input_path, config_path=config_path, in_fallback=_in_fallback):
                return
            return

        try:
            window.update_progress(0, "正在预检查页眉…", "步骤 2/2：已在后台完成页眉扫描，正在分析章节结构和必需页眉结果…")
        except Exception:
            pass

        _update_single_header_summary(window)
        try:
            window._header_precheck_stage = "预检查完成"
        except Exception:
            pass

        try:
            window.btn_run.setEnabled(False)
        except Exception:
            pass

        paused_processing_overlay_for_request_form = False
        try:
            if getattr(window, "_processing_overlay", None) and hasattr(window, "_hide_processing_overlay"):
                window._hide_processing_overlay()
                paused_processing_overlay_for_request_form = True
                logger.info("[SINGLE_RUN] processing_overlay_paused_for_request_form file=%s", str(input_path))
        except Exception:
            paused_processing_overlay_for_request_form = False

        ctx = prepare_single_run_context(window, input_path, config_path=config_path)
        if ctx is None:
            logger.info("[SINGLE_RUN] aborted_before_conversion file=%s reason=preflight_returned_none", str(input_path))
            try:
                if hasattr(window, "_hide_processing_overlay"):
                    window._hide_processing_overlay()
            except Exception:
                pass
            return

        requested_enabled_sections = ctx.requested_enabled_sections
        effective_enabled_sections = ctx.effective_enabled_sections
        confirmed_request_info = ctx.confirmed_request_info
        patent_type = ctx.effective_patent_type or ctx.patent_type
        desc_split_mode = ctx.desc_split_mode

        try:
            window._last_single_patent_type = patent_type
            window._last_single_enabled_sections = requested_enabled_sections
            window._last_single_effective_enabled_sections = effective_enabled_sections
            window._set_current_file_label(input_path)
        except Exception:
            pass

        if paused_processing_overlay_for_request_form:
            try:
                if hasattr(window, "_show_processing_overlay"):
                    window._show_processing_overlay("正在准备转换...", os.path.basename(input_path))
                    logger.info("[SINGLE_RUN] processing_overlay_resumed_after_request_form file=%s", str(input_path))
            except Exception:
                pass

        window.update_progress(0, "正在准备转换...", "页眉检测完成，正在准备后台转换...")
        window.update_progress(1, "正在启动转换...", "正在后台启动 Word 并加载配置...")

        try:
            if hasattr(window, "_reset_cancel_state"):
                window._reset_cancel_state()
            else:
                window._cancel_requested = False
        except Exception:
            pass


        result = run_conversion(
            input_path,
            config_path=config_path,
            progress_callback=window._progress_callback,
            optimize_equation_centering=(
                bool(window.get_optimize_equation_centering_enabled())
                if hasattr(window, "get_optimize_equation_centering_enabled")
                else False
            ),
            optimize_table_image_centering=bool(getattr(window, "_opt_table_img_center_enabled", True)),
            patent_type=patent_type,
            request_info=confirmed_request_info,
            enabled_sections=effective_enabled_sections,
            description_paragraph_split_mode=desc_split_mode,
            image_processing_overrides=overrides,
        )

        window.update_progress(100, "转换完成", "转换流程已结束，准备保存案卷 ZIP。")
        window._has_run_conversion = True
        try:
            window._set_current_file_label(input_path)
        except Exception:
            pass

        saved_single = False
        result_items: list[tuple[str, str]] = []
        if isinstance(result, dict) and (result.get("outer_zip_path") or result.get("inner_zip_path")):
            saved_single, result_items = save_single_zip_from_result(
                window,
                input_path=input_path,
                result=result,
                enabled_sections=effective_enabled_sections,
                patent_type=patent_type,
            )
        else:
            result_items.append((os.path.basename(input_path), "fail"))

        postprocess_single_run(window, result=result, result_items=result_items, saved_single=saved_single)

    except WordComHijackedError as exc:
        if _handle_word_com_error(window, exc, input_path=input_path, config_path=config_path, in_fallback=_in_fallback):
            return
        return

    except ConversionCancelled:
        try:
            status_label = getattr(window, "status_label", None)
            if status_label is not None:
                status_label.setText("状态：已取消")
        except Exception:
            pass
        try:
            if hasattr(window, "_hide_processing_overlay"):
                window._hide_processing_overlay()
        except Exception:
            pass
        return

    except Exception as exc:
        try:
            status_label = getattr(window, "status_label", None)
            if status_label is not None:
                status_label.setText("状态：转换失败")
        except Exception:
            pass
        try:
            error_code = str(getattr(exc, "conversion_error_code", "") or "").strip() or classify_conversion_error(exc)
        except Exception:
            error_code = "UNEXPECTED_ERROR"
        logger.error("[SINGLE_RUN_ERROR] code=%s file=%s", error_code, str(input_path), exc_info=True)
        if not getattr(sys, "frozen", False):
            traceback.print_exc()
        show_blocking_alert_modal(window, "错误", _build_single_run_error_message(exc))

    finally:
        release_single_run_session(window)
