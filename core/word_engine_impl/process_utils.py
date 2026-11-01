import psutil


def _safe_process_create_time(pid: int) -> float | None:
    try:
        p = psutil.Process(int(pid))
        return float(p.create_time())
    except Exception:
        return None


def _is_same_process(pid: int, create_time: float | None, *, target_names: set[str]) -> bool:
    try:
        p = psutil.Process(int(pid))
    except Exception:
        return False
    try:
        name = (p.name() or "").lower()
    except Exception:
        name = ""
    if name not in target_names:
        return False
    if create_time is None:
        return False
    try:
        actual = float(p.create_time())
    except Exception:
        return False
    return abs(actual - float(create_time)) < 2.0
