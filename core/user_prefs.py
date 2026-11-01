from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

from core.logging_utils import logger
from core.paths_utils import get_user_data_dir

_PREFS_FILENAME = "user_prefs.json"


def _get_prefs_path() -> str:
    return os.path.join(get_user_data_dir(), _PREFS_FILENAME)


def _backup_corrupt_file(path: str, reason: str) -> None:
    backup_path = f"{path}.corrupt-{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    try:
        os.replace(path, backup_path)
    except Exception as move_exc:
        logger.warning("[USER_PREFS] 偏好文件损坏且备份失败，本次按空配置继续；原因：%s；备份错误：%s", reason, move_exc)
        return
    logger.warning("[USER_PREFS] 偏好文件损坏，已备份到 %s，本次按空配置继续；原因：%s", backup_path, reason)


def _load_json(path: str) -> dict:
    try:
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            _backup_corrupt_file(path, "内容不是 JSON 对象")
            return {}
        return data
    except Exception as exc:
        _backup_corrupt_file(path, str(exc))
        return {}


def _save_json_atomic(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def load_prefs() -> dict:
    return _load_json(_get_prefs_path())


def save_prefs(data: dict) -> None:
    _save_json_atomic(_get_prefs_path(), data)


def get_pref(key: str, default: Any = None) -> Any:
    data = load_prefs()
    return data.get(key, default)


def set_pref(key: str, value: Any) -> None:
    data = load_prefs()
    data[key] = value
    save_prefs(data)


def pop_pref(key: str) -> None:
    data = load_prefs()
    if key in data:
        data.pop(key, None)
        save_prefs(data)

