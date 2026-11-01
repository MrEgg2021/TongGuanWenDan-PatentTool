from __future__ import annotations

import os
import shutil

from core.logging_utils import logger
from core.paths_utils import get_app_dir, get_resource_path


def export_template(output_path):
    """导出发明专利 Word 模板到指定路径。

    运行时**只复制**固定模板文件 `templates/invention_cn_template.docx`，
    不再自动生成，若模板缺失则抛出 FileNotFoundError。
    """

    base_dir = get_app_dir()
    template_path = get_resource_path(os.path.join("templates", "invention_cn_template.docx"))

    if not os.path.exists(template_path):
        msg = f"未找到模板文件: {template_path}"
        logger.error(f"❌ {msg}")
        raise FileNotFoundError(msg)

    dest_dir = os.path.dirname(os.path.abspath(output_path)) or base_dir
    if dest_dir and not os.path.exists(dest_dir):
        os.makedirs(dest_dir, exist_ok=True)

    shutil.copyfile(template_path, output_path)
    logger.info(f"📄 模板已复制到: {output_path}")
