import subprocess
import time

import psutil
import win32com.client

from core.office_process_safety import external_document_hosts, scan_office_processes

from ..process_registry import _register_office_process, _unregister_office_process
from ..process_utils import _safe_process_create_time
from ..owned_process_claim import snapshot_winword_processes, try_claim_word_process_for_engine
from ..registry_probe import find_first_winword_exe
from ..word_com_resolver import collect_word_app_diag, dispatch_word_via_com, get_active_word_via_com, is_wps_runtime_diag


def start_app_dispatch_flow(engine, append_word_startup_faq):
    """启动 Word 进程 (静默模式)"""
    try:
        foreign = external_document_hosts()

        if foreign:
            try:
                lines = [item.display_line() for item in foreign[:20]]
                more = ""
                if len(foreign) > 20:
                    more = f"\n... 还有 {len(foreign) - 20} 个进程未列出"
                detail = "\n".join(lines) + more
            except Exception:
                detail = ""
            msg = (
                "检测到系统中存在未被本工具认领的 Word/WPS 文档进程。为避免误操作或影响用户文档，本工具不会自动关闭它们。\n\n"
                "请先关闭所有 Word/WPS 文档窗口和后台进程，或重启 Windows 后再重试。"
            )
            if detail.strip():
                msg = msg + "\n\n检测到的进程：\n" + detail
            raise RuntimeError(append_word_startup_faq(msg))

        engine.clean_zombie_processes()

        engine._logger.info("🚀 正在启动 Word 进程...")

        def _post_start_setup(
            *,
            started_pid=None,
            started_ct=None,
            before_snapshot: dict[int, float] | None = None,
            min_create_time: float | None = None,
        ):
            try:
                engine._app_start_before_snapshot = dict(before_snapshot) if before_snapshot is not None else None
            except Exception:
                engine._app_start_before_snapshot = None
            try:
                engine._app_start_min_create_time = float(min_create_time) if min_create_time is not None else None
            except Exception:
                engine._app_start_min_create_time = None
            try:
                engine._app_started_ts = float(time.time())
            except Exception:
                engine._app_started_ts = 0.0
            engine._visible_true_since_ts = None

            try:
                engine.app.Visible = engine.config.get("visible", False)
                engine.app.DisplayAlerts = engine.config.get("display_alerts", 0)
                engine.app.ScreenUpdating = engine.config.get("screen_updating", False)
            except Exception:
                pass

            try:
                engine.app.AutomationSecurity = 3
            except Exception:
                pass
            try:
                engine.app.Options.SaveNormalPrompt = False
            except Exception:
                pass
            try:
                engine.app.NormalTemplate.Saved = True
            except Exception:
                pass

            try:
                version_str = str(engine.app.Version)
                engine._logger.info(f"📦 检测到 Word 版本: {version_str}")
                try:
                    engine.version = float(version_str)
                except (TypeError, ValueError):
                    engine.version = None
            except Exception as ve:
                engine._logger.warning(f"⚠️ 获取 Word 版本号失败: {ve}")
                engine.version = None

            if getattr(engine, "version", None) is not None and engine.version < 12.0:
                msg = (
                    f"当前工具最低仅支持 Word 2007 及以上版本（检测到版本号: {engine.version}），"
                    "请升级 Word 后再使用本工具。"
                )
                engine._logger.error(msg)
                raise RuntimeError(append_word_startup_faq(msg))

            diag = None
            try:
                diag = collect_word_app_diag(engine.app)
                engine._logger.info(
                    "[WORD_COM] Path=%r Hwnd=%r PID=%r ProcExe=%r",
                    diag.get("Path") if isinstance(diag, dict) else None,
                    diag.get("Hwnd") if isinstance(diag, dict) else None,
                    diag.get("PID") if isinstance(diag, dict) else None,
                    diag.get("ProcExe") if isinstance(diag, dict) else None,
                )
            except Exception:
                diag = None

            pid = None
            try:
                pid = diag.get("PID") if isinstance(diag, dict) else None
            except Exception:
                pid = None
            effective_pid = None
            try:
                if pid is not None:
                    effective_pid = int(pid)
            except Exception:
                effective_pid = None
            if effective_pid is None and started_pid is not None:
                try:
                    effective_pid = int(started_pid)
                except Exception:
                    effective_pid = None

            if effective_pid is not None:
                engine._owned_pid = effective_pid
                if started_pid is not None and effective_pid == int(started_pid) and started_ct is not None:
                    try:
                        engine._owned_create_time = float(started_ct)
                    except Exception:
                        engine._owned_create_time = None
                else:
                    try:
                        engine._owned_create_time = _safe_process_create_time(int(effective_pid))
                    except Exception:
                        engine._owned_create_time = None
                try:
                    _register_office_process(int(engine._owned_pid), engine._owned_create_time)
                except Exception:
                    pass
            else:
                try:
                    engine._logger.warning(
                        "[WORD_PID_MISSING] COM diagnostics did not expose a PID; trying conservative claim. before=%r min_create_time=%r diag=%r",
                        before_snapshot,
                        min_create_time,
                        diag,
                    )
                except Exception:
                    pass
                if not try_claim_word_process_for_engine(
                    engine,
                    before_snapshot=before_snapshot,
                    min_create_time=min_create_time,
                    diag=diag,
                    reason="post_start_setup",
                ):
                    raise RuntimeError(
                        append_word_startup_faq(
                            "Word COM 已绑定，但工具无法确认本次启动的 WINWORD.EXE 进程。"
                            "请关闭后台 Word/WPS 进程后重试。"
                        )
                    )

            engine._logger.info(
                f"✅ Word 进程启动成功 (PID: {engine._owned_pid if engine._owned_pid else 'Unknown'})"
            )

        before_dispatch_snapshot = snapshot_winword_processes()
        try:
            dispatch_start_ts = float(time.time())
        except Exception:
            dispatch_start_ts = None
        app_obj, dispatch_info = dispatch_word_via_com(client=win32com.client)
        if app_obj is not None:
            try:
                engine._logger.info(
                    "[WORD_COM_BIND] source=%r progid=%r attempted=%r last_diag=%r",
                    dispatch_info.get("binding_source"),
                    dispatch_info.get("binding_progid"),
                    dispatch_info.get("attempted_progids"),
                    dispatch_info.get("last_diag"),
                )
            except Exception:
                pass
            engine.app = app_obj
            _post_start_setup(
                before_snapshot=before_dispatch_snapshot,
                min_create_time=dispatch_start_ts,
            )
            return
        try:
            engine._logger.warning(
                "[WORD_COM_BIND] default COM unavailable or unsuitable. attempted=%r last_diag=%r last_error=%r",
                dispatch_info.get("attempted_progids"),
                dispatch_info.get("last_diag"),
                dispatch_info.get("last_error"),
            )
        except Exception:
            pass

        winword_exe = find_first_winword_exe()
        if not winword_exe:
            raise RuntimeError(append_word_startup_faq("未能定位 WINWORD.EXE 路径，请确认已正确安装 Microsoft Word。"))

        started_proc = None
        started_pid = None
        started_ct = None
        before_popen_snapshot = snapshot_winword_processes()
        try:
            popen_start_ts = float(time.time())
        except Exception:
            popen_start_ts = None
        try:
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
            started_proc = subprocess.Popen(
                [winword_exe, "/a", "/q"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                startupinfo=startupinfo,
                creationflags=creationflags,
                close_fds=True,
            )
            started_pid = int(getattr(started_proc, "pid", 0) or 0)
            if started_pid <= 0:
                raise RuntimeError(append_word_startup_faq("启动 WINWORD.EXE 失败：无法获取进程 PID"))
            try:
                started_ct = _safe_process_create_time(started_pid)
            except Exception:
                started_ct = None
        except Exception:
            started_proc = None
            started_pid = None
            started_ct = None
            raise

        def _hide_pid_windows(pid: int) -> None:
            try:
                import win32gui
                import win32process
                import win32con
            except Exception:
                return

            def _cb(hwnd, _param):
                try:
                    try:
                        if not win32gui.IsWindow(hwnd):
                            return True
                    except Exception:
                        return True
                    try:
                        _tid, wpid = win32process.GetWindowThreadProcessId(hwnd)
                    except Exception:
                        return True
                    if int(wpid or 0) != int(pid):
                        return True
                    try:
                        win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
                    except Exception:
                        pass
                except Exception:
                    return True
                return True

            try:
                win32gui.EnumWindows(_cb, None)
            except Exception:
                return

        try:
            if started_pid is not None:
                _hide_pid_windows(int(started_pid))
        except Exception:
            pass

        def _collect_word_com_diag(app_obj):
            diag = collect_word_app_diag(app_obj)
            engine._logger.info(
                "[WORD_COM] Name=%r Version=%r Build=%r Path=%r OS=%r Hwnd=%r PID=%r ProcName=%r ProcExe=%r",
                diag.get("Name"),
                getattr(app_obj, "Version", None),
                getattr(app_obj, "Build", None),
                diag.get("Path"),
                getattr(app_obj, "OperatingSystem", None),
                diag.get("Hwnd"),
                diag.get("PID"),
                diag.get("ProcName"),
                diag.get("ProcExe"),
            )
            return diag

        def _is_wps_diag(diag):
            return is_wps_runtime_diag(diag)

        bind_deadline = time.time() + 15.0
        last_bind_error = None
        app_obj = None
        first_active_obj_ts = None
        while time.time() < bind_deadline:
            foreign_runtime = [
                (item.name.lower(), item.pid)
                for item in scan_office_processes()
                if item.pid != started_pid
            ]

            if foreign_runtime:
                try:
                    p = psutil.Process(int(started_pid))
                    p.terminate()
                except Exception:
                    pass
                raise RuntimeError(
                    append_word_startup_faq(
                        "检测到未被本工具认领的 Word/WPS 进程，可能是历史残留、其他程序启动或用户新开。"
                        "该状态会影响本工具的安全与产出正确性，请关闭所有 Word/WPS 后重试。"
                    )
                )

            try:
                if started_pid is not None:
                    _hide_pid_windows(int(started_pid))
            except Exception:
                pass

            try:
                app_obj, _active_info = get_active_word_via_com(client=win32com.client)
            except Exception as e:
                last_bind_error = e
                time.sleep(0.2)
                continue

            if first_active_obj_ts is None:
                try:
                    first_active_obj_ts = float(time.time())
                except Exception:
                    first_active_obj_ts = 0.0

            try:
                diag = _collect_word_com_diag(app_obj)
            except Exception:
                diag = None

            pid = None
            try:
                pid = diag.get("PID") if isinstance(diag, dict) else None
            except Exception:
                pid = None

            if pid is not None and started_pid is not None and int(pid) == int(started_pid):
                if diag and _is_wps_diag(diag):
                    try:
                        app_obj.Quit(SaveChanges=0)
                    except Exception:
                        pass
                    app_obj = None
                    break
                engine.app = app_obj
                try:
                    engine.app.Visible = engine.config.get("visible", False)
                    engine.app.DisplayAlerts = engine.config.get("display_alerts", 0)
                    engine.app.ScreenUpdating = engine.config.get("screen_updating", False)
                except Exception:
                    pass
                break

            if pid is None and started_pid is not None:
                if diag and _is_wps_diag(diag):
                    try:
                        app_obj.Quit(SaveChanges=0)
                    except Exception:
                        pass
                    app_obj = None
                    break
                try:
                    now_ts = float(time.time())
                except Exception:
                    now_ts = 0.0
                try:
                    if first_active_obj_ts is not None and (now_ts - float(first_active_obj_ts)) < 1.0:
                        time.sleep(0.2)
                        continue
                except Exception:
                    pass

                ok_started = False
                try:
                    p = psutil.Process(int(started_pid))
                    ok_started = (p.name() or "").lower() == "winword.exe"
                except Exception:
                    ok_started = False

                if ok_started:
                    engine.app = app_obj
                    engine._owned_pid = int(started_pid)
                    if started_ct is not None:
                        try:
                            engine._owned_create_time = float(started_ct)
                        except Exception:
                            engine._owned_create_time = None
                    else:
                        try:
                            engine._owned_create_time = _safe_process_create_time(int(started_pid))
                        except Exception:
                            engine._owned_create_time = None
                    try:
                        _register_office_process(int(engine._owned_pid), engine._owned_create_time)
                    except Exception:
                        pass
                    break

            time.sleep(0.2)

        if not engine.app:
            try:
                if started_pid is not None and started_ct is not None:
                    _unregister_office_process(started_pid, started_ct)
            except Exception:
                pass
            try:
                if started_pid is not None:
                    p = psutil.Process(int(started_pid))
                    p.terminate()
            except Exception:
                pass
            if app_obj is not None:
                try:
                    app_obj.Quit(SaveChanges=0)
                except Exception:
                    pass
            raise RuntimeError(
                append_word_startup_faq(f"启动 Word 后未能绑定到指定实例（PID={started_pid}）。{last_bind_error!r}")
            )

        _post_start_setup(
            started_pid=started_pid,
            started_ct=started_ct,
            before_snapshot=before_popen_snapshot,
            min_create_time=popen_start_ts,
        )

    except Exception as e:
        try:
            wrapped = append_word_startup_faq(str(e))
        except Exception:
            wrapped = str(e)
        engine._logger.error(f"❌ Word 启动失败: {wrapped}")
        raise RuntimeError(wrapped) from e
