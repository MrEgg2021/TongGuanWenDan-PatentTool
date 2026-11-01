from __future__ import annotations

import json
import os
import hashlib
import sqlite3
import tempfile
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from core.paths_utils import get_user_data_dir


_TGD_SETTINGS_FILENAME = "tgd_settings.json"
_TGD_DB_PATH_KEY = "db_path"
_DEFAULT_DB_FILENAME = "tgd_data_management.db"


def get_tgd_settings_path() -> str:
    """返回通官文旦-专利工具模块用户配置文件路径（位于用户数据目录，可写）。"""

    base = get_user_data_dir()
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, _TGD_SETTINGS_FILENAME)


def load_tgd_settings() -> Dict[str, Any]:
    """读取通官文旦-专利工具模块用户配置；只有文件不存在才使用空配置。"""

    path = get_tgd_settings_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"数据库设置格式无效：{path}")
    return data


def _get_drive_type_windows(root_path: str) -> Optional[int]:
    try:
        import ctypes

        GetDriveTypeW = ctypes.windll.kernel32.GetDriveTypeW
        GetDriveTypeW.argtypes = [ctypes.c_wchar_p]
        GetDriveTypeW.restype = ctypes.c_uint
        return int(GetDriveTypeW(str(root_path)))
    except Exception:
        return None


def is_network_path(path: str) -> bool:
    """判断给定路径是否为网络路径（UNC 或映射网络驱动器）。"""

    if not path:
        return False

    try:
        p = os.path.abspath(str(path).strip())
    except Exception:
        return False

    if p.startswith("\\\\"):
        return True

    drive, _ = os.path.splitdrive(p)
    if not drive:
        return False

    root = drive + "\\"

    dtype = _get_drive_type_windows(root)
    if dtype == 4:
        return True

    if dtype is None:
        try:
            import win32file

            return int(win32file.GetDriveType(root)) == int(win32file.DRIVE_REMOTE)
        except Exception:
            return False

    return False


def normalize_db_path(path: str) -> str:
    """标准化 DB 路径：转绝对路径；若传入目录则自动补默认 DB 文件名。"""

    raw = str(path or "").strip()
    if not raw:
        return os.path.abspath(os.path.join(get_user_data_dir(), _DEFAULT_DB_FILENAME))

    p = os.path.abspath(raw)
    try:
        if os.path.isdir(p):
            p = os.path.join(p, _DEFAULT_DB_FILENAME)
    except Exception:
        pass

    return p


def get_db_path() -> str:
    """获取当前 DB 路径；若未配置则返回默认路径（用户数据目录下）。"""

    settings = load_tgd_settings()
    raw = settings.get(_TGD_DB_PATH_KEY)
    p = normalize_db_path(_norm_text(raw)) if raw else normalize_db_path("")
    if is_network_path(p):
        return normalize_db_path("")
    return p


def _norm_text(value) -> str:
    if value is None:
        return ""
    try:
        return str(value).strip()
    except Exception:
        return ""


def get_app_lock_path() -> str:
    """返回应用单实例锁文件路径（位于用户数据目录）。"""

    base = get_user_data_dir()
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "app_instance.lock")


def ensure_daily_backup(db_path: str, *, keep_days: int = 7) -> Optional[str]:
    """为当前源库创建一致、可恢复的每日备份。"""

    p = normalize_db_path(db_path)
    if not os.path.isfile(p):
        return None
    if os.path.getsize(p) == 0:
        raise sqlite3.DatabaseError(f"数据库文件为空，无法备份：{p}")

    today = datetime.now().strftime("%Y%m%d")
    source_id = hashlib.sha256(os.path.normcase(os.path.realpath(p)).encode("utf-8")).hexdigest()[:16]
    prefix = f"data_auto_v2_{source_id}_"
    backup_dir = os.path.join(os.path.dirname(p), ".backups")
    os.makedirs(backup_dir, exist_ok=True)
    backup_path = os.path.join(backup_dir, f"{prefix}{today}.bak")
    if os.path.exists(backup_path):
        _verify_restorable_backup(backup_path)
        return backup_path

    fd, tmp = tempfile.mkstemp(prefix=f".{prefix}", suffix=".tmp", dir=backup_dir)
    os.close(fd)
    try:
        with closing(sqlite3.connect(Path(p).resolve().as_uri() + "?mode=ro", uri=True)) as source:
            with closing(sqlite3.connect(tmp)) as target:
                source.backup(target)
        _verify_restorable_backup(tmp)
        os.replace(tmp, backup_path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

    # Older data_auto_*.bak files have unknown ownership; retain them.
    own_names = sorted(
        (name for name in os.listdir(backup_dir)
         if name.startswith(prefix) and name.endswith(".bak")
         and len(name) == len(prefix) + 12 and name[len(prefix):-4].isdigit()),
        reverse=True,
    )
    for name in own_names[max(1, keep_days):]:
        os.remove(os.path.join(backup_dir, name))
    return backup_path


def _verify_restorable_backup(path: str) -> None:
    with open(path, "rb") as f:
        header = f.read(16)
    if os.path.getsize(path) < 100 or header != b"SQLite format 3\x00":
        raise sqlite3.DatabaseError(f"数据库备份文件格式无效：{path}")
    fd, restored_path = tempfile.mkstemp(prefix=".backup_restore_", suffix=".tmp", dir=os.path.dirname(path))
    os.close(fd)
    try:
        with closing(sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)) as backup:
            with closing(sqlite3.connect(restored_path)) as restored:
                backup.backup(restored)
                result = restored.execute("PRAGMA integrity_check").fetchone()
                if result != ("ok",):
                    raise RuntimeError(f"数据库备份无法通过恢复校验：{path}: {result}")
    finally:
        if os.path.exists(restored_path):
            os.remove(restored_path)
