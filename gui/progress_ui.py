from __future__ import annotations

import os
import re
from typing import Optional

from gui.windowing import ui_pump as ui_pump_api

try:
    from core.conversion import ConversionCancelled
except Exception:
    class ConversionCancelled(Exception):
        pass


def _build_step_format(primary_text: Optional[str], detail_text: Optional[str]) -> Optional[str]:
    detail = (detail_text or "").strip()
    primary = (primary_text or "").strip()

    if detail:
        m = re.match(r"^(步骤\s*(\d+)\s*/\s*(\d+)\s*[:：])\s*(.*)$", detail)
        if m:
            step_prefix = f"步骤 {m.group(2)}/{m.group(3)}："
            rest = (m.group(4) or "").strip()
            if "检查运行环境" in rest or "清理残留" in rest:
                rest = "检查环境"
            elif "页眉扫描" in rest:
                rest = "页眉扫描"
            else:
                rest = re.split(r"[，。]", rest)[0].strip()
            if rest:
                return f"{step_prefix}{rest} | %p%"
            return f"{step_prefix} | %p%"

    if not primary:
        return None

    step_num: Optional[int] = None
    step_name: str = ""
    if "准备转换环境" in primary:
        step_num = 1
        step_name = "准备环境"
    elif "加载文档" in primary:
        step_num = 2
        step_name = "加载文档"
    elif any(key in primary for key in ["已识别章节结构", "正在处理正文", "正在处理第"]):
        step_num = 3
        step_name = "遍历段落"
    elif "正在生成" in primary:
        step_num = 4
        step_name = "生成打包"
    elif "转换完成" in primary:
        step_num = 5
        step_name = "完成"

    if step_num is None:
        return None

    return f"步骤 {step_num}/5：{step_name} | %p%"


def update_progress_ui(
    window,
    percent: int,
    primary_text: Optional[str] = None,
    detail_text: Optional[str] = None,
    batch_info: Optional[str] = None,
) -> None:
    """更新底部三行状态区域（独立于 MainWindow 的实现）。"""
    scope = "single"
    try:
        raw_scope = getattr(window, "_progress_scope", None)
        if isinstance(raw_scope, str) and raw_scope.strip():
            scope = raw_scope.strip()
        else:
            mode = getattr(window, "_processing_mode", "single")
            if mode in ("single", "batch", "preview"):
                scope = mode
    except Exception:
        scope = "single"

    try:
        percent = max(0, min(100, int(percent)))
    except Exception:
        percent = 0

    try:
        if (not hasattr(window, "_progress_state")) or (not isinstance(getattr(window, "_progress_state", None), dict)):
            window._progress_state = {}
        window._progress_state[scope] = {
            "percent": percent,
            "primary_text": primary_text,
            "detail_text": detail_text,
            "batch_info": batch_info,
        }
    except Exception:
        pass

    bar = getattr(window, "progress_bar", None)
    if bar is not None:
        try:
            bar.setValue(percent)
        except Exception:
            pass
        try:
            fmt = _build_step_format(primary_text, detail_text)
            bar.setFormat(fmt or "%p%")
        except Exception:
            pass

    if detail_text is not None:
        lbl_detail = getattr(window, "detail_label", None)
        if lbl_detail is not None:
            try:
                lbl_detail.setText(detail_text)
            except Exception:
                pass

    # 批量模式下，自动在主状态前加“正在处理 (X/Y)”
    primary_display = primary_text or ""
    if scope == "batch" and getattr(window, "_batch_total_files", 0) > 0:
        idx = max(1, getattr(window, "_batch_current_index", 1))
        total = max(1, getattr(window, "_batch_total_files", 1))
        prefix = f"正在处理 ({idx}/{total})"
        if primary_display:
            primary_display = f"{prefix} - {primary_display}"
        else:
            primary_display = prefix

    if not primary_display:
        primary_display = ""

    # 批量处理汇总信息行 / 页眉检测结果
    if batch_info is not None:
        lbl_batch = getattr(window, "batch_status_label", None)
        if lbl_batch is not None:
            try:
                lbl_batch.setText(batch_info)
                lbl_batch.setVisible(True)
            except Exception:
                pass

    # 根据内容粗略判断是否属于错误/中断状态，以切换红色样式
    is_error_state = False
    text_for_check = (primary_display or "") + " " + (batch_info or "")

    # 1) 明确错误：中断 / 出错 / ❌ 前缀
    if any(key in text_for_check for key in ["中断", "出错"]):
        is_error_state = True
    if batch_info and batch_info.strip().startswith("❌"):
        is_error_state = True

    # 2) “失败”需要更精确：
    # - 批量汇总行可能包含 “失败：0”，此时不应变红
    # - 当前文件失败等文案不带数字，仍视为错误
    if not is_error_state and "失败" in text_for_check:
        failed_num = None
        try:
            import re

            m = re.search(r"失败\s*[:：]\s*(\d+)", text_for_check)
            if m:
                failed_num = int(m.group(1))
        except Exception:
            failed_num = None

        if failed_num is None:
            is_error_state = True
        elif failed_num > 0:
            is_error_state = True

    if hasattr(window, "_detail_label_style_normal"):
        lbl_detail = getattr(window, "detail_label", None)
        if lbl_detail is not None:
            try:
                lbl_detail.setStyleSheet(
                    window._detail_label_style_error
                    if is_error_state
                    else window._detail_label_style_normal
                )
            except Exception:
                pass
    if hasattr(window, "_batch_status_style_normal"):
        lbl_batch = getattr(window, "batch_status_label", None)
        if lbl_batch is not None:
            try:
                lbl_batch.setStyleSheet(
                    window._batch_status_style_error
                    if is_error_state
                    else window._batch_status_style_normal
                )
            except Exception:
                pass

    # 根据进度更新状态图标
    if percent == 0:
        lbl_status = getattr(window, "status_label", None)
        if lbl_status is not None:
            try:
                lbl_status.setText("状态：" + primary_display)
            except Exception:
                pass
    elif percent < 100:
        lbl_status = getattr(window, "status_label", None)
        if lbl_status is not None:
            try:
                lbl_status.setText("状态：" + primary_display)
            except Exception:
                pass
    else:
        lbl_status = getattr(window, "status_label", None)
        if lbl_status is not None:
            try:
                lbl_status.setText("状态：" + primary_display)
            except Exception:
                pass

    try:
        if hasattr(window, "_update_processing_overlay"):
            overlay_primary = primary_display
            overlay_detail = detail_text
            overlay_batch_info = batch_info

            try:
                if scope == "preview" and bool(getattr(window, "_overlay_preview_zip_only", False)):
                    zp = str(getattr(window, "_preview_last_zip_path", "") or "").strip()
                    if zp:
                        overlay_detail = os.path.basename(zp)
                    else:
                        overlay_detail = ""
                    overlay_batch_info = None
                    window._update_processing_overlay(percent, overlay_primary, overlay_detail, overlay_batch_info)
                    ui_pump_api.pump(allow_user_input=True)
                    try:
                        if bool(getattr(window, "_cancel_requested", False)):
                            raise ConversionCancelled()
                    except ConversionCancelled:
                        raise
                    except Exception:
                        pass
                    return
            except ConversionCancelled:
                raise
            except Exception:
                pass

            file_line = ""
            try:
                file_line = str(getattr(window, "_current_file_display_text", "") or "").strip()
            except Exception:
                file_line = ""
            if not file_line:
                try:
                    if hasattr(window, "current_file_label"):
                        lbl = window.current_file_label
                        if hasattr(lbl, "fullText"):
                            file_line = str(lbl.fullText() or "").strip()
                        else:
                            file_line = str(lbl.text() or "").strip()
                except Exception:
                    file_line = ""

            file_name = ""
            try:
                t = (file_line or "").strip()
                if t.startswith("当前文件："):
                    t = t[len("当前文件：") :].strip()
                if "｜" in t:
                    t = t.split("｜", 1)[0].strip()
                if "|" in t:
                    t = t.split("|", 1)[0].strip()
                file_name = t
            except Exception:
                file_name = ""

            if not file_name:
                try:
                    p = str(getattr(window, "_current_file_path", "") or "").strip()
                    if p:
                        file_name = os.path.basename(p)
                except Exception:
                    file_name = ""

            detail_part = (detail_text or "").strip()
            file_part = f"文件：{file_name}" if file_name else ""

            detail_has_filename = False
            try:
                d = (detail_part or "").lower()
                if d and any(ext in d for ext in [".zip", ".docx", ".doc", ".pdf"]):
                    detail_has_filename = True
            except Exception:
                detail_has_filename = False

            try:
                if file_name and detail_part and file_name in detail_part:
                    detail_has_filename = True
            except Exception:
                pass

            if detail_has_filename:
                file_part = ""

            if detail_part and file_part:
                overlay_detail = f"{detail_part} | {file_part}"
            elif detail_part:
                overlay_detail = detail_part
            else:
                overlay_detail = file_part

            if scope == "batch":
                overlay_batch_info = None
            window._update_processing_overlay(percent, overlay_primary, overlay_detail, overlay_batch_info)
    except Exception:
        pass

    # 立即刷新 UI，避免长任务下界面卡死
    ui_pump_api.pump(allow_user_input=True)

    try:
        if bool(getattr(window, "_cancel_requested", False)):
            raise ConversionCancelled()
    except ConversionCancelled:
        raise
    except Exception:
        pass


def progress_callback(window, stage: str, payload: dict) -> None:
    """供后端调用的进度回调，将阶段事件映射为百分比和文案。"""
    # 基础默认值
    percent = 0
    primary: Optional[str] = None
    detail: Optional[str] = None

    if stage == "init_load_config":
        percent = 1
        primary = "正在准备转换环境..."
        detail = payload.get("message") or "正在后台加载配置文件..."
    elif stage == "init_modules":
        percent = 2
        primary = "正在准备转换环境..."
        detail = (
            payload.get("message")
            or "正在准备图片和公式转换..."
        )
    elif stage == "init_start_word":
        percent = 3
        primary = "正在准备转换环境..."
        detail = payload.get("message") or "正在后台启动 Word 应用并准备文档环境..."
    elif stage == "start":
        percent = 5
        primary = "正在加载文档..."
        detail = payload.get("message") or "正在后台打开 DOC/DOCX 文件..."
    elif stage == "section_plan_ready":
        percent = 10
        primary = "已识别章节结构"
        detail = (
            payload.get("message")
            or "已识别文档章节，正在准备处理正文。"
        )
    elif stage == "scan_ready":
        percent = 12
        total = payload.get("total_paragraphs")
        primary = "正在处理正文"
        if total:
            detail = f"文档共有 {total} 个段落，开始逐段处理..."
    elif stage == "paragraph":
        # 主进度区间：10%~80%
        idx = payload.get("index") or 0
        total = payload.get("total") or 1
        try:
            progress_ratio = max(0.0, min(1.0, float(idx) / float(total)))
        except Exception:
            progress_ratio = 0.0
        percent = int(10 + progress_ratio * 70)
        section_key = payload.get("section") or ""
        primary = f"正在处理第 {idx} / {total} 个段落"
        if section_key:
            section_map = {
                "claims": "权利要求书",
                "description": "说明书",
                "drawings": "说明书附图",
                "abstract": "说明书摘要",
            }
            zh_name = section_map.get(section_key, section_key)
            detail = f"当前章节：{zh_name}"
    elif stage == "before_generate":
        percent = 85
        primary = "正在生成 XML 与案卷包"
        detail = (
            payload.get("message")
            or "已完成段落处理，正在生成 XML、list.xml 和 ZIP 包..."
        )
    elif stage == "generate_110101":
        percent = 90
        primary = "正在生成发明专利请求书"
        detail = payload.get("message") or "正在生成发明专利请求书..."
    elif stage == "done":
        percent = 100
        primary = "转换完成"
        detail = payload.get("message") or "所有文件已生成，等待保存案卷 ZIP。"

    update_progress_ui(window, percent, primary, detail)
