from __future__ import annotations


def _strip_cell_text(cell) -> str:
    """安全提取 Word 表格单元格文本，去除结尾控制字符。"""
    try:
        # 既兼容 Table Cell（有 .Range 属性），也兼容直接传入 Range 对象
        rng = getattr(cell, "Range", cell)
        text = rng.Text
    except Exception:
        text = ""
    if not text:
        return ""
    # 常见尾部包含 "\r\x07" 等控制符
    text = text.replace("\r", "").replace("\x07", "")
    return str(text).strip()


__all__ = ["_strip_cell_text"]
