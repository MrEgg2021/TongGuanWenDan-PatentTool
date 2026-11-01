from __future__ import annotations

import psutil

from .process_registry import _register_office_process
from .process_utils import _safe_process_create_time
from .word_com_resolver import collect_word_app_diag, is_wps_runtime_diag


WINWORD_PROCESS_NAME = "winword.exe"


def snapshot_winword_processes() -> dict[int, float]:
    snapshot: dict[int, float] = {}
    try:
        processes = psutil.process_iter(["pid", "name", "create_time"])
    except Exception:
        return snapshot

    for proc in processes:
        try:
            name = str(proc.info.get("name") or "").lower()
            pid = proc.info.get("pid")
            if name != WINWORD_PROCESS_NAME or pid is None:
                continue
            create_time = proc.info.get("create_time")
            if create_time is None:
                create_time = _safe_process_create_time(int(pid))
            if create_time is None:
                continue
            snapshot[int(pid)] = float(create_time)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
        except Exception:
            continue
    return snapshot


def _candidate_summary(snapshot: dict[int, float]) -> list[tuple[int, float]]:
    return sorted((int(pid), float(create_time)) for pid, create_time in snapshot.items())


def _diag_confirms_microsoft_word(diag: dict | None) -> bool:
    if not isinstance(diag, dict):
        return False
    if is_wps_runtime_diag(diag):
        return False
    try:
        name = str(diag.get("Name") or "").strip().lower()
    except Exception:
        name = ""
    if "microsoft word" in name:
        return True
    try:
        proc_name = str(diag.get("ProcName") or "").strip().lower()
    except Exception:
        proc_name = ""
    if proc_name == WINWORD_PROCESS_NAME:
        return True
    try:
        proc_exe = str(diag.get("ProcExe") or "").strip().lower().replace("/", "\\")
    except Exception:
        proc_exe = ""
    return proc_exe.endswith("\\winword.exe") or proc_exe == "winword.exe"


def _log_claim_warning(logger, message: str, *args) -> None:
    if logger is None:
        return
    try:
        logger.warning(message, *args)
    except Exception:
        pass


def find_claimable_winword_process(
    *,
    before_snapshot: dict[int, float] | None = None,
    min_create_time: float | None = None,
    diag: dict | None = None,
    after_snapshot: dict[int, float] | None = None,
    reason: str = "",
    logger=None,
) -> tuple[int, float] | None:
    if is_wps_runtime_diag(diag):
        _log_claim_warning(logger, "[WORD_PID_CLAIM] skipped WPS runtime diag reason=%r diag=%r", reason, diag)
        return None
    if not _diag_confirms_microsoft_word(diag):
        _log_claim_warning(
            logger,
            "[WORD_PID_CLAIM] skipped non-confirmed Microsoft Word diag reason=%r diag=%r",
            reason,
            diag,
        )
        return None

    before = dict(before_snapshot) if before_snapshot is not None else None
    after = dict(after_snapshot) if after_snapshot is not None else snapshot_winword_processes()
    candidates: list[tuple[int, float]] = []
    for candidate_pid, create_time in after.items():
        try:
            pid_int = int(candidate_pid)
            create_float = float(create_time)
        except Exception:
            continue
        if min_create_time is not None and create_float < float(min_create_time) - 2.0:
            continue
        if before is not None:
            old_create_time = before.get(pid_int)
            if old_create_time is not None and abs(float(old_create_time) - create_float) < 2.0:
                continue
        candidates.append((pid_int, create_float))

    if len(candidates) != 1:
        _log_claim_warning(
            logger,
            "[WORD_PID_CLAIM] unable to claim unique WINWORD reason=%r before=%r after=%r candidates=%r diag=%r",
            reason,
            _candidate_summary(before or {}),
            _candidate_summary(after),
            sorted(candidates),
            diag,
        )
        return None

    return candidates[0]


def try_claim_word_process_for_engine(
    engine,
    *,
    before_snapshot: dict[int, float] | None = None,
    min_create_time: float | None = None,
    diag: dict | None = None,
    reason: str = "",
) -> bool:
    try:
        if getattr(engine, "_owned_pid", None):
            return True
    except Exception:
        return False

    app_obj = getattr(engine, "app", None)
    if app_obj is None:
        return False

    if diag is None:
        try:
            diag = collect_word_app_diag(app_obj)
        except Exception:
            diag = None

    if is_wps_runtime_diag(diag):
        _log_claim_warning(getattr(engine, "_logger", None), "[WORD_PID_CLAIM] skipped WPS runtime diag reason=%r diag=%r", reason, diag)
        return False

    pid = None
    try:
        pid = diag.get("PID") if isinstance(diag, dict) else None
    except Exception:
        pid = None
    if pid is not None:
        try:
            claimed_pid = int(pid)
            create_time = _safe_process_create_time(claimed_pid)
        except Exception:
            claimed_pid = None
            create_time = None
        if claimed_pid is not None:
            engine._owned_pid = claimed_pid
            engine._owned_create_time = create_time
            try:
                _register_office_process(int(claimed_pid), create_time)
            except Exception:
                pass
            try:
                engine._logger.info(
                    "[WORD_PID_CLAIM] claimed from COM diag reason=%r pid=%r create_time=%r",
                    reason,
                    claimed_pid,
                    create_time,
                )
            except Exception:
                pass
            return True

    claimed = find_claimable_winword_process(
        before_snapshot=before_snapshot,
        min_create_time=min_create_time,
        diag=diag,
        reason=reason,
        logger=getattr(engine, "_logger", None),
    )
    if claimed is None:
        return False

    claimed_pid, create_time = claimed
    engine._owned_pid = int(claimed_pid)
    engine._owned_create_time = float(create_time)
    try:
        _register_office_process(int(claimed_pid), float(create_time))
    except Exception:
        pass
    try:
        engine._logger.info(
            "[WORD_PID_CLAIM] claimed unique WINWORD reason=%r pid=%r create_time=%r diag=%r",
            reason,
            claimed_pid,
            create_time,
            diag,
        )
    except Exception:
        pass
    return True


__all__ = [
    "WINWORD_PROCESS_NAME",
    "find_claimable_winword_process",
    "snapshot_winword_processes",
    "try_claim_word_process_for_engine",
]
