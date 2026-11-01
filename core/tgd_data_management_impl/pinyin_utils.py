from __future__ import annotations

import pypinyin

def get_pinyin_full(text: str) -> str:
    """获取文本的全拼（无声调，小写，无空格）。"""
    if not text:
        return ""
    # style=pypinyin.NORMAL: 普通风格，不带声调
    # heteronym=False: 不启用多音字
    pys = pypinyin.pinyin(text, style=pypinyin.NORMAL, heteronym=False)
    # pys is list of list of str, e.g. [['zhong'], ['guo']]
    return "".join([x[0] for x in pys if x]).lower()

def get_pinyin_initials(text: str) -> str:
    """获取文本的拼音首字母（小写）。"""
    if not text:
        return ""
    # style=pypinyin.FIRST_LETTER: 首字母风格
    pys = pypinyin.pinyin(text, style=pypinyin.FIRST_LETTER, heteronym=False)
    return "".join([x[0] for x in pys if x]).lower()
