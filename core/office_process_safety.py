from __future__ import annotations

from dataclasses import dataclass, field

import psutil

from core.word_engine_impl.process_registry import _load_office_process_registry
from core.word_engine_impl.window_probe import _visible_window_pids


OFFICE_PROCESS_NAMES = {"winword.exe", "wps.exe", "et.exe", "wpp.exe"}
IGNORED_OFFICE_SERVICE_NAMES = {
    "officeclicktorun.exe",
    "ksolaunch.exe",
    "wpscloudsvr.exe",
    "wpscenter.exe",
    "wpsupdate.exe",
    "wpscloudlaunch.exe",
}


@dataclass(frozen=True)
class OfficeProcessInfo:
    name: str
    pid: int
    exe: str | None
    create_time: float | None
    visible: bool | None
    owned: bool
    app_family: str

    def display_line(self) -> str:
        parts = [f"{self.name} (PID={self.pid})"]
        if self.exe:
            parts.append(f"路径：{self.exe}")
        if self.visible is not None:
            parts.append("可见窗口：是" if self.visible else "可见窗口：否")
        if self.owned:
            parts.append("来源：本工具残留")
        return " | ".join(parts)


@dataclass(frozen=True)
class ProcessTerminationResult:
    terminated: list[int] = field(default_factory=list)
    killed: list[int] = field(default_factory=list)
    remaining: list[OfficeProcessInfo] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class OfficeProcessClassification:
    visible_document_sessions: list[OfficeProcessInfo] = field(default_factory=list)
    hidden_background_document_hosts: list[OfficeProcessInfo] = field(default_factory=list)
    owned_residuals: list[OfficeProcessInfo] = field(default_factory=list)
    ignored_background_services: list[OfficeProcessInfo] = field(default_factory=list)


def _app_family(name: str) -> str:
    lname = str(name or "").lower()
    if lname == "winword.exe":
        return "word"
    if lname == "wps.exe":
        return "wps"
    if lname == "et.exe":
        return "et"
    if lname == "wpp.exe":
        return "wpp"
    return "office"


def _process_info_from_proc(proc, *, visible_pids: set[int] | None, owned_keys: set[tuple[int, int]]) -> OfficeProcessInfo | None:
    try:
        name = str(proc.info.get("name") or "")
        pid = int(proc.info.get("pid"))
    except Exception:
        return None

    exe = None
    create_time = None
    try:
        exe_val = proc.info.get("exe")
        exe = str(exe_val) if exe_val else None
    except Exception:
        exe = None
    try:
        create_time = float(proc.info.get("create_time"))
    except Exception:
        create_time = None

    visible = None
    if visible_pids is not None:
        visible = int(pid) in visible_pids

    return OfficeProcessInfo(
        name=name,
        pid=pid,
        exe=exe,
        create_time=create_time,
        visible=visible,
        owned=_is_owned_winword(pid, create_time, name, owned_keys),
        app_family=_app_family(name),
    )


def _owned_registry_keys() -> set[tuple[int, int]]:
    try:
        _path, items = _load_office_process_registry()
    except Exception:
        items = []
    keys: set[tuple[int, int]] = set()
    for item in items or []:
        try:
            pid = int(item.get("pid"))
            ct = float(item.get("create_time"))
        except Exception:
            continue
        keys.add((pid, int(round(ct))))
    return keys


def _is_owned_winword(pid: int, create_time: float | None, name: str, owned_keys: set[tuple[int, int]]) -> bool:
    if str(name or "").lower() != "winword.exe" or create_time is None:
        return False
    try:
        return (int(pid), int(round(float(create_time)))) in owned_keys
    except Exception:
        return False


def _is_hidden_wps_qing_browser_helper(proc, item: OfficeProcessInfo) -> bool:
    if item.visible is not False or item.name.lower() != "wps.exe":
        return False
    try:
        cmdline = proc.info.get("cmdline") or []
        if isinstance(cmdline, str):
            command = cmdline.lower()
        else:
            command = " ".join(str(part) for part in cmdline).lower()
    except Exception:
        return False
    return "jsapibrowser.dll" in command and "--from=qing" in command


def scan_office_processes() -> list[OfficeProcessInfo]:
    classified = classify_office_processes()
    return (
        list(classified.visible_document_sessions)
        + list(classified.hidden_background_document_hosts)
        + list(classified.owned_residuals)
    )


def classify_office_processes() -> OfficeProcessClassification:
    owned_keys = _owned_registry_keys()
    try:
        visible_pids = _visible_window_pids()
    except Exception:
        visible_pids = None

    visible_document_sessions: list[OfficeProcessInfo] = []
    hidden_background_hosts: list[OfficeProcessInfo] = []
    owned_residuals: list[OfficeProcessInfo] = []
    ignored_services: list[OfficeProcessInfo] = []

    try:
        processes = psutil.process_iter(["pid", "name", "exe", "create_time", "cmdline"])
    except Exception:
        return OfficeProcessClassification()

    for proc in processes:
        try:
            name = str(proc.info.get("name") or "")
            lname = name.lower()
        except Exception:
            continue
        if lname not in OFFICE_PROCESS_NAMES and lname not in IGNORED_OFFICE_SERVICE_NAMES:
            continue

        item = _process_info_from_proc(proc, visible_pids=visible_pids, owned_keys=owned_keys)
        if item is None:
            continue
        if lname in IGNORED_OFFICE_SERVICE_NAMES:
            ignored_services.append(item)
            continue
        if _is_hidden_wps_qing_browser_helper(proc, item):
            ignored_services.append(item)
            continue
        if item.owned:
            owned_residuals.append(item)
            continue
        if item.visible is False:
            hidden_background_hosts.append(item)
        else:
            visible_document_sessions.append(item)

    return OfficeProcessClassification(
        visible_document_sessions=visible_document_sessions,
        hidden_background_document_hosts=hidden_background_hosts,
        owned_residuals=owned_residuals,
        ignored_background_services=ignored_services,
    )


def blocking_office_processes() -> list[OfficeProcessInfo]:
    """Return visible external Office document sessions that require user action."""
    return classify_office_processes().visible_document_sessions


def hidden_background_document_hosts() -> list[OfficeProcessInfo]:
    return classify_office_processes().hidden_background_document_hosts


def external_document_hosts() -> list[OfficeProcessInfo]:
    classified = classify_office_processes()
    return list(classified.visible_document_sessions) + list(classified.hidden_background_document_hosts)


def terminate_office_processes(
    items: list[OfficeProcessInfo],
    *,
    allow_kill: bool = False,
    terminate_timeout: float = 3.0,
) -> ProcessTerminationResult:
    terminated: list[int] = []
    killed: list[int] = []
    remaining: list[OfficeProcessInfo] = []
    errors: list[str] = []

    for item in list(items or []):
        try:
            process = psutil.Process(int(item.pid))
            process.terminate()
            terminated.append(int(item.pid))
            try:
                process.wait(timeout=float(terminate_timeout))
                continue
            except Exception:
                if not allow_kill:
                    remaining.append(item)
                    continue
                process.kill()
                killed.append(int(item.pid))
                try:
                    process.wait(timeout=float(terminate_timeout))
                except Exception:
                    remaining.append(item)
        except Exception as exc:
            remaining.append(item)
            errors.append(f"{item.name} (PID={item.pid}): {exc}")

    return ProcessTerminationResult(
        terminated=terminated,
        killed=killed,
        remaining=remaining,
        errors=errors,
    )


__all__ = [
    "OFFICE_PROCESS_NAMES",
    "IGNORED_OFFICE_SERVICE_NAMES",
    "OfficeProcessClassification",
    "OfficeProcessInfo",
    "ProcessTerminationResult",
    "blocking_office_processes",
    "classify_office_processes",
    "external_document_hosts",
    "hidden_background_document_hosts",
    "scan_office_processes",
    "terminate_office_processes",
]
