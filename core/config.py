from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict

import yaml

from core.paths_utils import get_resource_path

_WINDOWS_RESERVED_FILENAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{idx}" for idx in range(1, 10)),
    *(f"LPT{idx}" for idx in range(1, 10)),
}


def load_config(config_path: str | None = None) -> Dict[str, Any]:
    """加载全局配置文件，与原 main.load_config 行为保持一致。"""
    if config_path is None:
        config_path = get_resource_path("config.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_app_display_title() -> str:
    return f"通官文旦-专利工具 V{load_config()['version']}"


def sanitize_filename(name: object) -> str:
    """清洗文件名，移除 Windows 不安全字符并限制长度。"""
    text = unicodedata.normalize("NFC", str(name or "")).strip()
    if not text:
        return "output"
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = re.sub(r"[\x00\\/:*?\"<>|]", "_", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    if not text:
        return "output"
    if len(text) > 80:
        text = text[:80].strip(" .")
    if not text:
        return "output"

    stem, dot, suffix = text.partition(".")
    if stem.upper() in _WINDOWS_RESERVED_FILENAMES:
        text = f"{stem}_{dot}{suffix}" if dot else f"{stem}_"
    return text
