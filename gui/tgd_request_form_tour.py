from __future__ import annotations

from typing import Any

from core.user_prefs import get_pref, pop_pref, set_pref


TGD_DATA_MANAGEMENT_GUIDE_AUTO_OPENED_KEY = "tgd_data_management_request_guide_auto_opened_v1"


def has_auto_opened_data_management_request_guide() -> bool:
    return bool(get_pref(TGD_DATA_MANAGEMENT_GUIDE_AUTO_OPENED_KEY, False))


def mark_data_management_request_guide_auto_opened(opened: Any = True) -> None:
    if bool(opened):
        set_pref(TGD_DATA_MANAGEMENT_GUIDE_AUTO_OPENED_KEY, True)
        return
    pop_pref(TGD_DATA_MANAGEMENT_GUIDE_AUTO_OPENED_KEY)


def get_data_management_request_guide_summary() -> str:
    return "可先批量导入带有请求书的历史案卷包，把申请人、发明人、代理机构等常用信息集中整理在这里；后续在转档功能中勾选请求书时，可在请求书弹窗直接快速下拉复用这些信息，修改后的信息也能再写回这里。"


def build_data_management_request_guide_steps() -> list[tuple[str, str]]:
    return [
        (
            "批量导入并整理信息",
            "可批量导入带有请求书历史案卷包，导入成功后，可在这里继续补充或修改申请人、发明人、联系人、分组和代理机构等信息。",
        ),
        (
            "转档时勾选请求书即可复用",
            "在转档功能中勾选请求书后，可在请求书弹窗中快速下拉选择这里的常用信息，减少重复录入和核对。",
        ),
        (
            "修改后可写回继续复用",
            "如果请求书弹窗中补充或改动了信息，可将更新内容保存回这里，后续案件继续直接复用。",
        ),
    ]


__all__ = [
    "TGD_DATA_MANAGEMENT_GUIDE_AUTO_OPENED_KEY",
    "has_auto_opened_data_management_request_guide",
    "mark_data_management_request_guide_auto_opened",
    "get_data_management_request_guide_summary",
    "build_data_management_request_guide_steps",
]
