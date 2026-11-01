import os
import zipfile

from PySide6.QtWidgets import QFileDialog

from .report import _write_batch_report_txt
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


def _build_batch_fallback_notice(window, enabled_sections: dict) -> str | None:
    _ = enabled_sections
    entries = []
    try:
        raw = getattr(window, "_batch_object_fallback_warn_files", None)
        if isinstance(raw, list):
            entries = raw
    except Exception:
        entries = []
    if not entries:
        return None

    total_hits = 0
    lines = [f"部分外部对象未能完整转换：共 {len(entries)} 个文件涉及该类对象。"]
    for name, count, kind_summary in entries[:10]:
        try:
            total_hits += int(count or 0)
        except Exception:
            pass
        detail = f"{name}：{count} 处"
        if kind_summary:
            detail += f"（{kind_summary}）"
        lines.append(detail)
    if len(entries) > 10:
        lines.append(f"... 还有 {len(entries) - 10} 个文件未展开")
    if total_hits > 0:
        lines[0] = f"部分外部对象未能完整转换：共 {total_hits} 处，分布在 {len(entries)} 个文件中。"
    return "\n".join(lines)


def finalize_batch_zip(
    window,
    *,
    batch_zip_filename: str,
    individual_zips: list[tuple[str, str]],
    enabled_sections: dict,
    success_count: int,
    fail_count: int,
    error_messages: list[str],
    table_warn_files: list[tuple[str, int]],
    result_items: list[tuple[str, str]],
) -> bool:
    saved_batch = False
    result_items = result_items or []
    _raw_total = getattr(window, "_batch_total_files", 0)
    if isinstance(_raw_total, int):
        total_files = _raw_total
    elif isinstance(_raw_total, (list, tuple, set, dict)):
        try:
            total_files = len(_raw_total)
        except Exception:
            total_files = 0
    else:
        try:
            total_files = int(_raw_total or 0)
        except Exception:
            total_files = 0

    # 创建批量包
    if individual_zips:
        # 根据用户指定的输出目录和文件名生成最终批量 ZIP 路径
        dest_path = ""
        output_dir = ""
        try:
            if hasattr(window, "output_dir_edit"):
                output_dir = window.output_dir_edit.text().strip()
        except Exception:
            output_dir = ""

        if output_dir:
            try:
                os.makedirs(output_dir, exist_ok=True)
                dest_path = os.path.join(output_dir, batch_zip_filename)
                dest_path = _resolve_collision_path(dest_path)
            except Exception:
                dest_path = ""
                show_blocking_alert_modal(
                    window,
                    "提示",
                    f"创建输出目录失败：{output_dir}\n将改为手动选择保存位置。",
                    primary_text="关闭",
                    secondary_text="关闭",
                )

        if not dest_path:
            default_path = batch_zip_filename
            try:
                last_saved = getattr(window, "_last_batch_saved_path", "") or ""
                if last_saved:
                    last_dir = os.path.dirname(os.path.abspath(last_saved))
                    if last_dir and os.path.isdir(last_dir):
                        default_path = os.path.join(last_dir, batch_zip_filename)
            except Exception:
                default_path = batch_zip_filename

            dest_path, _ = QFileDialog.getSaveFileName(
                window,
                "保存批量案卷包",
                default_path,
                "ZIP 文件 (*.zip)",
            )

        # 汇总结果信息
        msg = f"批量处理完成\n\n成功: {success_count} 个\n失败: {fail_count} 个"
        if error_messages:
            msg += "\n\n错误详情：\n" + "\n".join(error_messages[:5])
            if len(error_messages) > 5:
                msg += f"\n... 还有 {len(error_messages)-5} 个错误"

        # 若某些文件中存在表格转换失败，追加人工复查提示
        if table_warn_files:
            msg += "\n\n表格转换提醒（需人工复查）："
            for name, cnt in table_warn_files[:10]:
                msg += f"\n- {name}：{cnt} 个表格未能自动转换，请人工核对"
            if len(table_warn_files) > 10:
                msg += f"\n... 还有 {len(table_warn_files)-10} 个文件存在表格需复查"

        drawings_warn_files = []
        try:
            raw = getattr(window, "_batch_drawings_warn_files", None)
            if isinstance(raw, list):
                drawings_warn_files = raw
        except Exception:
            drawings_warn_files = []

        if drawings_warn_files:
            msg += "\n\n说明书附图图号警告（需人工复查）："
            for name, summary in drawings_warn_files[:10]:
                msg += f"\n- {name}：{summary}"
            if len(drawings_warn_files) > 10:
                msg += f"\n... 还有 {len(drawings_warn_files)-10} 个文件存在附图图号需复查"

        if dest_path:
            dest_path = _resolve_collision_path(dest_path)
            # 用户选择了保存位置，再实际创建批量 ZIP
            window.update_progress(95, "正在创建批量包...", dest_path)

            with zipfile.ZipFile(dest_path, "w", zipfile.ZIP_DEFLATED) as batch_zip:
                for src_path, arc_name in individual_zips:
                    if os.path.exists(src_path):
                        batch_zip.write(src_path, arc_name)

            # 写出失败/警告报告到同目录，便于批量处理后复盘
            report_path = None
            try:
                header_empty = getattr(window, "_batch_header_empty_files", None)

                should_write_report = False
                if fail_count > 0:
                    should_write_report = True
                if error_messages:
                    should_write_report = True
                if table_warn_files:
                    should_write_report = True
                if drawings_warn_files:
                    should_write_report = True
                if header_empty:
                    should_write_report = True

                if should_write_report:
                    report_base = os.path.splitext(os.path.basename(dest_path))[0]
                    report_path = os.path.join(
                        os.path.dirname(dest_path),
                        f"{report_base}_失败清单.txt",
                    )
                    report_path = _resolve_collision_path(report_path)
                    ok = _write_batch_report_txt(
                        report_path,
                        batch_zip_filename,
                        success_count,
                        fail_count,
                        error_messages,
                        table_warn_files,
                        drawings_warn_files=drawings_warn_files,
                        header_empty_files=header_empty,
                    )
                    if not ok:
                        report_path = None
            except Exception:
                report_path = None

            final_batch_info = f"第 {total_files}/{total_files} 个文件 | 成功：{success_count} | 失败：{fail_count}"
            if report_path:
                try:
                    final_batch_info += f" | 报告：{os.path.basename(report_path)}"
                except Exception:
                    pass
            window.update_progress(
                100,
                "批量处理完成",
                f"成功: {success_count}, 失败: {fail_count}",
                batch_info=final_batch_info,
            )
            try:
                setattr(window, "_last_batch_saved_path", dest_path)
            except Exception:
                pass
            saved_batch = True
        else:
            # 用户在批量完成后取消了保存，仅提示处理结果
            window.update_progress(
                100,
                "批量处理完成",
                f"成功: {success_count}, 失败: {fail_count}",
                batch_info=(f"第 {total_files}/{total_files} 个文件 | 成功：{success_count} | 失败：{fail_count}"),
            )

        try:
            header_empty = getattr(window, "_batch_header_empty_files", None)
        except Exception:
            header_empty = None
        should_show_summary = False
        try:
            if fail_count > 0:
                should_show_summary = True
            if error_messages:
                should_show_summary = True
            if table_warn_files:
                should_show_summary = True
            if drawings_warn_files:
                should_show_summary = True
            if header_empty:
                should_show_summary = True
        except Exception:
            should_show_summary = False
        if should_show_summary:
            try:
                show_blocking_alert_modal(
                    window,
                    "提示",
                    msg,
                    primary_text="关闭",
                    secondary_text="关闭",
                    close_result="secondary",
                )
            except Exception:
                pass

        window._has_run_conversion = True
    else:
        window.update_progress(
            100,
            "批量处理完成",
            "没有成功处理任何文件。",
            batch_info="❌ 所有文件均未成功处理",
        )

    notice_text = _build_batch_fallback_notice(window, enabled_sections)
    # 展示结果成绩单遮罩
    try:
        window._show_result_overlay(
            result_items,
            total_files,
            success_count,
            fail_count,
            notice_text=notice_text,
        )
    except Exception:
        pass
    return saved_batch


__all__ = ["finalize_batch_zip"]
