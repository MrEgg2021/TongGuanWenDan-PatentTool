from __future__ import annotations

import os

from gui.dialog_utils import ask_continue_cancel, show_blocking_alert_modal
from gui.section_resolution import normalize_enabled_sections


def _prevalidate_batch_overview(window, target_files: list[str], enabled_sections: dict) -> bool:
    requested_enabled_sections = normalize_enabled_sections(enabled_sections)
    if not any(bool(v) for v in requested_enabled_sections.values()):
        show_blocking_alert_modal(
            window,
            "提示",
            "请至少勾选一项需要生成的文书（五书/请求书）。",
            primary_text="关闭",
            secondary_text="关闭",
        )
        return False

    confirm_req = True
    try:
        confirm_req = bool(window.batch_chk_confirm_req.isChecked())
    except Exception:
        confirm_req = True

    try:
        probe_map = getattr(window, "_batch_header_probe_map", {}) or {}
    except Exception:
        probe_map = {}

    try:
        meta_map = getattr(window, "_batch_doc_meta_map", {}) or {}
    except Exception:
        meta_map = {}

    lines: list[str] = []
    missing_confirm: list[str] = []
    missing_by_section: dict[str, list[str]] = {"claims": [], "description": [], "abstract": [], "drawings": []}
    unwritable_files: list[str] = []
    protected_files: list[str] = []
    protection_check_failed: list[tuple[str, str]] = []
    any_effective_request_form = bool(requested_enabled_sections.get("request_form")) and bool(target_files)

    for file_path in target_files:
        base_name = os.path.basename(file_path)
        probe = probe_map.get(file_path)
        if isinstance(probe, dict):
            if requested_enabled_sections.get("request_form") and not bool(probe.get("request_meta")):
                missing_confirm.append(base_name)
            for section in ("claims", "description", "abstract", "drawings"):
                if requested_enabled_sections.get(section) and not bool(probe.get(section)):
                    missing_by_section[section].append(base_name)

        meta = meta_map.get(file_path)
        if not isinstance(meta, dict):
            continue
        try:
            if meta.get("source_writable") is False:
                unwritable_files.append(base_name)
        except Exception:
            pass
        try:
            if meta.get("protected") is True:
                protected_files.append(base_name)
        except Exception:
            pass
        try:
            err = meta.get("protection_check_error")
            if err:
                protection_check_failed.append((base_name, str(err)))
        except Exception:
            pass

    if missing_confirm:
        lines.append(
            f"- 已勾选“请求书”，但以下文件未检测到“申请信息确认页”页眉：{len(missing_confirm)} 个；这些文件不会被忽略，仍将进入请求书补填流程。"
        )
        lines.extend([f"  - {name}" for name in missing_confirm[:10]])
        if len(missing_confirm) > 10:
            lines.append(f"  - ... 还有 {len(missing_confirm) - 10} 个")

    section_labels = {
        "claims": "权利要求书",
        "description": "说明书",
        "abstract": "说明书摘要",
        "drawings": "说明书附图",
    }
    for section, names in missing_by_section.items():
        if not names:
            continue
        lines.append(
            f"- 已勾选“{section_labels.get(section, section)}”，但以下文件页眉检测未识别到该章节：{len(names)} 个；本次将忽略该章节，不参与转换。"
        )
        lines.extend([f"  - {name}" for name in names[:10]])
        if len(names) > 10:
            lines.append(f"  - ... 还有 {len(names) - 10} 个")

    if unwritable_files:
        lines.append(f"- 以下文件可能为只读或无写权限：{len(unwritable_files)} 个，建议复制到可写目录后再转换。")
        lines.extend([f"  - {name}" for name in unwritable_files[:10]])
        if len(unwritable_files) > 10:
            lines.append(f"  - ... 还有 {len(unwritable_files) - 10} 个")

    if protected_files:
        lines.append(f"- 以下文件处于保护/限制编辑状态：{len(protected_files)} 个，可能导致解析或处理失败，建议先取消保护。")
        lines.extend([f"  - {name}" for name in protected_files[:10]])
        if len(protected_files) > 10:
            lines.append(f"  - ... 还有 {len(protected_files) - 10} 个")

    if protection_check_failed:
        lines.append(f"- 以下文件未能检测文档保护状态：{len(protection_check_failed)} 个，建议先在 Word 中确认是否受保护。")
        for name, err in protection_check_failed[:5]:
            lines.append(f"  - {name}：{err}")
        if len(protection_check_failed) > 5:
            lines.append(f"  - ... 还有 {len(protection_check_failed) - 5} 个")

    if requested_enabled_sections.get("request_form") and not confirm_req and any_effective_request_form:
        if missing_confirm:
            lines.append("- 您未启用“使用弹窗确认请求书信息”；有确认页的文件将直接使用解析结果，缺少确认页的文件仍会强制打开请求书弹窗补填。")
        else:
            lines.append("- 您已勾选“请求书”，但未启用“使用弹窗确认请求书信息”；本次批量将直接使用解析结果，请在客户端导入后再人工核对请求书内容。")

    if not lines:
        return True

    if any_effective_request_form:
        naming_tip = (
            "\n\n命名规则预览：\n"
            "- 实际参与请求书转换的文件，其单案 ZIP 将按“发明/实用新型-专利名称”命名（重名自动追加 _2/_3）。"
        )
    else:
        naming_tip = (
            "\n\n命名规则预览：\n"
            "- 本次没有文件实际参与请求书转换，单案 ZIP 将沿用原内层 ZIP 结构或原文件名，不附加专利类型前缀。"
        )

    msg = "批量开始前校验：检测到以下需要您知晓的信息：\n\n" + "\n".join(lines) + naming_tip
    msg += "\n\n是否继续开始批量转换？"
    return ask_continue_cancel(window, "批量转换前校验", msg)


__all__ = ["_prevalidate_batch_overview"]
