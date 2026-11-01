from __future__ import annotations

import os
import sqlite3
import sys
from contextlib import contextmanager
from typing import Callable, Dict, Iterator, Optional

from core.logging_utils import logger
from core.paths_utils import get_user_data_dir

from .infra import ensure_daily_backup, get_db_path, is_network_path


_TGD_DB_DEBUG_CONNECT_DUMPED = False
_TGD_DB_RAW_CONNECT_FN = None
_TGD_DB_RAW_CONNECTION_CLS = None


def _is_bad_connect_fn(fn) -> bool:
    try:
        if not callable(fn):
            return True
        mod = str(getattr(fn, "__module__", "") or "")
        name = str(getattr(fn, "__name__", "") or "")
        if mod == "functools" and name == "decorating_function":
            return True
        return False
    except Exception:
        return True


def _get_fresh_lowlevel_connect_and_cls():
    try:
        import _sqlite3 as _tgd__sqlite3_fresh

        fn = getattr(_tgd__sqlite3_fresh, "connect", None)
        cls = getattr(_tgd__sqlite3_fresh, "Connection", None)
        if _is_bad_connect_fn(fn):
            fn = None
        if not isinstance(cls, type):
            cls = None
        return fn, cls
    except Exception:
        return None, None


def _open_connection_raw(path: str):
    fn, cls = _get_fresh_lowlevel_connect_and_cls()
    if callable(fn) and isinstance(cls, type):
        return fn(path, factory=cls)
    if callable(fn):
        try:
            return fn(path)
        except Exception:
            return None
    fallback_cls = _TGD_DB_RAW_CONNECTION_CLS if isinstance(_TGD_DB_RAW_CONNECTION_CLS, type) else None
    if callable(_TGD_DB_RAW_CONNECT_FN) and fallback_cls is not None:
        try:
            return _TGD_DB_RAW_CONNECT_FN(path, factory=fallback_cls)
        except Exception:
            return None
    if callable(_TGD_DB_RAW_CONNECT_FN):
        try:
            return _TGD_DB_RAW_CONNECT_FN(path)
        except Exception:
            return None
    return None


try:
    import _sqlite3 as _tgd__sqlite3

    _TGD_DB_RAW_CONNECT_FN = getattr(_tgd__sqlite3, "connect", None)
    _TGD_DB_RAW_CONNECTION_CLS = getattr(_tgd__sqlite3, "Connection", None)
    if not (callable(_TGD_DB_RAW_CONNECT_FN) and (not _is_bad_connect_fn(_TGD_DB_RAW_CONNECT_FN))):
        _TGD_DB_RAW_CONNECT_FN = None
except Exception:
    _TGD_DB_RAW_CONNECT_FN = None
    _TGD_DB_RAW_CONNECTION_CLS = None
if not callable(_TGD_DB_RAW_CONNECT_FN):
    try:
        _TGD_DB_RAW_CONNECT_FN = getattr(sqlite3, "connect", None)
        if _is_bad_connect_fn(_TGD_DB_RAW_CONNECT_FN):
            _TGD_DB_RAW_CONNECT_FN = None
    except Exception:
        _TGD_DB_RAW_CONNECT_FN = None
if not callable(_TGD_DB_RAW_CONNECTION_CLS):
    try:
        _TGD_DB_RAW_CONNECTION_CLS = getattr(sqlite3, "Connection", None)
    except Exception:
        _TGD_DB_RAW_CONNECTION_CLS = None


def _debug_log_path() -> str:
    try:
        return os.path.join(get_user_data_dir(), "tgd_db_debug_connect.log")
    except Exception:
        return os.path.abspath("tgd_db_debug_connect.log")


def _debug_write_line(line: str) -> None:
    try:
        print(line, file=sys.stderr)
    except Exception:
        pass
    try:
        path = _debug_log_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(str(line) + "\n")
    except Exception:
        pass


def _debug_dump_connect_state() -> None:
    global _TGD_DB_DEBUG_CONNECT_DUMPED
    try:
        if _TGD_DB_DEBUG_CONNECT_DUMPED:
            return
        if not os.environ.get("TGD_DB_DEBUG_CONNECT"):
            return
        _TGD_DB_DEBUG_CONNECT_DUMPED = True
    except Exception:
        return

    def _safe_str(v) -> str:
        try:
            return str(v)
        except Exception:
            return "<unprintable>"

    def _dump_fn(fn, title: str) -> None:
        _debug_write_line(f"[TGD_DB_DEBUG_CONNECT] {title}:")
        try:
            _debug_write_line(f"  repr={_safe_str(fn)!r}")
        except Exception:
            pass
        try:
            _debug_write_line(f"  type={_safe_str(type(fn))}")
        except Exception:
            pass
        try:
            _debug_write_line(f"  id={id(fn)}")
        except Exception:
            pass
        try:
            _debug_write_line(f"  __module__={_safe_str(getattr(fn, '__module__', None))}")
        except Exception:
            pass
        try:
            _debug_write_line(f"  __name__={_safe_str(getattr(fn, '__name__', None))}")
        except Exception:
            pass
        try:
            _debug_write_line(f"  __qualname__={_safe_str(getattr(fn, '__qualname__', None))}")
        except Exception:
            pass

        try:
            chain = []
            seen = set()
            cur = fn
            for _ in range(30):
                if cur is None:
                    break
                cid = id(cur)
                if cid in seen:
                    break
                seen.add(cid)
                chain.append(cur)
                cur = getattr(cur, "__wrapped__", None)
            if len(chain) > 1:
                _debug_write_line("  __wrapped__ chain:")
                for i, c in enumerate(chain):
                    cm = _safe_str(getattr(c, "__module__", None))
                    cq = _safe_str(getattr(c, "__qualname__", None))
                    cn = _safe_str(getattr(c, "__name__", None))
                    _debug_write_line(f"    [{i}] id={id(c)} module={cm} qualname={cq} name={cn}")
        except Exception:
            pass

    _debug_write_line("[TGD_DB_DEBUG_CONNECT] sqlite3 module:")
    try:
        _debug_write_line(f"  sqlite3.__file__={_safe_str(getattr(sqlite3, '__file__', None))}")
    except Exception:
        pass
    try:
        _dump_fn(getattr(sqlite3, "connect", None), "sqlite3.connect")
    except Exception:
        pass
    try:
        import _sqlite3

        _dump_fn(getattr(_sqlite3, "connect", None), "_sqlite3.connect")
    except Exception:
        pass


def open_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """打开 SQLite 连接。

    - 默认使用通官文旦-专利工具配置中的 DB 路径
    - 禁止网络路径（UNC/映射盘）
    - 自动创建父目录
    """

    path = db_path or get_db_path()
    if is_network_path(path):
        raise ValueError("数据库路径不允许使用网络路径（UNC/映射盘）。")
    try:
        parent = os.path.dirname(os.path.abspath(path))
        if parent:
            os.makedirs(parent, exist_ok=True)
    except Exception:
        pass
    try:
        _debug_dump_connect_state()
    except Exception:
        pass
    try:
        conn = _open_connection_raw(path)
    except RecursionError as exc:
        _debug_write_line("[TGD_DB_DEBUG_CONNECT] RecursionError: low-level connect trigger recursion; refuse sqlite3.connect fallback.")
        raise RuntimeError("数据库连接失败：检测到递归包装的 sqlite connect，请检查环境是否 monkeypatch 了 sqlite3.connect。") from exc
    if conn is None:
        _debug_write_line("[TGD_DB_DEBUG_CONNECT] low-level sqlite connect unavailable; refuse sqlite3.connect fallback.")
        raise RuntimeError("数据库连接失败：未获取到底层 sqlite 连接函数，可设置 TGD_DB_DEBUG_CONNECT=1 查看详细日志。")
    try:
        conn.row_factory = sqlite3.Row
    except Exception:
        pass
    try:
        conn.execute("PRAGMA foreign_keys = ON")
    except Exception as exc:
        logger.warning("[TGD_DB] 启用外键约束失败，继续使用当前连接：%s", exc)
    return conn


@contextmanager
def db_session(db_path: Optional[str] = None) -> Iterator[sqlite3.Connection]:
    """数据库会话上下文：自动提交；异常时回滚；最终关闭连接。"""

    conn = open_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            conn.close()
        except Exception:
            pass


def get_user_version(conn: sqlite3.Connection) -> int:
    """读取 `PRAGMA user_version`（用于迁移版本号）。"""

    cur = conn.execute("PRAGMA user_version")
    row = cur.fetchone()
    if row is None:
        raise RuntimeError("无法读取数据库版本")
    return int(row[0])


def set_user_version(conn: sqlite3.Connection, version: int) -> None:
    """写入 `PRAGMA user_version`。"""

    conn.execute(f"PRAGMA user_version = {int(version)}")


MigrationFunc = Callable[[sqlite3.Connection], None]


def apply_migrations(
    conn: sqlite3.Connection,
    migrations: Dict[int, MigrationFunc],
    *,
    backup_db_path: Optional[str] = None,
    backup_already_checked: bool = False,
) -> int:
    """按 `PRAGMA user_version` 迭代执行迁移。

    - 迁移字典 key：当前版本号
    - value：把 DB 从该版本迁移到下一版本的函数（函数内部必须更新 user_version）
    - 执行迁移前必须完成每日备份
    """

    current = get_user_version(conn)

    did_backup = backup_already_checked
    while True:
        fn = migrations.get(current)
        if fn is None:
            break

        if not did_backup:
            ensure_daily_backup(backup_db_path or get_db_path())
            did_backup = True

        fn(conn)
        current = get_user_version(conn)

    return current
