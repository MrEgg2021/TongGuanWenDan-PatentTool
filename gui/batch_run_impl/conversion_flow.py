import os
import shutil
import sys
import traceback


from gui.dialog_utils import ask_continue_cancel
from core.conversion import run_conversion
from core.conversion import ConversionCancelled
from core.config import sanitize_filename
from core.word_engine import WordComHijackedError

from .utils import _increment_case_number, _repack_case_zip_with_root


def execute_conversion_flow(
    window,
    target_files: list[str],
    *,
    config_path=None,
    enabled_sections: dict,
    per_file_settings: dict[str, dict],
    case_number: str | None,
    temp_batch_dir: str,
    image_processing_overrides: dict | None = None,
) -> tuple[list[tuple[str, str]], int, int, list[str], list[tuple[str, int]], str | None, list[tuple[str, str]]]:
    # 第二阶段：正式逐个执行转换
    used_arc_names = set()

    individual_zips: list[tuple[str, str]] = []
    success_count = 0
    fail_count = 0
    error_messages: list[str] = []
    result_items: list[tuple[str, str]] = []  # (filename, status)
    # 记录每个文件内表格截图失败的数量，用于批量结束时提示人工复查
    table_warn_files: list[tuple[str, int]] = []  # [(basename, failure_count), ...]
    drawings_warn_files: list[tuple[str, str]] = []  # [(basename, summary), ...]
    object_fallback_warn_files: list[tuple[str, int, str]] = []  # [(basename, count, kind_summary), ...]

    total_files = len(target_files)

    desc_split_mode = None
    try:
        if hasattr(window, "get_description_paragraph_split_mode"):
            desc_split_mode = window.get_description_paragraph_split_mode()
    except Exception:
        desc_split_mode = None

    for idx, file_path in enumerate(target_files):
        window._batch_current_index = idx + 1

        # 批量统计行仅展示当前进度与累计成功/失败数量
        batch_info_text = f"第 {window._batch_current_index}/{total_files} 个文件 | 成功：{success_count} | 失败：{fail_count}"

        window._clear_system_clipboard_safely()
        base_name = os.path.basename(file_path)

        window._set_current_file_label(file_path)
        window.update_progress(
            0,
            "正在处理...",
            "正在准备处理当前文件...",
            batch_info=batch_info_text,
        )

        def batch_progress(stage, payload, file_index=window._batch_current_index):
            window._batch_current_index = file_index
            window._progress_callback(stage, payload)

        error_short = None

        try:
            settings = per_file_settings.get(file_path) or {}
            patent_type = settings.get("effective_patent_type") or settings.get("patent_type", "invention")
            confirmed_request_info = settings.get("request_info")
            file_enabled_sections = settings.get("effective_enabled_sections") or enabled_sections

            result = run_conversion(
                file_path,
                config_path=config_path,
                progress_callback=batch_progress,
                optimize_equation_centering=bool(window.get_optimize_equation_centering_enabled()) if hasattr(window, "get_optimize_equation_centering_enabled") else False,
                optimize_table_image_centering=bool(getattr(window, "_opt_table_img_center_enabled", True)),
                case_id=case_number,
                patent_type=patent_type,
                request_info=confirmed_request_info,
                enabled_sections=file_enabled_sections,
                description_paragraph_split_mode=desc_split_mode,
                image_processing_overrides=image_processing_overrides,
            )
            if isinstance(result, dict):
                result["source_path"] = file_path
            if isinstance(result, dict) and result.get("inner_zip_path"):
                # 统计本文件内部表格截图失败数量（仅用于提示，不影响成功/失败计数）
                table_failures = result.get("table_screenshot_failures") or []
                if table_failures:
                    table_warn_files.append((base_name, len(table_failures)))

                object_fallbacks = result.get("object_fallback_failures") or []
                if object_fallbacks:
                    kind_counts = {}
                    for item in object_fallbacks:
                        if not isinstance(item, dict):
                            continue
                        kind = str(item.get("object_kind") or "external_object").strip() or "external_object"
                        kind_counts[kind] = int(kind_counts.get(kind, 0) or 0) + 1
                    kind_parts = []
                    for kind, count in kind_counts.items():
                        if count <= 1:
                            kind_parts.append(kind)
                        else:
                            kind_parts.append(f"{kind} x{count}")
                    kind_summary = "、".join(kind_parts) if kind_parts else "external_object"
                    object_fallback_warn_files.append((base_name, len(object_fallbacks), kind_summary))

                # 统计本文件“说明书附图图号格式不规范”的摘要
                try:
                    dr = result.get("drawings_label_report") if isinstance(result, dict) else None
                except Exception:
                    dr = None
                if isinstance(dr, dict):
                    try:
                        count_mismatch = bool(dr.get("count_mismatch"))
                        missing_count = int(dr.get("missing_count") or 0)
                        dup = dr.get("duplicate_labels") or []
                        img_cnt = dr.get("img_count")
                        line_cnt = dr.get("label_line_count")
                        if count_mismatch or missing_count > 0 or dup:
                            summary = f"图片={img_cnt}, 图号行={line_cnt}"
                            if missing_count > 0:
                                summary += f", 缺失={missing_count}"
                            if dup:
                                try:
                                    summary += f", 重复={len(dup)}"
                                except Exception:
                                    summary += ", 重复=1"
                            drawings_warn_files.append((base_name, summary))
                    except Exception:
                        pass

                src_zip = result["inner_zip_path"]
                if os.path.exists(src_zip):
                    core_title = (
                        result.get("invention_title")
                        or (settings.get("request_info") or {}).get("title")
                        or os.path.splitext(base_name)[0]
                        or result.get("case_id")
                        or "output"
                    )

                    if isinstance(file_enabled_sections, dict) and file_enabled_sections.get("request_form", True):
                        type_label = "实用新型" if patent_type == "utility_model" else "发明"
                        display_title = f"{type_label}-{core_title}"
                    else:
                        display_title = core_title

                    display_base = sanitize_filename(display_title) or "output"
                    display_name = display_base
                    counter = 1
                    while display_name in used_arc_names:
                        counter += 1
                        display_name = f"{display_base}_{counter}"
                    used_arc_names.add(display_name)

                    arc_name = display_name + ".zip"
                    temp_zip_path = os.path.join(temp_batch_dir, arc_name)

                    # 当勾选请求书时，保持“ZIP 名 == 顶层目录名”；未勾选请求书时直接复用原内层 ZIP 结构，避免多包一层
                    if isinstance(file_enabled_sections, dict) and file_enabled_sections.get("request_form", True):
                        case_id_in_result = ""
                        try:
                            if isinstance(result, dict) and result.get("case_id"):
                                case_id_in_result = str(result.get("case_id") or "")
                        except Exception:
                            case_id_in_result = ""

                        _repack_case_zip_with_root(src_zip, temp_zip_path, display_name, case_id_in_result)
                    else:
                        shutil.copy(src_zip, temp_zip_path)

                    individual_zips.append((temp_zip_path, arc_name))
                    success_count += 1
                    result_items.append((base_name, "success"))
                else:
                    fail_count += 1
                    result_items.append((base_name, "fail"))
            else:
                fail_count += 1
                result_items.append((base_name, "fail"))
        except ConversionCancelled:
            window.update_progress(
                0,
                "批量处理已取消",
                f"用户取消：{os.path.basename(file_path)}",
                batch_info=f"❌ 批量已取消：{os.path.basename(file_path)}",
            )
            raise
        except WordComHijackedError:
            fail_count += 1
            error_short = "Word 环境异常，请检查 Word/WPS 状态后重试"
            error_messages.append(f"{os.path.basename(file_path)}: {error_short}")
            result_items.append((base_name, "fail"))
            if case_number is not None:
                case_number = _increment_case_number(case_number)
        except Exception:  # 单个文件异常不中断整个批量
            fail_count += 1
            error_short = "转换失败，请人工复查"
            error_messages.append(f"{os.path.basename(file_path)}: {error_short}")
            result_items.append((base_name, "fail"))
            if not getattr(sys, "frozen", False):
                traceback.print_exc()
            if case_number is not None:
                case_number = _increment_case_number(case_number)

        if error_short is not None:
            base_name = os.path.basename(file_path)
            short = f"{base_name}：{error_short}"
            window.update_progress(
                0,
                "当前文件处理失败",
                short,
                batch_info=f"❌ 当前文件失败：{short}",
            )
            if not ask_continue_cancel(
                window,
                "批量处理出错",
                f"在批量处理中，文件：\n{base_name}\n\n发生错误：\n{error_short}\n\n是否继续处理剩余文件？",
            ):
                window.update_progress(
                    0,
                    "批量处理已终止",
                    short,
                    batch_info=f"❌ 批量处理中断：{short}",
                )
                break

    try:
        window._batch_drawings_warn_files = drawings_warn_files
    except Exception:
        pass
    try:
        window._batch_object_fallback_warn_files = object_fallback_warn_files
    except Exception:
        pass

    return individual_zips, success_count, fail_count, error_messages, table_warn_files, case_number, result_items


__all__ = ["execute_conversion_flow"]
