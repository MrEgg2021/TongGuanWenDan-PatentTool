from __future__ import annotations

import unittest
from unittest.mock import Mock, patch


class _FakeApp:
    def __init__(self, path: str, *, hwnd: int = 100, quit_raises: bool = False) -> None:
        self.Path = path
        self.Hwnd = hwnd
        self.quit_called = False
        self._quit_raises = bool(quit_raises)

    def Quit(self, SaveChanges=0):  # noqa: N802 - COM style
        self.quit_called = True
        if self._quit_raises:
            raise RuntimeError("quit failed")


class _FakeClient:
    def __init__(self, *, dispatch_map=None, active_map=None) -> None:
        self.dispatch_map = dict(dispatch_map or {})
        self.active_map = dict(active_map or {})
        self.dispatch_calls: list[str] = []
        self.active_calls: list[str] = []

    def DispatchEx(self, progid: str):  # noqa: N802 - COM style
        self.dispatch_calls.append(progid)
        value = self.dispatch_map[progid]
        if isinstance(value, Exception):
            raise value
        return value

    def GetActiveObject(self, progid: str):  # noqa: N802 - COM style
        self.active_calls.append(progid)
        value = self.active_map[progid]
        if isinstance(value, Exception):
            raise value
        return value


class _FakeProc:
    def __init__(self, pid: int, name: str, create_time: float = 100.0) -> None:
        self.info = {"pid": int(pid), "name": str(name), "create_time": float(create_time)}


class _FakeStartEngine:
    def __init__(self) -> None:
        self.config = {}
        self.app = None
        self.version = None
        self._owned_pid = None
        self._owned_create_time = None
        self._app_started_ts = None
        self._app_start_before_snapshot = None
        self._app_start_min_create_time = None
        self._visible_true_since_ts = None
        self._logger = Mock()
        self.clean_zombie_processes = Mock()


class WordComResolverTests(unittest.TestCase):
    def test_runtime_guard_uses_same_helper_classification_as_precheck(self) -> None:
        from core.office_process_safety import external_document_hosts
        from core.word_engine import WordEngine

        helper_command = ["wps.exe", "jsapibrowser.dll", "--from=qing"]
        cases = [
            ("hidden_helper", helper_command, set(), False),
            ("visible_helper", helper_command, {26088}, True),
            ("visibility_unknown", helper_command, None, True),
            ("missing_qing_marker", ["wps.exe", "jsapibrowser.dll"], set(), True),
            ("missing_browser_marker", ["wps.exe", "--from=qing"], set(), True),
            ("ordinary_wps", ["wps.exe", "document.docx"], set(), True),
        ]
        for name, command, visible, blocked in cases:
            with self.subTest(name=name):
                engine = WordEngine({})
                engine.app = Mock(Visible=False)
                engine._owned_pid = 23400
                engine._abort_owned_process = Mock(side_effect=RuntimeError("blocked"))
                owned = _FakeProc(23400, "WINWORD.EXE")
                helper = _FakeProc(26088, "wps.exe")
                helper.info["cmdline"] = command
                with (
                    patch("core.office_process_safety.psutil.process_iter", return_value=[owned, helper]),
                    patch("core.office_process_safety._visible_window_pids", return_value=visible),
                    patch("core.office_process_safety._load_office_process_registry", return_value=("registry", [{"pid": 23400, "create_time": 100.0}])),
                    patch("core.word_engine._visible_window_pids", return_value=visible),
                ):
                    self.assertEqual(bool(external_document_hosts()), blocked)
                    if blocked:
                        with self.assertRaisesRegex(RuntimeError, "blocked"):
                            engine._runtime_guard_check()
                    else:
                        engine._runtime_guard_check()
                        engine._abort_owned_process.assert_not_called()

    def test_runtime_guard_blocks_other_registered_word_residual(self) -> None:
        from core.word_engine import WordEngine

        engine = WordEngine({})
        engine.app = Mock(Visible=False)
        engine._owned_pid = 23400
        engine._abort_owned_process = Mock(side_effect=RuntimeError("blocked"))
        with (
            patch("core.office_process_safety.psutil.process_iter", return_value=[_FakeProc(23400, "WINWORD.EXE"), _FakeProc(24000, "WINWORD.EXE")]),
            patch("core.office_process_safety._visible_window_pids", return_value=set()),
            patch("core.office_process_safety._load_office_process_registry", return_value=("registry", [{"pid": pid, "create_time": 100.0} for pid in (23400, 24000)])),
            patch("core.word_engine._visible_window_pids", return_value=set()),
        ):
            with self.assertRaisesRegex(RuntimeError, "blocked"):
                engine._runtime_guard_check()

    def test_fallback_word_startup_ignores_helper_but_blocks_document_host(self) -> None:
        from core.word_engine_impl.start_app_steps.dispatch import start_app_dispatch_flow

        prefix = "core.word_engine_impl.start_app_steps.dispatch."
        for command, blocked in [
            (["wps.exe", "jsapibrowser.dll", "--from=qing"], False),
            (["wps.exe", "document.docx"], True),
            (["WINWORD.EXE"], True),
        ]:
            with self.subTest(command=command):
                engine = _FakeStartEngine()
                app = _FakeApp(r"C:\Office", hwnd=1)
                app.Version = "16.0"
                helper = _FakeProc(26088, "wps.exe")
                helper.info["cmdline"] = command
                if command[0] == "WINWORD.EXE":
                    helper.info["name"] = "WINWORD.EXE"
                with (
                    patch(prefix + "external_document_hosts", return_value=[]),
                    patch(prefix + "snapshot_winword_processes", return_value={}),
                    patch(prefix + "dispatch_word_via_com", return_value=(None, {})),
                    patch(prefix + "find_first_winword_exe", return_value=r"C:\Office\WINWORD.EXE"),
                    patch(prefix + "subprocess.Popen", return_value=Mock(pid=23400)),
                    patch(prefix + "_safe_process_create_time", return_value=100.0),
                    patch(prefix + "get_active_word_via_com", return_value=(app, {})),
                    patch(prefix + "collect_word_app_diag", return_value={"Name": "Microsoft Word", "PID": 23400, "Path": r"C:\Office"}),
                    patch(prefix + "_register_office_process"),
                    patch(prefix + "psutil.Process") as process,
                    patch("win32gui.EnumWindows"),
                    patch("core.office_process_safety.psutil.process_iter", return_value=[_FakeProc(23400, "WINWORD.EXE"), helper]),
                    patch("core.office_process_safety._visible_window_pids", return_value=set()),
                    patch("core.office_process_safety._load_office_process_registry", return_value=("registry", [{"pid": 26088, "create_time": 100.0}])),
                ):
                    if blocked:
                        with self.assertRaisesRegex(RuntimeError, "未被本工具认领"):
                            start_app_dispatch_flow(engine, str)
                        process.return_value.terminate.assert_called_once()
                    else:
                        start_app_dispatch_flow(engine, str)
                        self.assertEqual(engine._owned_pid, 23400)
                        self.assertIs(engine.app, app)
                        process.return_value.terminate.assert_not_called()

    def test_dispatch_word_via_com_skips_default_wps_and_uses_versioned_word(self) -> None:
        from core.word_engine_impl.word_com_resolver import dispatch_word_via_com

        wps_app = _FakeApp(r"C:\Program Files (x86)\Kingsoft\WPS Office\office6")
        word_app = _FakeApp(r"E:\Office14")
        client = _FakeClient(
            dispatch_map={
                "Word.Application": wps_app,
                "Word.Application.14": word_app,
            }
        )

        with patch(
            "core.word_engine_impl.word_com_resolver.discover_ms_word_versions_from_registry",
            return_value=[14],
        ), patch(
            "core.word_engine_impl.word_com_resolver.collect_word_app_diag",
            side_effect=[
                {"Path": r"C:\Program Files (x86)\Kingsoft\WPS Office\office6", "ProcExe": None},
                {"Path": r"E:\Office14", "ProcExe": None},
            ],
        ):
            app, info = dispatch_word_via_com(client=client)

        self.assertIs(word_app, app)
        self.assertEqual("versioned_progid", info["binding_source"])
        self.assertEqual("Word.Application.14", info["binding_progid"])
        self.assertTrue(wps_app.quit_called)
        self.assertEqual(["Word.Application", "Word.Application.14"], client.dispatch_calls)

    def test_dispatch_word_via_com_supports_office_2007_and_later_versioned_progids(self) -> None:
        from core.word_engine_impl.word_com_resolver import dispatch_word_via_com

        for version in [12, 14, 15, 16]:
            with self.subTest(version=version):
                progid = f"Word.Application.{version}"
                word_app = _FakeApp(rf"C:\Program Files (x86)\Microsoft Office\Office{version}\WINWORD.EXE")
                client = _FakeClient(dispatch_map={"Word.Application": RuntimeError("default unavailable"), progid: word_app})

                with (
                    patch(
                        "core.word_engine_impl.word_com_resolver.discover_ms_word_versions_from_registry",
                        return_value=[version],
                    ),
                    patch(
                        "core.word_engine_impl.word_com_resolver.collect_word_app_diag",
                        return_value={
                            "Name": "Microsoft Word",
                            "Path": rf"C:\Program Files (x86)\Microsoft Office\Office{version}",
                            "ProcExe": rf"C:\Program Files (x86)\Microsoft Office\Office{version}\WINWORD.EXE",
                        },
                    ),
                ):
                    app, info = dispatch_word_via_com(client=client)

                self.assertIs(word_app, app)
                self.assertEqual("versioned_progid", info["binding_source"])
                self.assertEqual(progid, info["binding_progid"])
                self.assertEqual(["Word.Application", progid], client.dispatch_calls)

    def test_dispatch_word_via_com_returns_none_when_all_candidates_are_wps(self) -> None:
        from core.word_engine_impl.word_com_resolver import dispatch_word_via_com

        default_wps = _FakeApp(r"C:\Program Files\Kingsoft\WPS Office\office6")
        versioned_wps = _FakeApp(r"C:\Program Files\Kingsoft\WPS Office\office6")
        client = _FakeClient(
            dispatch_map={
                "Word.Application": default_wps,
                "Word.Application.16": versioned_wps,
            }
        )

        with (
            patch(
                "core.word_engine_impl.word_com_resolver.discover_ms_word_versions_from_registry",
                return_value=[16],
            ),
            patch(
                "core.word_engine_impl.word_com_resolver.collect_word_app_diag",
                side_effect=[
                    {"Name": "WPS Writer", "Path": r"C:\Program Files\Kingsoft\WPS Office\office6"},
                    {"Name": "WPS Writer", "Path": r"C:\Program Files\Kingsoft\WPS Office\office6"},
                ],
            ),
        ):
            app, info = dispatch_word_via_com(client=client)

        self.assertIsNone(app)
        self.assertEqual("", info["binding_source"])
        self.assertEqual(["Word.Application", "Word.Application.16"], client.dispatch_calls)
        self.assertTrue(default_wps.quit_called)
        self.assertTrue(versioned_wps.quit_called)

    def test_get_active_or_dispatch_word_via_com_prefers_active_versioned_word(self) -> None:
        from core.word_engine_impl.word_com_resolver import get_active_or_dispatch_word_via_com

        wps_app = _FakeApp(r"C:\Program Files (x86)\Kingsoft\WPS Office\office6")
        word_app = _FakeApp(r"E:\Office14")
        client = _FakeClient(
            active_map={
                "Word.Application": wps_app,
                "Word.Application.14": word_app,
            }
        )

        with patch(
            "core.word_engine_impl.word_com_resolver.discover_ms_word_versions_from_registry",
            return_value=[14],
        ), patch(
            "core.word_engine_impl.word_com_resolver.collect_word_app_diag",
            side_effect=[
                {"Path": r"C:\Program Files (x86)\Kingsoft\WPS Office\office6", "ProcExe": None},
                {"Path": r"E:\Office14", "ProcExe": None},
            ],
        ):
            app, owned, info = get_active_or_dispatch_word_via_com(client=client)

        self.assertIs(word_app, app)
        self.assertFalse(owned)
        self.assertEqual("active_versioned_progid", info["binding_source"])
        self.assertEqual("Word.Application.14", info["binding_progid"])
        self.assertEqual(["Word.Application", "Word.Application.14"], client.active_calls)

    def test_claim_word_process_uses_unique_new_winword_when_com_pid_missing(self) -> None:
        from core.word_engine_impl.owned_process_claim import try_claim_word_process_for_engine

        engine = Mock()
        engine.app = _FakeApp(r"C:\Program Files\Microsoft Office\Root\Office16", hwnd=0)
        engine._owned_pid = None
        engine._owned_create_time = None
        engine._logger = Mock()

        with (
            patch(
                "core.word_engine_impl.owned_process_claim.collect_word_app_diag",
                return_value={"Name": "Microsoft Word", "Path": r"C:\Program Files\Microsoft Office\Root\Office16", "PID": None},
            ),
            patch(
                "core.word_engine_impl.owned_process_claim.psutil.process_iter",
                return_value=[
                    _FakeProc(101, "WINWORD.EXE", 100.0),
                    _FakeProc(202, "WINWORD.EXE", 205.0),
                ],
            ),
            patch("core.word_engine_impl.owned_process_claim._register_office_process") as register_mock,
        ):
            claimed = try_claim_word_process_for_engine(
                engine,
                before_snapshot={101: 100.0},
                min_create_time=200.0,
                reason="unit_test",
            )

        self.assertTrue(claimed)
        self.assertEqual(engine._owned_pid, 202)
        self.assertEqual(engine._owned_create_time, 205.0)
        register_mock.assert_called_once_with(202, 205.0)

    def test_find_claimable_word_process_returns_unique_new_winword(self) -> None:
        from core.word_engine_impl.owned_process_claim import find_claimable_winword_process

        with patch(
            "core.word_engine_impl.owned_process_claim.psutil.process_iter",
            return_value=[
                _FakeProc(101, "WINWORD.EXE", 100.0),
                _FakeProc(202, "WINWORD.EXE", 205.0),
            ],
        ):
            claimed = find_claimable_winword_process(
                before_snapshot={101: 100.0},
                min_create_time=200.0,
                diag={"Name": "Microsoft Word", "Path": r"C:\Program Files\Microsoft Office\Root\Office16", "PID": None},
                reason="unit_test",
            )

        self.assertEqual((202, 205.0), claimed)

    def test_claim_word_process_refuses_multiple_new_winword_candidates(self) -> None:
        from core.word_engine_impl.owned_process_claim import try_claim_word_process_for_engine

        engine = Mock()
        engine.app = _FakeApp(r"C:\Program Files\Microsoft Office\Root\Office16", hwnd=0)
        engine._owned_pid = None
        engine._owned_create_time = None
        engine._logger = Mock()

        with (
            patch(
                "core.word_engine_impl.owned_process_claim.collect_word_app_diag",
                return_value={"Name": "Microsoft Word", "Path": r"C:\Program Files\Microsoft Office\Root\Office16", "PID": None},
            ),
            patch(
                "core.word_engine_impl.owned_process_claim.psutil.process_iter",
                return_value=[
                    _FakeProc(202, "WINWORD.EXE", 205.0),
                    _FakeProc(303, "WINWORD.EXE", 206.0),
                ],
            ),
            patch("core.word_engine_impl.owned_process_claim._register_office_process") as register_mock,
        ):
            claimed = try_claim_word_process_for_engine(
                engine,
                before_snapshot={},
                min_create_time=200.0,
                reason="unit_test",
            )

        self.assertFalse(claimed)
        self.assertIsNone(engine._owned_pid)
        self.assertIsNone(engine._owned_create_time)
        register_mock.assert_not_called()

    def test_claim_word_process_rejects_wps_diag_even_when_pid_exists(self) -> None:
        from core.word_engine_impl.owned_process_claim import try_claim_word_process_for_engine

        engine = Mock()
        engine.app = _FakeApp(r"C:\Program Files\Kingsoft\WPS Office\office6", hwnd=0)
        engine._owned_pid = None
        engine._owned_create_time = None
        engine._logger = Mock()

        with (
            patch(
                "core.word_engine_impl.owned_process_claim.collect_word_app_diag",
                return_value={
                    "Name": "WPS Writer",
                    "Path": r"C:\Program Files\Kingsoft\WPS Office\office6",
                    "PID": 303,
                    "ProcName": "wps.exe",
                },
            ),
            patch("core.word_engine_impl.owned_process_claim._register_office_process") as register_mock,
        ):
            claimed = try_claim_word_process_for_engine(engine, reason="unit_test")

        self.assertFalse(claimed)
        self.assertIsNone(engine._owned_pid)
        register_mock.assert_not_called()

    def test_find_claimable_word_process_rejects_wps_diag(self) -> None:
        from core.word_engine_impl.owned_process_claim import find_claimable_winword_process

        with patch(
            "core.word_engine_impl.owned_process_claim.psutil.process_iter",
            return_value=[_FakeProc(202, "WINWORD.EXE", 205.0)],
        ):
            claimed = find_claimable_winword_process(
                before_snapshot={},
                min_create_time=200.0,
                diag={"Name": "WPS Writer", "Path": r"C:\Program Files\Kingsoft\WPS Office\office6", "PID": None},
                reason="unit_test",
            )

        self.assertIsNone(claimed)

    def test_runtime_guard_claims_unique_word_during_startup_grace(self) -> None:
        from core.word_engine import WordEngine

        engine = WordEngine({})
        engine.app = Mock()
        engine.app.Visible = False
        engine._app_started_ts = 100.0
        engine._app_start_before_snapshot = {101: 99.0}
        engine._app_start_min_create_time = 100.5

        def _claim(target_engine, **_kwargs):
            target_engine._owned_pid = 202
            target_engine._owned_create_time = 205.0
            return True

        with (
            patch("core.word_engine.time.time", return_value=101.0),
            patch("core.word_engine.try_claim_word_process_for_engine", side_effect=_claim) as claim_mock,
            patch("core.word_engine.psutil.process_iter", return_value=[_FakeProc(202, "WINWORD.EXE", 205.0)]),
            patch("core.word_engine._visible_window_pids", return_value=set()),
        ):
            engine._runtime_guard_check()

        claim_mock.assert_called_once()
        self.assertEqual({101: 99.0}, claim_mock.call_args.kwargs["before_snapshot"])
        self.assertEqual(100.5, claim_mock.call_args.kwargs["min_create_time"])
        self.assertEqual(engine._owned_pid, 202)

    def test_start_app_dispatch_fails_when_pid_missing_cannot_be_claimed(self) -> None:
        from core.word_engine_impl.start_app_steps.dispatch import start_app_dispatch_flow

        engine = _FakeStartEngine()
        app = _FakeApp(r"C:\Program Files\Microsoft Office\Root\Office16", hwnd=0)
        app.Version = "16.0"

        with (
            patch("core.word_engine_impl.start_app_steps.dispatch.external_document_hosts", return_value=[]),
            patch("core.word_engine_impl.start_app_steps.dispatch.snapshot_winword_processes", return_value={101: 99.0}),
            patch(
                "core.word_engine_impl.start_app_steps.dispatch.dispatch_word_via_com",
                return_value=(
                    app,
                    {
                        "binding_source": "default_progid",
                        "binding_progid": "Word.Application",
                        "attempted_progids": ["Word.Application"],
                        "last_diag": {"PID": None, "Name": "Microsoft Word"},
                    },
                ),
            ),
            patch(
                "core.word_engine_impl.start_app_steps.dispatch.collect_word_app_diag",
                return_value={"PID": None, "Name": "Microsoft Word", "Path": r"C:\Program Files\Microsoft Office\Root\Office16"},
            ),
            patch("core.word_engine_impl.start_app_steps.dispatch.try_claim_word_process_for_engine", return_value=False) as claim_mock,
        ):
            with self.assertRaises(RuntimeError) as ctx:
                start_app_dispatch_flow(engine, lambda message: message)

        self.assertIn("无法确认本次启动", str(ctx.exception))
        claim_mock.assert_called_once()
        self.assertEqual({101: 99.0}, claim_mock.call_args.kwargs["before_snapshot"])

    def test_start_app_dispatch_fails_when_hidden_external_host_exists(self) -> None:
        from core.office_process_safety import OfficeProcessInfo
        from core.word_engine_impl.start_app_steps.dispatch import start_app_dispatch_flow

        engine = _FakeStartEngine()
        hidden_host = OfficeProcessInfo(
            name="wps.exe",
            pid=909,
            exe=r"C:\WPS\wps.exe",
            create_time=90.0,
            visible=False,
            owned=False,
            app_family="wps",
        )

        with (
            patch("core.word_engine_impl.start_app_steps.dispatch.external_document_hosts", return_value=[hidden_host]),
            patch("core.word_engine_impl.start_app_steps.dispatch.dispatch_word_via_com") as dispatch_mock,
        ):
            with self.assertRaises(RuntimeError) as ctx:
                start_app_dispatch_flow(engine, lambda message: message)

        self.assertIn("请先关闭所有 Word/WPS", str(ctx.exception))
        dispatch_mock.assert_not_called()
        engine.clean_zombie_processes.assert_not_called()

    def test_start_app_dispatch_rejects_word_version_below_2007(self) -> None:
        from core.word_engine_impl.start_app_steps.dispatch import start_app_dispatch_flow

        engine = _FakeStartEngine()
        app = _FakeApp(r"C:\Program Files\Microsoft Office\Office11", hwnd=1101)
        app.Version = "11.0"

        with (
            patch("core.word_engine_impl.start_app_steps.dispatch.external_document_hosts", return_value=[]),
            patch("core.word_engine_impl.start_app_steps.dispatch.snapshot_winword_processes", return_value={}),
            patch(
                "core.word_engine_impl.start_app_steps.dispatch.dispatch_word_via_com",
                return_value=(
                    app,
                    {
                        "binding_source": "versioned_progid",
                        "binding_progid": "Word.Application.11",
                        "attempted_progids": ["Word.Application.11"],
                        "last_diag": {"PID": 1101, "Name": "Microsoft Word"},
                    },
                ),
            ),
        ):
            with self.assertRaises(RuntimeError) as ctx:
                start_app_dispatch_flow(engine, lambda message: message)

        self.assertIn("最低仅支持 Word 2007", str(ctx.exception))
        self.assertIsNone(engine._owned_pid)

    def test_runtime_guard_logs_foreign_process_before_abort(self) -> None:
        from core.word_engine import WordEngine

        engine = WordEngine({})
        engine.app = Mock()
        engine.app.Visible = False
        engine._app_started_ts = 100.0
        engine._logger = Mock()

        with (
            patch("core.word_engine.time.time", return_value=101.0),
            patch("core.word_engine.try_claim_word_process_for_engine", return_value=False),
            patch("core.word_engine.psutil.process_iter", return_value=[_FakeProc(303, "WINWORD.EXE", 206.0)]),
            patch("core.word_engine._visible_window_pids", return_value=set()),
        ):
            with self.assertRaises(RuntimeError):
                engine._runtime_guard_check()

        warning_messages = [str(call.args[0]) for call in engine._logger.warning.call_args_list]
        self.assertTrue(any("[WORD_GUARD_FOREIGN]" in message for message in warning_messages))


if __name__ == "__main__":
    unittest.main()
