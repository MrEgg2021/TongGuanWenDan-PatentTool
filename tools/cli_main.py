import os
import argparse
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.conversion import run_conversion
from core.config import get_app_display_title
from core.logging_utils import logger
from core.template_export import export_template


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=get_app_display_title())
    parser.add_argument(
        "--export-template",
        nargs="?",
        const="__DEFAULT__",
        metavar="OUT_PATH",
        help="导出发明专利 Word 模板；不带参数时导出到 output/模版文件.docx",
    )
    return parser


def main():
    logger.info("%s 启动...", get_app_display_title())
    base_dir = os.path.dirname(os.path.abspath(__file__))
    args = build_parser().parse_args()

    # 如果指定了导出模板，则只执行导出逻辑
    if args.export_template is not None:
        if args.export_template == "__DEFAULT__":
            default_dir = os.path.join(base_dir, "output")
            os.makedirs(default_dir, exist_ok=True)
            out_path = os.path.join(default_dir, "模版文件.docx")
        else:
            out_path = args.export_template

        export_template(out_path)
        logger.info(f"✅ 模板导出完成: {out_path}")
        return

    # 默认行为：在当前目录查找第一个 DOCX 并执行转换
    input_files = [
        f
        for f in os.listdir('.')
        if f.lower().endswith(('.doc', '.docx')) and not f.startswith('~$')
    ]
    if not input_files:
        logger.error("❌ 未找到 DOC/DOCX 文件")
        raise SystemExit(1)
    target_file = input_files[0]
    run_conversion(target_file, config_path=None)


if __name__ == "__main__":
    main()
