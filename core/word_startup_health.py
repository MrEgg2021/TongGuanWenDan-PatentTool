from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import os
import subprocess
import tempfile
import time

import psutil
import win32com.client

from core.logging_utils import logger
from core.word_engine_impl.com_compat import add_hidden_document
from core.word_engine_impl.owned_process_claim import find_claimable_winword_process, snapshot_winword_processes
from core.word_engine_impl.registry_probe import find_first_winword_exe
from core.word_engine_impl.word_com_resolver import dispatch_word_via_com, get_active_word_via_com, is_wps_runtime_diag


@dataclass(frozen=True)
class WordStartupHealthResult:
    ok: bool
    pid: int | None
    binding_progid: str | None
    error: str | None
    killed_before_check: bool
    reason_code: str = ""
    user_message: str = ""
    technical_detail: str = ""
    pdf_export_ok: bool | None = None
    pdf_export_error: str = ""


ProgressCallback = Callable[[str, dict], None]


def _emit_progress(progress_callback: ProgressCallback | None, stage: str, **payload) -> None:
    if progress_callback is None:
        return
    try:
        progress_callback(str(stage), dict(payload))
    except Exception:
        pass


def _with_kill_context(message: str, *, killed_before_check: bool) -> str:
    if not killed_before_check:
        return message
    return (
        message
        + "\n\n本轮已经执行过强制结束进程，Office/WPS 可能处于异常状态。"
        + "建议重启 Windows，或修复 Word/WPS 后再重新转换。"
    )


def _result_failure(
    message: str,
    *,
    pid: int | None = None,
    binding_progid: str | None = None,
    killed_before_check: bool,
    reason_code: str,
    user_message: str | None = None,
    technical_detail: str | None = None,
) -> WordStartupHealthResult:
    full_message = _with_kill_context(message, killed_before_check=killed_before_check)
    display_message = str(user_message or full_message)
    if killed_before_check and "Office/WPS 可能处于异常状态" not in display_message:
        display_message = _with_kill_context(display_message, killed_before_check=True)
    return WordStartupHealthResult(
        ok=False,
        pid=pid,
        binding_progid=binding_progid,
        error=full_message,
        killed_before_check=bool(killed_before_check),
        reason_code=str(reason_code or ""),
        user_message=display_message,
        technical_detail=str(technical_detail or message),
    )


def _start_word_process(winword_exe: str):
    startupinfo = None
    creationflags = 0
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
    except Exception:
        startupinfo = None
    try:
        creationflags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception:
        creationflags = 0
    return subprocess.Popen(
        [winword_exe, "/a", "/q"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        startupinfo=startupinfo,
        creationflags=creationflags,
    )


def _terminate_started_process(started_proc) -> None:
    if started_proc is None:
        return
    try:
        started_proc.terminate()
    except Exception:
        pass


def _quit_app_quietly(app_obj) -> None:
    if app_obj is None:
        return
    try:
        app_obj.Quit(SaveChanges=0)
    except Exception:
        pass


def _diag_pid(diag: dict | None) -> int | None:
    try:
        if isinstance(diag, dict) and diag.get("PID") is not None:
            return int(diag.get("PID"))
    except Exception:
        return None
    return None


def _word_version(app_obj) -> float | None:
    try:
        raw_version = getattr(app_obj, "Version", None)
    except Exception:
        return None
    try:
        return float(str(raw_version).split()[0])
    except (TypeError, ValueError):
        return None


def _runtime_detail(*, stage: str, info: dict | None, diag: dict | None, version: float | None, extra: object = None) -> str:
    payload = {
        "stage": str(stage),
        "binding_source": (info or {}).get("binding_source") if isinstance(info, dict) else None,
        "binding_progid": (info or {}).get("binding_progid") if isinstance(info, dict) else None,
        "attempted_progids": (info or {}).get("attempted_progids") if isinstance(info, dict) else None,
        "word_version": version,
        "diag": diag,
        "is_wps": is_wps_runtime_diag(diag),
    }
    if extra is not None:
        payload["extra"] = repr(extra)
    return repr(payload)


def _wait_for_pid(pid: int | None):
    if pid is None:
        return None
    try:
        return psutil.Process(int(pid))
    except psutil.NoSuchProcess:
        return None


def _probe_word_pdf_export(app_obj) -> tuple[bool, str]:
    try:
        with tempfile.TemporaryDirectory(prefix="cpc_word_pdf_probe_") as temp_dir:
            pdf_path = os.path.join(temp_dir, "word_pdf_probe.pdf")
            document = add_hidden_document(app_obj, logger=logger)
            try:
                document.Range(0, 0).Text = "Word PDF export capability check"
                document.ExportAsFixedFormat(OutputFileName=pdf_path, ExportFormat=17)
                if not os.path.isfile(pdf_path):
                    return False, "Word PDF export did not create an output file"
                with open(pdf_path, "rb") as pdf_file:
                    if pdf_file.read(5) != b"%PDF-":
                        return False, "Word PDF export created an invalid PDF file"
                return True, ""
            finally:
                try:
                    document.Close(SaveChanges=0)
                except Exception:
                    pass
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def _bind_active_word_until_ready(*, bind_timeout: float, poll_interval: float) -> tuple[object | None, dict, Exception | None]:
    deadline = time.monotonic() + max(0.1, float(bind_timeout))
    last_error = None
    while True:
        try:
            app_obj, info = get_active_word_via_com(client=win32com.client)
            return app_obj, info, None
        except Exception as exc:
            last_error = exc
            if time.monotonic() >= deadline:
                return None, {}, last_error
            time.sleep(max(0.05, float(poll_interval)))


def _wait_for_started_word_exit(
    started_proc,
    *,
    pid: int | None,
    exit_timeout: float,
    slow_exit_timeout: float,
    progress_callback: ProgressCallback | None,
) -> bool:
    fast_exit_timeout = max(0.0, float(exit_timeout))
    max_exit_timeout = max(fast_exit_timeout, float(slow_exit_timeout))
    _emit_progress(progress_callback, "wait_exit", pid=pid, timeout=fast_exit_timeout)
    try:
        started_proc.wait(timeout=fast_exit_timeout)
        return False
    except Exception as first_wait_exc:
        slow_remaining = max(0.0, max_exit_timeout - fast_exit_timeout)
        if slow_remaining <= 0:
            raise
        _emit_progress(
            progress_callback,
            "slow_exit_wait",
            pid=pid,
            timeout=slow_remaining,
            fast_timeout=fast_exit_timeout,
        )
        try:
            started_proc.wait(timeout=slow_remaining)
        except Exception as exc:
            raise TimeoutError(f"fast wait failed: {first_wait_exc!r}; slow wait failed: {exc!r}") from exc
        return True


def _finish_bound_word_health(
    app_obj,
    info: dict,
    *,
    result_pid: int | None,
    expected_pid: int | None,
    wait_target,
    killed_before_check: bool,
    exit_timeout: float,
    slow_exit_timeout: float,
    progress_callback: ProgressCallback | None,
    check_pdf_export: bool = False,
) -> WordStartupHealthResult:
    binding_progid = str(info.get("binding_progid") or "") or None
    diag = info.get("last_diag") if isinstance(info, dict) else None
    version = _word_version(app_obj)
    detail = _runtime_detail(stage="bound", info=info, diag=diag, version=version)

    if is_wps_runtime_diag(diag):
        _quit_app_quietly(app_obj)
        _terminate_started_process(wait_target)
        return _result_failure(
            "Word 启动健康检查绑定到了 WPS，而不是 Microsoft Word。",
            pid=result_pid,
            binding_progid=binding_progid,
            killed_before_check=killed_before_check,
            reason_code="com_bound_to_wps",
            user_message="Word 启动检查未通过。当前连接到了 WPS，而不是 Microsoft Word。",
            technical_detail=detail,
        )

    if version is not None and version < 12.0:
        try:
            app_obj.Quit(SaveChanges=0)
        except Exception:
            pass
        _terminate_started_process(wait_target)
        return _result_failure(
            f"当前工具最低仅支持 Word 2007 及以上版本（检测到版本号: {version}）。",
            pid=result_pid,
            binding_progid=binding_progid,
            killed_before_check=killed_before_check,
            reason_code="word_version_unsupported",
            user_message="当前工具最低仅支持 Word 2007 及以上版本，请升级 Microsoft Word 后再转换。",
            technical_detail=detail,
        )

    bound_pid = _diag_pid(diag)
    if expected_pid is not None and bound_pid is not None and bound_pid != int(expected_pid):
        _quit_app_quietly(app_obj)
        _terminate_started_process(wait_target)
        return _result_failure(
            f"Word COM 绑定 PID 与本次启动 PID 不一致：started={expected_pid}, bound={bound_pid}",
            pid=result_pid,
            binding_progid=binding_progid,
            killed_before_check=killed_before_check,
            reason_code="unexpected_word_pid",
            user_message="Word 启动检查未通过。工具连接到的 Word 进程与本次启动的进程不一致。",
            technical_detail=detail,
        )

    pdf_export_ok = None
    pdf_export_error = ""
    if check_pdf_export:
        _emit_progress(progress_callback, "test_pdf_export", pid=result_pid, binding_progid=binding_progid)
        pdf_export_ok, pdf_export_error = _probe_word_pdf_export(app_obj)
        logger.info(
            "[WORD_PDF_EXPORT_PROBE] ok=%r error=%r",
            pdf_export_ok,
            pdf_export_error,
        )

    try:
        _emit_progress(progress_callback, "quit_word", pid=result_pid, binding_progid=binding_progid)
        app_obj.Quit(SaveChanges=0)
    except Exception as exc:
        _terminate_started_process(wait_target)
        return _result_failure(
            f"Word COM Quit 失败：{exc}",
            pid=result_pid,
            binding_progid=binding_progid,
            killed_before_check=killed_before_check,
            reason_code="word_quit_failed",
            user_message="Word 启动检查未通过。工具无法正常关闭测试启动的 Word。",
            technical_detail=_runtime_detail(stage="quit_failed", info=info, diag=diag, version=version, extra=exc),
        )

    if wait_target is None:
        result = WordStartupHealthResult(
            ok=True,
            pid=result_pid,
            binding_progid=binding_progid,
            error=None,
            killed_before_check=bool(killed_before_check),
            reason_code="",
            user_message="",
            technical_detail=detail,
            pdf_export_ok=pdf_export_ok,
            pdf_export_error=pdf_export_error,
        )
        _emit_progress(progress_callback, "done", ok=True, reason_code=result.reason_code)
        return result

    try:
        slow_exit_recovered = _wait_for_started_word_exit(
            wait_target,
            pid=result_pid,
            exit_timeout=exit_timeout,
            slow_exit_timeout=slow_exit_timeout,
            progress_callback=progress_callback,
        )
        if slow_exit_recovered:
            result = WordStartupHealthResult(
                ok=True,
                pid=result_pid,
                binding_progid=binding_progid,
                error=None,
                killed_before_check=bool(killed_before_check),
                reason_code="slow_word_exit_recovered",
                user_message="",
                technical_detail=detail + f"; slow exit recovered after fast timeout {float(exit_timeout):.1f}s",
                pdf_export_ok=pdf_export_ok,
                pdf_export_error=pdf_export_error,
            )
            _emit_progress(progress_callback, "done", ok=True, reason_code=result.reason_code)
            return result
    except Exception as exc:
        _terminate_started_process(wait_target)
        return _result_failure(
            f"Word 启动后未能在超时时间内正常退出：{exc}",
            pid=result_pid,
            binding_progid=binding_progid,
            killed_before_check=killed_before_check,
            reason_code="word_exit_failed",
            user_message="Word 启动检查未通过。工具无法确认 Word 能正常退出。",
            technical_detail=_runtime_detail(stage="exit_failed", info=info, diag=diag, version=version, extra=exc),
        )

    result = WordStartupHealthResult(
        ok=True,
        pid=result_pid,
        binding_progid=binding_progid,
        error=None,
        killed_before_check=bool(killed_before_check),
        reason_code="",
        user_message="",
        technical_detail=detail,
        pdf_export_ok=pdf_export_ok,
        pdf_export_error=pdf_export_error,
    )
    _emit_progress(progress_callback, "done", ok=True, reason_code=result.reason_code)
    return result


def check_word_startup_health(
    *,
    killed_before_check: bool = False,
    bind_timeout: float = 10.0,
    poll_interval: float = 0.25,
    exit_timeout: float = 8.0,
    slow_exit_timeout: float = 25.0,
    progress_callback: ProgressCallback | None = None,
    check_pdf_export: bool = False,
) -> WordStartupHealthResult:
    _emit_progress(progress_callback, "bind_com")
    dispatch_app_obj = None
    dispatch_info: dict = {}
    dispatch_before_snapshot = snapshot_winword_processes()
    try:
        dispatch_start_ts = float(time.time())
    except Exception:
        dispatch_start_ts = None
    try:
        dispatch_app_obj, dispatch_info = dispatch_word_via_com(client=win32com.client)
    except Exception as exc:
        dispatch_info = {"binding_source": "", "binding_progid": "", "attempted_progids": [], "last_error": exc}

    if dispatch_app_obj is not None:
        diag = dispatch_info.get("last_diag") if isinstance(dispatch_info, dict) else None
        dispatch_pid = _diag_pid(diag)
        claimed_pid = dispatch_pid
        if dispatch_pid is None:
            try:
                logger.warning(
                    "[WORD_HEALTH_PID_MISSING] before=%r min_create_time=%r diag=%r",
                    dispatch_before_snapshot,
                    dispatch_start_ts,
                    diag,
                )
            except Exception:
                pass
            claimed = find_claimable_winword_process(
                before_snapshot=dispatch_before_snapshot,
                min_create_time=dispatch_start_ts,
                diag=diag,
                reason="word_startup_health_dispatch",
                logger=logger,
            )
            if claimed is None:
                _quit_app_quietly(dispatch_app_obj)
                return _result_failure(
                    "Word COM 诊断未返回 PID，且无法唯一确认本次启动的 Microsoft Word 进程。",
                    pid=None,
                    binding_progid=str(dispatch_info.get("binding_progid") or "") or None,
                    killed_before_check=killed_before_check,
                    reason_code="word_pid_missing_unclaimed",
                    user_message="Word 启动检查未通过。工具无法确认本次启动的 Word 进程，请关闭后台 Word/WPS 后重试。",
                    technical_detail=_runtime_detail(
                        stage="dispatch_pid_missing_unclaimed",
                        info=dispatch_info,
                        diag=diag,
                        version=_word_version(dispatch_app_obj),
                        extra={
                            "before_snapshot": dispatch_before_snapshot,
                            "dispatch_start_ts": dispatch_start_ts,
                        },
                    ),
                )
            claimed_pid = int(claimed[0])
        return _finish_bound_word_health(
            dispatch_app_obj,
            dispatch_info,
            result_pid=claimed_pid,
            expected_pid=None,
            wait_target=_wait_for_pid(claimed_pid),
            killed_before_check=killed_before_check,
            exit_timeout=exit_timeout,
            slow_exit_timeout=slow_exit_timeout,
            progress_callback=progress_callback,
            check_pdf_export=check_pdf_export,
        )

    _emit_progress(progress_callback, "locate_word")
    winword_exe = find_first_winword_exe()
    if not winword_exe:
        last_diag = dispatch_info.get("last_diag") if isinstance(dispatch_info, dict) else None
        if is_wps_runtime_diag(last_diag):
            return _result_failure(
                "Word 启动健康检查只能绑定到 WPS，未发现可用的 Microsoft Word。",
                killed_before_check=killed_before_check,
                reason_code="com_bound_to_wps",
                user_message="Word 启动检查未通过。当前连接到了 WPS，而不是 Microsoft Word。",
                technical_detail=_runtime_detail(stage="dispatch_only_wps", info=dispatch_info, diag=last_diag, version=None),
            )
        return _result_failure(
            "未能定位 WINWORD.EXE，无法确认 Microsoft Word 是否可正常启动。",
            killed_before_check=killed_before_check,
            reason_code="word_not_found",
            user_message="未检测到可用的 Microsoft Word，请确认已安装 Microsoft Word 后再转换。",
            technical_detail=_runtime_detail(
                stage="word_not_found",
                info=dispatch_info,
                diag=last_diag,
                version=None,
                extra=dispatch_info.get("last_error") if isinstance(dispatch_info, dict) else None,
            ),
        )

    started_proc = None
    app_obj = None
    started_pid = None
    try:
        _emit_progress(progress_callback, "start_word", winword_exe=str(winword_exe))
        started_proc = _start_word_process(str(winword_exe))
        started_pid = int(getattr(started_proc, "pid", 0) or 0) or None
    except Exception as exc:
        return _result_failure(
            f"启动 WINWORD.EXE 失败：{exc}",
            killed_before_check=killed_before_check,
            reason_code="word_start_failed",
            user_message="Word 启动检查未通过。工具无法启动 Microsoft Word，请关闭后台 Office/WPS 后重试。",
            technical_detail=repr(exc),
        )

    try:
        _emit_progress(progress_callback, "bind_com", pid=started_pid)
        app_obj, info, bind_error = _bind_active_word_until_ready(
            bind_timeout=bind_timeout,
            poll_interval=poll_interval,
        )
        if app_obj is None:
            _terminate_started_process(started_proc)
            last_diag = info.get("last_diag") if isinstance(info, dict) else None
            return _result_failure(
                f"未能绑定到本次启动的 Microsoft Word COM 实例：{bind_error}",
                pid=started_pid,
                binding_progid=str(info.get("binding_progid") or "") or None,
                killed_before_check=killed_before_check,
                reason_code="com_bind_failed",
                user_message="Word 启动检查未通过。工具暂时无法连接 Microsoft Word。",
                technical_detail=_runtime_detail(stage="manual_bind_failed", info=info, diag=last_diag, version=None, extra=bind_error),
            )

        result = _finish_bound_word_health(
            app_obj,
            info,
            result_pid=started_pid,
            expected_pid=started_pid,
            wait_target=started_proc,
            killed_before_check=killed_before_check,
            exit_timeout=exit_timeout,
            slow_exit_timeout=slow_exit_timeout,
            progress_callback=progress_callback,
            check_pdf_export=check_pdf_export,
        )
        app_obj = None
        return result
    finally:
        if app_obj is not None:
            try:
                app_obj.Quit(SaveChanges=0)
            except Exception:
                pass


def check_word_pdf_export_health(**kwargs) -> WordStartupHealthResult:
    return check_word_startup_health(check_pdf_export=True, **kwargs)


__all__ = ["WordStartupHealthResult", "check_word_pdf_export_health", "check_word_startup_health"]
