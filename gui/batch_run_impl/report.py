import os
import sys
import traceback


def _write_batch_report_txt(
    report_path: str,
    batch_zip_filename: str,
    success_count: int,
    fail_count: int,
    error_messages: list[str],
    table_warn_files: list[tuple[str, int]],
    drawings_warn_files: list[tuple[str, str]] | None = None,
    header_empty_files: list[str] | None = None,
) -> bool:
    try:
        lines: list[str] = []
        lines.append("批量处理报告")
        lines.append(f"批量案卷包：{batch_zip_filename}")
        lines.append("")
        lines.append(f"成功：{success_count} 个")
        lines.append(f"失败：{fail_count} 个")

        if error_messages:
            lines.append("")
            lines.append("失败详情：")
            for msg in error_messages:
                lines.append(f"- {msg}")

        if table_warn_files:
            lines.append("")
            lines.append("表格转换提醒（需人工复查）：")
            for name, cnt in table_warn_files:
                lines.append(f"- {name}：{cnt} 个表格未能自动转换，请人工核对")

        if drawings_warn_files:
            lines.append("")
            lines.append("说明书附图图号警告（需人工复查）：")
            for name, summary in drawings_warn_files:
                lines.append(f"- {name}：{summary}")

        if header_empty_files:
            cleaned = [os.path.basename(p) for p in header_empty_files if p]
            if cleaned:
                lines.append("")
                lines.append("页眉检测全空（需人工复查）：")
                for name in cleaned:
                    lines.append(f"- {name}")

        os.makedirs(os.path.dirname(os.path.abspath(report_path)), exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines).strip() + "\n")
        return True
    except Exception:
        if not getattr(sys, "frozen", False):
            traceback.print_exc()
        return False


__all__ = ["_write_batch_report_txt"]
