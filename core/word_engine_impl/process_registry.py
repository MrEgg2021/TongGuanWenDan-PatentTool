import json
import os

import psutil

from core.paths_utils import get_user_data_dir

from .process_utils import _is_same_process


def _get_office_process_registry_path() -> str:
    data_dir = get_user_data_dir()
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "office_process_registry.json")


def _load_office_process_registry() -> tuple[str, list[dict]]:
    path = _get_office_process_registry_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = []
    if isinstance(data, dict):
        data = data.get("processes")
    if not isinstance(data, list):
        data = []
    return path, data


def _save_office_process_registry(path: str, processes: list[dict]) -> None:
    try:
        payload = {"processes": processes}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _register_office_process(pid: int, create_time: float | None) -> None:
    if pid is None or create_time is None:
        return
    path, processes = _load_office_process_registry()
    cleaned: list[dict] = []
    target_names = {"winword.exe"}
    for item in processes:
        try:
            ipid = int(item.get("pid"))
            ict = float(item.get("create_time"))
        except Exception:
            continue
        if _is_same_process(ipid, ict, target_names=target_names):
            cleaned.append({"pid": ipid, "create_time": ict})
    for item in cleaned:
        try:
            if int(item.get("pid")) == int(pid) and abs(float(item.get("create_time")) - float(create_time)) < 2.0:
                _save_office_process_registry(path, cleaned)
                return
        except Exception:
            continue
    cleaned.append({"pid": int(pid), "create_time": float(create_time)})
    _save_office_process_registry(path, cleaned)


def _unregister_office_process(pid: int | None, create_time: float | None) -> None:
    if pid is None or create_time is None:
        return
    path, processes = _load_office_process_registry()
    kept: list[dict] = []
    target_names = {"winword.exe"}
    for item in processes:
        try:
            ipid = int(item.get("pid"))
            ict = float(item.get("create_time"))
        except Exception:
            continue
        if ipid == int(pid) and abs(ict - float(create_time)) < 2.0:
            continue
        if _is_same_process(ipid, ict, target_names=target_names):
            kept.append({"pid": ipid, "create_time": ict})
    _save_office_process_registry(path, kept)


def terminate_owned_office_processes(*, exclude_pid: int | None = None, allow_kill: bool = False) -> int:
    path, processes = _load_office_process_registry()
    target_names = {"winword.exe"}
    kept: list[dict] = []
    terminated = 0
    for item in processes:
        try:
            pid = int(item.get("pid"))
            ct = float(item.get("create_time"))
        except Exception:
            continue
        if exclude_pid is not None and pid == int(exclude_pid):
            if _is_same_process(pid, ct, target_names=target_names):
                kept.append({"pid": pid, "create_time": ct})
            continue
        if not _is_same_process(pid, ct, target_names=target_names):
            continue
        try:
            p = psutil.Process(pid)
            p.terminate()
            try:
                p.wait(timeout=3)
            except Exception:
                if allow_kill:
                    try:
                        p.kill()
                    except Exception:
                        pass
            terminated += 1
        except Exception:
            kept.append({"pid": pid, "create_time": ct})
    _save_office_process_registry(path, kept)
    return terminated
