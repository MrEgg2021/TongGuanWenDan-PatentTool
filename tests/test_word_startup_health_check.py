from __future__ import annotations

import unittest
from unittest.mock import patch


class _FakeStartedProcess:
    def __init__(self, *, pid: int = 808, fail_wait: bool = False, wait_outcomes=None) -> None:
        self.pid = pid
        self.fail_wait = fail_wait
        self.wait_outcomes = list(wait_outcomes or [])
        self.terminated = False
        self.wait_calls = 0
        self.wait_timeouts: list[float | None] = []

    def wait(self, timeout: float | None = None) -> int:
        self.wait_calls += 1
        self.wait_timeouts.append(timeout)
        if self.wait_outcomes:
            outcome = self.wait_outcomes.pop(0)
            if isinstance(outcome, BaseException):
                raise outcome
            return int(outcome)
        if self.fail_wait:
            raise TimeoutError("word did not exit")
        return 0

    def terminate(self) -> None:
        self.terminated = True


class _FakeWordApp:
    def __init__(self, *, version: str = "16.0") -> None:
        self.quit_called = False
        self.Version = version

    def Quit(self, SaveChanges=0):  # noqa: N802 - COM style
        self.quit_called = True


class WordStartupHealthCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self._dispatch_patcher = patch("core.word_startup_health.dispatch_word_via_com", return_value=(None, {}))
        self._dispatch_patcher.start()
        self.addCleanup(self._dispatch_patcher.stop)

    def test_health_check_passes_when_started_word_binds_and_exits(self) -> None:
        from core.word_startup_health import check_word_startup_health

        proc = _FakeStartedProcess(pid=808)
        app = _FakeWordApp()

        with (
            patch("core.word_startup_health.find_first_winword_exe", return_value=r"C:\Office\WINWORD.EXE"),
            patch("core.word_startup_health.subprocess.Popen", return_value=proc) as popen_mock,
            patch(
                "core.word_startup_health.get_active_word_via_com",
                return_value=(
                    app,
                    {
                        "binding_progid": "Word.Application.16",
                        "last_diag": {"PID": 808, "Name": "Microsoft Word", "ProcExe": r"C:\Office\WINWORD.EXE"},
                    },
                ),
            ),
            patch("core.word_startup_health.is_wps_runtime_diag", return_value=False),
        ):
            result = check_word_startup_health()

        self.assertTrue(result.ok)
        self.assertEqual(808, result.pid)
        self.assertEqual("Word.Application.16", result.binding_progid)
        self.assertIsNone(result.error)
        self.assertTrue(app.quit_called)
        self.assertGreaterEqual(proc.wait_calls, 1)
        popen_mock.assert_called_once()

    def test_health_check_fails_when_binding_is_wps(self) -> None:
        from core.word_startup_health import check_word_startup_health

        proc = _FakeStartedProcess(pid=909)
        app = _FakeWordApp()

        with (
            patch("core.word_startup_health.find_first_winword_exe", return_value=r"C:\Office\WINWORD.EXE"),
            patch("core.word_startup_health.subprocess.Popen", return_value=proc),
            patch(
                "core.word_startup_health.get_active_word_via_com",
                return_value=(
                    app,
                    {
                        "binding_progid": "Word.Application",
                        "last_diag": {"PID": 909, "Name": "WPS Writer", "ProcExe": r"C:\WPS\wps.exe"},
                    },
                ),
            ),
            patch("core.word_startup_health.is_wps_runtime_diag", return_value=True),
        ):
            result = check_word_startup_health()

        self.assertFalse(result.ok)
        self.assertIn("WPS", str(result.error))
        self.assertEqual("com_bound_to_wps", result.reason_code)
        self.assertIn("Microsoft Word", str(result.user_message))
        self.assertIn("WPS Writer", str(result.technical_detail))

    def test_health_check_passes_when_pid_is_missing_but_runtime_is_word_and_exits(self) -> None:
        from core.word_startup_health import check_word_startup_health

        proc = _FakeStartedProcess(pid=1201)
        app = _FakeWordApp()

        with (
            patch("core.word_startup_health.find_first_winword_exe", return_value=r"C:\Office\WINWORD.EXE"),
            patch("core.word_startup_health.subprocess.Popen", return_value=proc),
            patch(
                "core.word_startup_health.get_active_word_via_com",
                return_value=(
                    app,
                    {
                        "binding_progid": "Word.Application.16",
                        "last_diag": {"PID": None, "Name": "Microsoft Word", "ProcExe": r"C:\Office\WINWORD.EXE"},
                    },
                ),
            ),
            patch("core.word_startup_health.is_wps_runtime_diag", return_value=False),
        ):
            result = check_word_startup_health()

        self.assertTrue(result.ok)
        self.assertEqual("Word.Application.16", result.binding_progid)
        self.assertIsNone(result.error)
        self.assertTrue(app.quit_called)

    def test_health_check_fails_when_binding_pid_is_unexpected(self) -> None:
        from core.word_startup_health import check_word_startup_health

        proc = _FakeStartedProcess(pid=1001)
        app = _FakeWordApp()

        with (
            patch("core.word_startup_health.find_first_winword_exe", return_value=r"C:\Office\WINWORD.EXE"),
            patch("core.word_startup_health.subprocess.Popen", return_value=proc),
            patch(
                "core.word_startup_health.get_active_word_via_com",
                return_value=(
                    app,
                    {
                        "binding_progid": "Word.Application.16",
                        "last_diag": {"PID": 1002, "Name": "Microsoft Word", "ProcExe": r"C:\Office\WINWORD.EXE"},
                    },
                ),
            ),
            patch("core.word_startup_health.is_wps_runtime_diag", return_value=False),
        ):
            result = check_word_startup_health()

        self.assertFalse(result.ok)
        self.assertIn("PID", str(result.error))

    def test_health_check_fails_when_word_does_not_exit(self) -> None:
        from core.word_startup_health import check_word_startup_health

        proc = _FakeStartedProcess(pid=1101, fail_wait=True)
        app = _FakeWordApp()

        with (
            patch("core.word_startup_health.find_first_winword_exe", return_value=r"C:\Office\WINWORD.EXE"),
            patch("core.word_startup_health.subprocess.Popen", return_value=proc),
            patch(
                "core.word_startup_health.get_active_word_via_com",
                return_value=(
                    app,
                    {
                        "binding_progid": "Word.Application.16",
                        "last_diag": {"PID": 1101, "Name": "Microsoft Word", "ProcExe": r"C:\Office\WINWORD.EXE"},
                    },
                ),
            ),
            patch("core.word_startup_health.is_wps_runtime_diag", return_value=False),
        ):
            result = check_word_startup_health()

        self.assertFalse(result.ok)
        self.assertIn("退出", str(result.error))
        self.assertEqual("word_exit_failed", result.reason_code)
        self.assertIn("Word 启动检查未通过", str(result.user_message))
        self.assertIn("word did not exit", str(result.technical_detail))
        self.assertTrue(proc.terminated)

    def test_health_check_recovers_when_word_exits_within_slow_window(self) -> None:
        from core.word_startup_health import check_word_startup_health

        proc = _FakeStartedProcess(pid=1102, wait_outcomes=[TimeoutError("first wait timed out"), 0])
        app = _FakeWordApp()
        progress_events: list[tuple[str, dict]] = []

        with (
            patch("core.word_startup_health.find_first_winword_exe", return_value=r"C:\Office\WINWORD.EXE"),
            patch("core.word_startup_health.subprocess.Popen", return_value=proc),
            patch(
                "core.word_startup_health.get_active_word_via_com",
                return_value=(
                    app,
                    {
                        "binding_progid": "Word.Application.16",
                        "last_diag": {"PID": 1102, "Name": "Microsoft Word", "ProcExe": r"C:\Office\WINWORD.EXE"},
                    },
                ),
            ),
            patch("core.word_startup_health.is_wps_runtime_diag", return_value=False),
        ):
            result = check_word_startup_health(
                exit_timeout=8.0,
                slow_exit_timeout=25.0,
                progress_callback=lambda stage, payload: progress_events.append((stage, payload)),
            )

        self.assertTrue(result.ok)
        self.assertEqual("slow_word_exit_recovered", result.reason_code)
        self.assertIn("slow exit", result.technical_detail)
        self.assertFalse(proc.terminated)
        self.assertEqual([8.0, 17.0], proc.wait_timeouts)
        self.assertTrue(any(stage == "slow_exit_wait" for stage, _ in progress_events))

    def test_health_check_fails_when_word_exceeds_slow_window(self) -> None:
        from core.word_startup_health import check_word_startup_health

        proc = _FakeStartedProcess(
            pid=1103,
            wait_outcomes=[TimeoutError("first wait timed out"), TimeoutError("second wait timed out")],
        )
        app = _FakeWordApp()

        with (
            patch("core.word_startup_health.find_first_winword_exe", return_value=r"C:\Office\WINWORD.EXE"),
            patch("core.word_startup_health.subprocess.Popen", return_value=proc),
            patch(
                "core.word_startup_health.get_active_word_via_com",
                return_value=(
                    app,
                    {
                        "binding_progid": "Word.Application.16",
                        "last_diag": {"PID": 1103, "Name": "Microsoft Word", "ProcExe": r"C:\Office\WINWORD.EXE"},
                    },
                ),
            ),
            patch("core.word_startup_health.is_wps_runtime_diag", return_value=False),
        ):
            result = check_word_startup_health(exit_timeout=8.0, slow_exit_timeout=25.0)

        self.assertFalse(result.ok)
        self.assertEqual("word_exit_failed", result.reason_code)
        self.assertTrue(proc.terminated)
        self.assertEqual([8.0, 17.0], proc.wait_timeouts)

    def test_killed_before_check_failure_mentions_abnormal_office_state(self) -> None:
        from core.word_startup_health import check_word_startup_health

        with patch("core.word_startup_health.find_first_winword_exe", return_value=""):
            result = check_word_startup_health(killed_before_check=True)

        self.assertFalse(result.ok)
        self.assertTrue(result.killed_before_check)
        self.assertIn("Office/WPS 可能处于异常状态", str(result.error))
        self.assertIn("Office/WPS 可能处于异常状态", str(result.user_message))
        self.assertEqual("word_not_found", result.reason_code)

    def test_health_check_passes_when_dispatch_succeeds_without_active_object_lookup(self) -> None:
        from core.word_startup_health import check_word_startup_health

        proc = _FakeStartedProcess(pid=1601)
        app = _FakeWordApp(version="16.0")

        with (
            patch(
                "core.word_startup_health.dispatch_word_via_com",
                return_value=(
                    app,
                    {
                        "binding_source": "default_progid",
                        "binding_progid": "Word.Application",
                        "attempted_progids": ["Word.Application"],
                        "last_diag": {
                            "PID": 1601,
                            "Name": "Microsoft Word",
                            "Path": r"C:\Program Files (x86)\Microsoft Office\root\Office16",
                            "ProcExe": r"C:\Program Files (x86)\Microsoft Office\root\Office16\WINWORD.EXE",
                        },
                    },
                ),
            ),
            patch("core.word_startup_health._wait_for_pid", return_value=proc),
            patch("core.word_startup_health.get_active_word_via_com") as active_mock,
            patch("core.word_startup_health.find_first_winword_exe") as find_mock,
            patch("core.word_startup_health.subprocess.Popen") as popen_mock,
        ):
            result = check_word_startup_health()

        self.assertTrue(result.ok)
        self.assertEqual(1601, result.pid)
        self.assertEqual("Word.Application", result.binding_progid)
        self.assertIn("Program Files (x86)", result.technical_detail)
        self.assertTrue(app.quit_called)
        self.assertGreaterEqual(proc.wait_calls, 1)
        active_mock.assert_not_called()
        find_mock.assert_not_called()
        popen_mock.assert_not_called()

    def test_health_check_fails_when_dispatch_diag_pid_is_missing_and_unclaimed(self) -> None:
        from core.word_startup_health import check_word_startup_health

        app = _FakeWordApp(version="14.0")

        with (
            patch(
                "core.word_startup_health.dispatch_word_via_com",
                return_value=(
                    app,
                    {
                        "binding_source": "versioned_progid",
                        "binding_progid": "Word.Application.14",
                        "attempted_progids": ["Word.Application", "Word.Application.14"],
                        "last_diag": {
                            "PID": None,
                            "Name": "Microsoft Word",
                            "Path": r"C:\Office14",
                            "ProcExe": None,
                        },
                    },
                ),
            ),
            patch("core.word_startup_health.find_claimable_winword_process", return_value=None) as claim_mock,
            patch("core.word_startup_health._wait_for_pid") as wait_for_pid_mock,
        ):
            result = check_word_startup_health()

        self.assertFalse(result.ok)
        self.assertIsNone(result.pid)
        self.assertEqual("Word.Application.14", result.binding_progid)
        self.assertTrue(app.quit_called)
        self.assertEqual("word_pid_missing_unclaimed", result.reason_code)
        self.assertIn("无法确认", str(result.user_message))
        claim_mock.assert_called_once()
        wait_for_pid_mock.assert_not_called()

    def test_health_check_passes_when_dispatch_diag_pid_is_missing_but_unique_word_is_claimed(self) -> None:
        from core.word_startup_health import check_word_startup_health

        app = _FakeWordApp(version="16.0")
        proc = _FakeStartedProcess(pid=1701)

        with (
            patch(
                "core.word_startup_health.dispatch_word_via_com",
                return_value=(
                    app,
                    {
                        "binding_source": "default_progid",
                        "binding_progid": "Word.Application",
                        "attempted_progids": ["Word.Application"],
                        "last_diag": {
                            "PID": None,
                            "Name": "Microsoft Word",
                            "Path": r"C:\Office16",
                            "ProcExe": None,
                        },
                    },
                ),
            ),
            patch("core.word_startup_health.find_claimable_winword_process", return_value=(1701, 220.0)) as claim_mock,
            patch("core.word_startup_health._wait_for_pid", return_value=proc) as wait_for_pid_mock,
        ):
            result = check_word_startup_health()

        self.assertTrue(result.ok)
        self.assertEqual(1701, result.pid)
        self.assertEqual("Word.Application", result.binding_progid)
        self.assertTrue(app.quit_called)
        self.assertGreaterEqual(proc.wait_calls, 1)
        claim_mock.assert_called_once()
        wait_for_pid_mock.assert_called_once_with(1701)

    def test_health_check_fails_when_dispatch_only_finds_wps_and_no_winword(self) -> None:
        from core.word_startup_health import check_word_startup_health

        with (
            patch(
                "core.word_startup_health.dispatch_word_via_com",
                return_value=(
                    None,
                    {
                        "binding_source": "",
                        "binding_progid": "",
                        "attempted_progids": ["Word.Application", "Word.Application.16"],
                        "last_diag": {
                            "PID": 1701,
                            "Name": "WPS Writer",
                            "Path": r"C:\Program Files\Kingsoft\WPS Office\office6",
                            "ProcExe": r"C:\Program Files\Kingsoft\WPS Office\office6\wps.exe",
                        },
                    },
                ),
            ),
            patch("core.word_startup_health.find_first_winword_exe", return_value=""),
        ):
            result = check_word_startup_health()

        self.assertFalse(result.ok)
        self.assertEqual("com_bound_to_wps", result.reason_code)
        self.assertIn("WPS", result.technical_detail)

    def test_health_check_rejects_word_version_below_2007(self) -> None:
        from core.word_startup_health import check_word_startup_health

        app = _FakeWordApp(version="11.0")

        proc = _FakeStartedProcess(pid=1101)

        with patch(
            "core.word_startup_health.dispatch_word_via_com",
            return_value=(
                app,
                {
                    "binding_source": "versioned_progid",
                    "binding_progid": "Word.Application.11",
                    "attempted_progids": ["Word.Application.11"],
                    "last_diag": {"PID": 1101, "Name": "Microsoft Word", "ProcExe": r"C:\Office11\WINWORD.EXE"},
                },
            ),
        ), patch("core.word_startup_health._wait_for_pid", return_value=proc):
            result = check_word_startup_health()

        self.assertFalse(result.ok)
        self.assertEqual("word_version_unsupported", result.reason_code)
        self.assertIn("Word 2007", result.user_message)
        self.assertTrue(app.quit_called)


if __name__ == "__main__":
    unittest.main()
