import os

from PySide6.QtWidgets import QFileDialog

from core.tgd_data_management_impl.excel_io import (
    export_tgd_excel_data,
    export_tgd_excel_template,
    format_import_summary_text,
    import_tgd_excel_data,
)
from gui.dialog_utils import show_blocking_alert_modal

from .output_dir import _ensure_output_dir

def on_tgd_excel_export_template(window) -> None:
    default_dir = _ensure_output_dir()
    default_path = os.path.join(default_dir, "通官文旦-专利工具_申请信息_导入模版.xlsx")
    dest_path, _ = QFileDialog.getSaveFileName(
        window,
        "导出通官文旦-专利工具 Excel 导入模板",
        default_path,
        "Excel 文件 (*.xlsx)",
    )
    if not dest_path:
        return

    try:
        export_tgd_excel_template(dest_path)
        show_blocking_alert_modal(window, "完成", f"模板已导出到：\n{dest_path}", primary_text="关闭", secondary_text="关闭")
    except Exception as e:
        show_blocking_alert_modal(window, "错误", f"导出模板失败：{e}", primary_text="关闭", secondary_text="关闭")


def on_tgd_excel_import(window) -> None:
    default_dir = _ensure_output_dir()
    src_path, _ = QFileDialog.getOpenFileName(
        window,
        "导入通官文旦-专利工具 Excel",
        default_dir,
        "Excel 文件 (*.xlsx)",
    )
    if not src_path:
        return

    try:
        summary = import_tgd_excel_data(src_path)
        text = format_import_summary_text(summary)
        show_blocking_alert_modal(window, "导入完成", text, primary_text="关闭", secondary_text="关闭")
    except Exception as e:
        show_blocking_alert_modal(window, "错误", f"导入失败：{e}", primary_text="关闭", secondary_text="关闭")


def on_tgd_excel_export(window) -> None:
    default_dir = _ensure_output_dir()
    default_path = os.path.join(default_dir, "通官文旦-专利工具_数据导出.xlsx")
    dest_path, _ = QFileDialog.getSaveFileName(
        window,
        "导出通官文旦-专利工具数据到 Excel",
        default_path,
        "Excel 文件 (*.xlsx)",
    )
    if not dest_path:
        return

    try:
        export_tgd_excel_data(dest_path, masked=False)
        show_blocking_alert_modal(window, "完成", f"数据已导出到：\n{dest_path}", primary_text="关闭", secondary_text="关闭")
    except Exception as e:
        show_blocking_alert_modal(window, "错误", f"导出失败：{e}", primary_text="关闭", secondary_text="关闭")


def on_tgd_excel_export_masked(window) -> None:
    default_dir = _ensure_output_dir()
    default_path = os.path.join(default_dir, "通官文旦-专利工具_数据导出_脱敏.xlsx")
    dest_path, _ = QFileDialog.getSaveFileName(
        window,
        "脱敏导出通官文旦-专利工具数据到 Excel",
        default_path,
        "Excel 文件 (*.xlsx)",
    )
    if not dest_path:
        return

    try:
        export_tgd_excel_data(dest_path, masked=True)
        show_blocking_alert_modal(window, "完成", f"数据已脱敏导出到：\n{dest_path}", primary_text="关闭", secondary_text="关闭")
    except Exception as e:
        show_blocking_alert_modal(window, "错误", f"脱敏导出失败：{e}", primary_text="关闭", secondary_text="关闭")
