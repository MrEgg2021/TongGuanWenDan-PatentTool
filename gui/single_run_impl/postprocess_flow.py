import os
import sys

from core.runtime import cleanup_runtime_artifacts
from gui.dialog_utils import show_blocking_alert_modal
from gui.tools_ui import preview_single_case


def _maybe_alert_table_screenshot_failures(window, result) -> None:
    table_failures = []
    if isinstance(result, dict):
        table_failures = result.get("table_screenshot_failures") or []
    if not table_failures:
        return

    section_map = {
        "claims": "权利要求书",
        "description": "说明书",
        "drawings": "说明书附图",
        "abstract": "说明书摘要",
    }
    lines = [
        "检测到部分表格未能自动转换，请人工复查：",
        "",
    ]
    for f in table_failures[:10]:
        sec_key = f.get("section")
        sec_cn = section_map.get(sec_key, sec_key or "")
        para_idx = f.get("paragraph_index")
        desc_num = f.get("desc_para_num")
        claim_num = f.get("claim_num")
        if sec_key == "description" and desc_num:
            pos_text = f"说明书第 {desc_num} 段附近的表格"
        elif sec_key == "claims" and claim_num:
            pos_text = f"权利要求 {claim_num} 中的表格"
        else:
            pos_text = f"{sec_cn or '未知章节'}：第 {para_idx} 段附近的表格"
        lines.append(f"- {pos_text}")
    if len(table_failures) > 10:
        lines.append(f"... 还有 {len(table_failures) - 10} 个表格未列出")
    show_blocking_alert_modal(
        window,
        "提示",
        "\n".join(lines),
        primary_text="关闭",
        secondary_text="关闭",
        close_result="secondary",
    )


def _maybe_alert_drawings_label_report(window, result) -> None:
    drawings_report = None
    if isinstance(result, dict):
        drawings_report = result.get("drawings_label_report")
    if not isinstance(drawings_report, dict):
        return

    img_count = drawings_report.get("img_count")
    label_line_count = drawings_report.get("label_line_count")
    count_mismatch = bool(drawings_report.get("count_mismatch"))
    missing_count = int(drawings_report.get("missing_count") or 0)
    duplicate_labels = drawings_report.get("duplicate_labels") or []
    unused_labels = drawings_report.get("unused_labels") or []
    if not (count_mismatch or missing_count > 0 or duplicate_labels):
        return

    lines = [
        "检测到说明书附图图号需要人工复查（本工具按“清洗后每一行有效图号=一个附图标签，按序号对应附图”处理）：",
        "",
        f"- 附图图片数量：{img_count}",
        f"- 图号行数量：{label_line_count}",
    ]
    if missing_count > 0:
        lines.append(f"- 图号缺失（已写入“图号缺失”）：{missing_count} 张")
    if duplicate_labels:
        try:
            dup_preview = "、".join([str(x) for x in duplicate_labels[:10] if str(x).strip()])
        except Exception:
            dup_preview = ""
        lines.append(f"- 图号重复：{len(duplicate_labels)} 种")
        if dup_preview:
            lines.append(f"  重复样例：{dup_preview}")
    if unused_labels:
        lines.append(f"- 多余图号行（已忽略）：{len(unused_labels)} 行")
    show_blocking_alert_modal(
        window,
        "提示",
        "\n".join(lines),
        primary_text="关闭",
        secondary_text="关闭",
        close_result="secondary",
    )


def _show_single_result_overlay(window, result_items, result=None) -> None:
    try:
        total = 1
        success = 1 if any(status == "success" for _, status in (result_items or [])) else 0
        failed = total - success
        notice_text = _build_single_fallback_notice(window, result)
        window._show_result_overlay(
            result_items or [],
            total,
            success,
            failed,
            notice_text=notice_text,
        )
    except Exception:
        pass


def _build_single_fallback_notice(window, result=None) -> str | None:
    _ = window
    fallback_items = []
    if isinstance(result, dict):
        fallback_items = result.get("object_fallback_failures") or []
    if not fallback_items:
        return None

    section_map = {
        "claims": "权利要求书",
        "description": "说明书",
        "drawings": "说明书附图",
        "abstract": "说明书摘要",
    }
    section_names = []
    for item in fallback_items:
        if not isinstance(item, dict):
            continue
        section = section_map.get(str(item.get("section") or "").strip(), "")
        if section and section not in section_names:
            section_names.append(section)

    sections_text = "、".join(section_names) if section_names else "正文"
    return (
        f"部分外部对象未能完整转换：共 {len(fallback_items)} 处，涉及 {sections_text}。"
        "相关对象已改用静态图片或占位图片，请核对内容，必要时补充原始内容后重新转换。"
    )


def _maybe_auto_open_single_preview(window, saved_single: bool) -> None:
    try:
        auto_open = False
        try:
            if hasattr(window, "chk_auto_open_preview"):
                auto_open = bool(window.chk_auto_open_preview.isChecked())
        except Exception:
            auto_open = False

        if saved_single and auto_open:
            try:
                zip_for_preview = getattr(window, "_last_single_saved_zip_path", None) or ""
            except Exception:
                zip_for_preview = ""
            if zip_for_preview and os.path.isfile(str(zip_for_preview)):
                preview_single_case(window, str(zip_for_preview))
    except Exception:
        pass


def postprocess_single_run(window, *, result, result_items, saved_single: bool) -> None:
    _maybe_alert_table_screenshot_failures(window, result)
    _maybe_alert_drawings_label_report(window, result)
    _show_single_result_overlay(window, result_items, result)
    _maybe_auto_open_single_preview(window, saved_single)

    if getattr(sys, "frozen", False):
        try:
            cleanup_runtime_artifacts(result)
        except Exception:
            pass
