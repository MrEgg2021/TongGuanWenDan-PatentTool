from __future__ import annotations

import unittest
from unittest.mock import patch


class _FakeProc:
    def __init__(
        self,
        *,
        pid: int,
        name: str,
        exe: str = "",
        create_time: float = 1.0,
        cmdline: list[str] | None = None,
    ) -> None:
        self.info = {
            "pid": pid,
            "name": name,
            "exe": exe,
            "create_time": create_time,
            "cmdline": cmdline,
        }


class _FakeTerminableProcess:
    def __init__(self, *, fail_wait: bool = False) -> None:
        self.fail_wait = fail_wait
        self.terminated = False
        self.killed = False

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True

    def wait(self, timeout: float) -> None:
        if self.fail_wait and not self.killed:
            raise TimeoutError("still alive")


class OfficeProcessGuardTests(unittest.TestCase):
    def test_scan_reports_external_word_and_wps_with_visibility_and_path(self) -> None:
        from core.office_process_safety import scan_office_processes

        fake_processes = [
            _FakeProc(pid=101, name="WINWORD.EXE", exe=r"C:\Office\WINWORD.EXE", create_time=10.0),
            _FakeProc(pid=202, name="wps.exe", exe=r"C:\WPS\wps.exe", create_time=20.0),
        ]

        with (
            patch("core.office_process_safety.psutil.process_iter", return_value=fake_processes),
            patch("core.office_process_safety._visible_window_pids", return_value={101}),
            patch("core.office_process_safety._load_office_process_registry", return_value=("registry.json", [])),
        ):
            found = scan_office_processes()

        self.assertEqual([101, 202], [item.pid for item in found])
        self.assertEqual(["word", "wps"], [item.app_family for item in found])
        self.assertEqual([True, False], [item.visible for item in found])
        self.assertEqual(r"C:\Office\WINWORD.EXE", found[0].exe)

    def test_scan_ignores_cloud_update_and_launcher_processes(self) -> None:
        from core.office_process_safety import scan_office_processes

        fake_processes = [
            _FakeProc(pid=701, name="wpscloudsvr.exe", exe=r"C:\WPS\wpscloudsvr.exe", create_time=70.0),
            _FakeProc(pid=702, name="ksolaunch.exe", exe=r"C:\WPS\ksolaunch.exe", create_time=71.0),
            _FakeProc(pid=703, name="OfficeClickToRun.exe", exe=r"C:\Office\OfficeClickToRun.exe", create_time=72.0),
            _FakeProc(pid=704, name="OneDrive.exe", exe=r"C:\OneDrive\OneDrive.exe", create_time=73.0),
        ]

        with (
            patch("core.office_process_safety.psutil.process_iter", return_value=fake_processes),
            patch("core.office_process_safety._visible_window_pids", return_value=set()),
            patch("core.office_process_safety._load_office_process_registry", return_value=("registry.json", [])),
        ):
            found = scan_office_processes()

        self.assertEqual([], found)

    def test_classification_ignores_only_hidden_wps_qing_browser_helper(self) -> None:
        from core.office_process_safety import classify_office_processes

        qing_browser_cmdline = [
            r"D:\WPS\wps.exe",
            "Run",
            "-Entry=EntryPoint",
            r"C:\Users\user\addons\jsapibrowser.dll",
            "--server=browser",
            "--from=qing",
        ]
        fake_processes = [
            _FakeProc(pid=901, name="wps.exe", cmdline=qing_browser_cmdline),
            _FakeProc(pid=902, name="wps.exe", cmdline=[r"D:\WPS\wps.exe", r"D:\document.docx"]),
            _FakeProc(pid=903, name="wps.exe", cmdline=qing_browser_cmdline),
        ]

        with (
            patch("core.office_process_safety.psutil.process_iter", return_value=fake_processes),
            patch("core.office_process_safety._visible_window_pids", return_value={903}),
            patch("core.office_process_safety._load_office_process_registry", return_value=("registry.json", [])),
        ):
            classified = classify_office_processes()

        self.assertEqual([901], [item.pid for item in classified.ignored_background_services])
        self.assertEqual([902], [item.pid for item in classified.hidden_background_document_hosts])
        self.assertEqual([903], [item.pid for item in classified.visible_document_sessions])

    def test_scan_marks_registered_winword_as_owned_residual(self) -> None:
        from core.office_process_safety import scan_office_processes

        fake_processes = [
            _FakeProc(pid=303, name="WINWORD.EXE", exe=r"C:\Office\WINWORD.EXE", create_time=33.0),
        ]

        with (
            patch("core.office_process_safety.psutil.process_iter", return_value=fake_processes),
            patch("core.office_process_safety._visible_window_pids", return_value=set()),
            patch(
                "core.office_process_safety._load_office_process_registry",
                return_value=("registry.json", [{"pid": 303, "create_time": 33.0}]),
            ),
        ):
            found = scan_office_processes()

        self.assertEqual(1, len(found))
        self.assertTrue(found[0].owned)

    def test_blocking_processes_exclude_owned_residuals_and_cloud_services(self) -> None:
        from core.office_process_safety import blocking_office_processes

        fake_processes = [
            _FakeProc(pid=301, name="WINWORD.EXE", exe=r"C:\Office\WINWORD.EXE", create_time=30.0),
            _FakeProc(pid=302, name="WINWORD.EXE", exe=r"C:\Office\WINWORD.EXE", create_time=31.0),
            _FakeProc(pid=303, name="wpscloudsvr.exe", exe=r"C:\WPS\wpscloudsvr.exe", create_time=32.0),
            _FakeProc(pid=304, name="OfficeClickToRun.exe", exe=r"C:\Office\OfficeClickToRun.exe", create_time=33.0),
        ]

        with (
            patch("core.office_process_safety.psutil.process_iter", return_value=fake_processes),
            patch("core.office_process_safety._visible_window_pids", return_value={301, 302}),
            patch(
                "core.office_process_safety._load_office_process_registry",
                return_value=("registry.json", [{"pid": 301, "create_time": 30.0}]),
            ),
        ):
            found = blocking_office_processes()

        self.assertEqual([302], [item.pid for item in found])

    def test_classification_splits_visible_hidden_owned_and_ignored_processes(self) -> None:
        from core.office_process_safety import (
            blocking_office_processes,
            classify_office_processes,
            external_document_hosts,
            hidden_background_document_hosts,
        )

        fake_processes = [
            _FakeProc(pid=801, name="wps.exe", exe=r"C:\WPS\wps.exe", create_time=80.0),
            _FakeProc(pid=802, name="wps.exe", exe=r"C:\WPS\wps.exe", create_time=81.0),
            _FakeProc(pid=803, name="WINWORD.EXE", exe=r"C:\Office\WINWORD.EXE", create_time=82.0),
            _FakeProc(pid=804, name="wpscloudsvr.exe", exe=r"C:\WPS\wpscloudsvr.exe", create_time=83.0),
            _FakeProc(pid=805, name="OfficeClickToRun.exe", exe=r"C:\Office\OfficeClickToRun.exe", create_time=84.0),
        ]

        with (
            patch("core.office_process_safety.psutil.process_iter", return_value=fake_processes),
            patch("core.office_process_safety._visible_window_pids", return_value={801}),
            patch(
                "core.office_process_safety._load_office_process_registry",
                return_value=("registry.json", [{"pid": 803, "create_time": 82.0}]),
            ),
        ):
            classified = classify_office_processes()
            blocking = blocking_office_processes()
            hidden = hidden_background_document_hosts()
            external = external_document_hosts()

        self.assertEqual([801], [item.pid for item in classified.visible_document_sessions])
        self.assertEqual([802], [item.pid for item in classified.hidden_background_document_hosts])
        self.assertEqual([803], [item.pid for item in classified.owned_residuals])
        self.assertEqual([804, 805], [item.pid for item in classified.ignored_background_services])
        self.assertEqual([801], [item.pid for item in blocking])
        self.assertEqual([802], [item.pid for item in hidden])
        self.assertEqual([801, 802], [item.pid for item in external])

    def test_guard_blocks_hidden_background_hosts_by_default_without_terminating(self) -> None:
        from core.office_process_safety import OfficeProcessInfo
        from gui.office_process_guard import ensure_office_processes_ready

        hidden_item = OfficeProcessInfo(
            name="wps.exe",
            pid=901,
            exe=r"C:\WPS\wps.exe",
            create_time=90.0,
            visible=False,
            owned=False,
            app_family="wps",
        )

        with (
            patch("gui.office_process_guard.terminate_owned_office_processes"),
            patch("gui.office_process_guard.blocking_office_processes", return_value=[]),
            patch("gui.office_process_guard.hidden_background_document_hosts", return_value=[hidden_item]),
            patch("gui.office_process_guard.show_blocking_alert_modal", return_value="secondary") as modal_mock,
            patch("gui.office_process_guard.terminate_office_processes") as terminate_mock,
        ):
            allowed = ensure_office_processes_ready(object(), context="conversion_start")

        self.assertFalse(allowed)
        modal_mock.assert_called_once()
        self.assertEqual("后台 Office/WPS 进程", modal_mock.call_args.args[1])
        self.assertEqual("重新检测", modal_mock.call_args.kwargs["primary_text"])
        self.assertEqual("取消", modal_mock.call_args.kwargs["secondary_text"])
        self.assertEqual("尝试清理后台程序...", modal_mock.call_args.kwargs["tertiary_text"])
        self.assertIn("可能会影响后续检测或转换", modal_mock.call_args.args[2])
        self.assertIn("一般只在反复检测不过时使用", modal_mock.call_args.args[2])
        self.assertIn("PID=901", modal_mock.call_args.args[2])
        terminate_mock.assert_not_called()

    def test_guard_allows_after_hidden_retry_recheck_clears(self) -> None:
        from core.office_process_safety import OfficeProcessInfo
        from gui.office_process_guard import ensure_office_processes_ready

        hidden_item = OfficeProcessInfo(
            name="wps.exe",
            pid=902,
            exe=r"C:\WPS\wps.exe",
            create_time=90.0,
            visible=False,
            owned=False,
            app_family="wps",
        )

        with (
            patch("gui.office_process_guard.terminate_owned_office_processes"),
            patch("gui.office_process_guard.blocking_office_processes", return_value=[]),
            patch("gui.office_process_guard.hidden_background_document_hosts", side_effect=[[hidden_item], []]),
            patch("gui.office_process_guard.show_blocking_alert_modal", return_value="primary") as modal_mock,
            patch("gui.office_process_guard.terminate_office_processes") as terminate_mock,
        ):
            allowed = ensure_office_processes_ready(object(), context="conversion_start")

        self.assertTrue(allowed)
        modal_mock.assert_called_once()
        terminate_mock.assert_not_called()

    def test_guard_advanced_cleanup_requires_confirmation_before_terminating(self) -> None:
        from core.office_process_safety import OfficeProcessInfo, ProcessTerminationResult
        from gui.office_process_guard import ensure_office_processes_ready

        hidden_item = OfficeProcessInfo(
            name="wps.exe",
            pid=903,
            exe=r"C:\WPS\wps.exe",
            create_time=90.0,
            visible=False,
            owned=False,
            app_family="wps",
        )

        with (
            patch("gui.office_process_guard.terminate_owned_office_processes"),
            patch("gui.office_process_guard.blocking_office_processes", return_value=[]),
            patch("gui.office_process_guard.hidden_background_document_hosts", side_effect=[[hidden_item], [hidden_item], [], []]),
            patch("gui.office_process_guard.show_blocking_alert_modal", return_value="tertiary"),
            patch("gui.office_process_guard.ask_continue_cancel", return_value=True) as confirm_mock,
            patch(
                "gui.office_process_guard.terminate_office_processes",
                return_value=ProcessTerminationResult(terminated=[903], killed=[], remaining=[], errors=[]),
            ) as terminate_mock,
        ):
            allowed = ensure_office_processes_ready(object(), context="conversion_start")

        self.assertTrue(allowed)
        confirm_mock.assert_called_once()
        self.assertEqual("高级清理后台进程", confirm_mock.call_args.args[1])
        self.assertEqual("已保存，开始清理", confirm_mock.call_args.kwargs["continue_text"])
        self.assertIn("看不见的 Word/WPS 后台程序", confirm_mock.call_args.args[2])
        self.assertIn("重要文档已经保存", confirm_mock.call_args.args[2])
        terminate_mock.assert_called_once_with([hidden_item], allow_kill=False)

    def test_advanced_cleanup_logs_normal_termination_success(self) -> None:
        from core.office_process_safety import OfficeProcessInfo, ProcessTerminationResult
        from gui.office_process_guard import advanced_cleanup_hidden_office_processes

        hidden_item = OfficeProcessInfo(
            name="wps.exe",
            pid=911,
            exe=r"C:\WPS\wps.exe",
            create_time=91.0,
            visible=False,
            owned=False,
            app_family="wps",
        )

        with (
            patch("gui.office_process_guard.hidden_background_document_hosts", side_effect=[[hidden_item], []]),
            patch(
                "gui.office_process_guard.terminate_office_processes",
                return_value=ProcessTerminationResult(terminated=[911], killed=[], remaining=[], errors=[]),
            ) as terminate_mock,
            patch("gui.office_process_guard.ask_continue_cancel", return_value=True) as ask_mock,
            patch("gui.office_process_guard.logger") as logger_mock,
        ):
            cleaned = advanced_cleanup_hidden_office_processes(object(), context="word_health_failure")

        self.assertTrue(cleaned)
        terminate_mock.assert_called_once_with([hidden_item], allow_kill=False)
        ask_mock.assert_called_once()
        info_messages = [str(call.args[0]) for call in logger_mock.info.call_args_list]
        self.assertTrue(any("[OFFICE_CLEANUP] normal_terminate" in msg for msg in info_messages))
        self.assertTrue(any("[OFFICE_CLEANUP] normal_terminate_cleared" in msg for msg in info_messages))

    def test_cleanup_prompts_hard_kill_only_after_normal_termination_leaves_remaining(self) -> None:
        from core.office_process_safety import OfficeProcessInfo, ProcessTerminationResult
        from gui.office_process_guard import advanced_cleanup_hidden_office_processes

        hidden_item = OfficeProcessInfo(
            name="wps.exe",
            pid=912,
            exe=r"C:\WPS\wps.exe",
            create_time=92.0,
            visible=False,
            owned=False,
            app_family="wps",
        )

        with (
            patch(
                "gui.office_process_guard.hidden_background_document_hosts",
                side_effect=[[hidden_item], [hidden_item], []],
            ),
            patch(
                "gui.office_process_guard.terminate_office_processes",
                side_effect=[
                    ProcessTerminationResult(terminated=[912], killed=[], remaining=[hidden_item], errors=[]),
                    ProcessTerminationResult(terminated=[912], killed=[912], remaining=[], errors=[]),
                ],
            ) as terminate_mock,
            patch("gui.office_process_guard.ask_continue_cancel", return_value=True) as ask_mock,
            patch("gui.office_process_guard.logger") as logger_mock,
        ):
            cleaned = advanced_cleanup_hidden_office_processes(object(), context="word_health_failure")

        self.assertTrue(cleaned)
        self.assertEqual(2, terminate_mock.call_count)
        self.assertFalse(terminate_mock.call_args_list[0].kwargs["allow_kill"])
        self.assertTrue(terminate_mock.call_args_list[1].kwargs["allow_kill"])
        self.assertEqual(2, ask_mock.call_count)
        self.assertEqual("高级清理后台进程", ask_mock.call_args_list[0].args[1])
        self.assertEqual("已保存，开始清理", ask_mock.call_args_list[0].kwargs["continue_text"])
        self.assertEqual("继续结束后台程序", ask_mock.call_args_list[1].kwargs["continue_text"])
        self.assertIn("部分 Word/WPS 后台程序没有正常关闭", ask_mock.call_args_list[1].args[2])
        info_messages = [str(call.args[0]) for call in logger_mock.info.call_args_list]
        self.assertTrue(any("[OFFICE_CLEANUP] hard_kill_prompt" in msg for msg in info_messages))
        self.assertTrue(any("[OFFICE_CLEANUP] hard_kill_result" in msg for msg in info_messages))

    def test_cleanup_does_not_kill_when_user_rejects_hard_kill(self) -> None:
        from core.office_process_safety import OfficeProcessInfo, ProcessTerminationResult
        from gui.office_process_guard import advanced_cleanup_hidden_office_processes

        hidden_item = OfficeProcessInfo(
            name="wps.exe",
            pid=913,
            exe=r"C:\WPS\wps.exe",
            create_time=93.0,
            visible=False,
            owned=False,
            app_family="wps",
        )

        with (
            patch(
                "gui.office_process_guard.hidden_background_document_hosts",
                side_effect=[[hidden_item], [hidden_item]],
            ),
            patch(
                "gui.office_process_guard.terminate_office_processes",
                return_value=ProcessTerminationResult(terminated=[913], killed=[], remaining=[hidden_item], errors=[]),
            ) as terminate_mock,
            patch("gui.office_process_guard.ask_continue_cancel", side_effect=[True, False]),
            patch("gui.office_process_guard.show_blocking_alert_modal"),
            patch("gui.office_process_guard.logger") as logger_mock,
        ):
            cleaned = advanced_cleanup_hidden_office_processes(object(), context="word_health_failure")

        self.assertFalse(cleaned)
        terminate_mock.assert_called_once_with([hidden_item], allow_kill=False)
        info_messages = [str(call.args[0]) for call in logger_mock.info.call_args_list]
        self.assertTrue(any("[OFFICE_CLEANUP] hard_kill_rejected" in msg for msg in info_messages))

    def test_terminate_uses_normal_termination_without_kill_by_default(self) -> None:
        from core.office_process_safety import OfficeProcessInfo, terminate_office_processes

        fake_process = _FakeTerminableProcess()
        item = OfficeProcessInfo(
            name="WINWORD.EXE",
            pid=404,
            exe=r"C:\Office\WINWORD.EXE",
            create_time=44.0,
            visible=False,
            owned=False,
            app_family="word",
        )

        with patch("core.office_process_safety.psutil.Process", return_value=fake_process):
            result = terminate_office_processes([item], allow_kill=False)

        self.assertTrue(fake_process.terminated)
        self.assertFalse(fake_process.killed)
        self.assertEqual([404], result.terminated)
        self.assertEqual([], result.killed)
        self.assertEqual([], result.remaining)

    def test_terminate_does_not_kill_when_wait_fails_without_confirmation(self) -> None:
        from core.office_process_safety import OfficeProcessInfo, terminate_office_processes

        fake_process = _FakeTerminableProcess(fail_wait=True)
        item = OfficeProcessInfo(
            name="WINWORD.EXE",
            pid=505,
            exe=r"C:\Office\WINWORD.EXE",
            create_time=55.0,
            visible=False,
            owned=False,
            app_family="word",
        )

        with patch("core.office_process_safety.psutil.Process", return_value=fake_process):
            result = terminate_office_processes([item], allow_kill=False)

        self.assertTrue(fake_process.terminated)
        self.assertFalse(fake_process.killed)
        self.assertEqual([], result.killed)
        self.assertEqual([505], [item.pid for item in result.remaining])

    def test_terminate_uses_kill_only_when_confirmed(self) -> None:
        from core.office_process_safety import OfficeProcessInfo, terminate_office_processes

        fake_process = _FakeTerminableProcess(fail_wait=True)
        item = OfficeProcessInfo(
            name="WINWORD.EXE",
            pid=606,
            exe=r"C:\Office\WINWORD.EXE",
            create_time=66.0,
            visible=False,
            owned=False,
            app_family="word",
        )

        with patch("core.office_process_safety.psutil.Process", return_value=fake_process):
            result = terminate_office_processes([item], allow_kill=True)

        self.assertTrue(fake_process.terminated)
        self.assertTrue(fake_process.killed)
        self.assertEqual([606], result.terminated)
        self.assertEqual([606], result.killed)
        self.assertEqual([], result.remaining)


if __name__ == "__main__":
    unittest.main()
