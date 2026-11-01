import os
import sys
import traceback

from PySide6.QtWidgets import QFileDialog

from core.config import load_config
from core.template_export import export_template
from core.paths_utils import get_app_dir
from gui.dialog_utils import show_blocking_alert_modal


def open_output_dir(window) -> None:
    """打开配置中定义的输出目录。"""
    base_dir = get_app_dir()
    try:
        cfg = load_config()
    except FileNotFoundError:
        show_blocking_alert_modal(window, "错误", "程序配置文件缺失，请重新下载完整程序后重试。", primary_text="关闭", secondary_text="关闭")
        return
    except Exception as e:
        show_blocking_alert_modal(window, "错误", f"无法读取程序设置：{e}", primary_text="关闭", secondary_text="关闭")
        return
    output_dir = cfg.get("paths", {}).get("output_dir")
    if not output_dir:
        show_blocking_alert_modal(window, "错误", "未设置输出目录，请在转档页面选择输出目录。", primary_text="关闭", secondary_text="关闭")
        return

    if not os.path.isabs(output_dir):
        output_dir = os.path.join(base_dir, output_dir)
    if not os.path.isdir(output_dir):
        show_blocking_alert_modal(window, "错误", f"输出目录不存在：{output_dir}", primary_text="关闭", secondary_text="关闭")
        return

    os.startfile(output_dir)


def open_log_file(window) -> None:
    """打开当前会话的转换日志文件。"""
    show_blocking_alert_modal(window, "提示", "GUI 不提供打开日志入口。", primary_text="关闭", secondary_text="关闭")
    return


def export_word_template(window) -> None:
    """导出发明专利 Word 模板文件。"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    default_dir = os.path.join(base_dir, "output")
    os.makedirs(default_dir, exist_ok=True)
    default_path = os.path.join(default_dir, "模版文件.docx")

    dest_path, _ = QFileDialog.getSaveFileName(
        window,
        "保存发明专利 Word 模板",
        default_path,
        "Word 文档 (*.docx)",
    )
    if not dest_path:
        return

    try:
        export_template(dest_path)
        show_blocking_alert_modal(window, "完成", f"模板已导出到：\n{dest_path}", primary_text="关闭", secondary_text="关闭")
    except FileNotFoundError:
        show_blocking_alert_modal(
            window,
            "错误",
            "未找到模板源文件：resources/templates/invention_cn_template.docx\n请先在项目根目录下的 resources/templates 目录中放入该文件。",
            primary_text="关闭",
            secondary_text="关闭",
        )
    except Exception as e:
        if not getattr(sys, "frozen", False):
            traceback.print_exc()
        show_blocking_alert_modal(window, "错误", f"导出模板失败：{e}", primary_text="关闭", secondary_text="关闭")
