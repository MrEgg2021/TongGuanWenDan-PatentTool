from __future__ import annotations

import tempfile
import unittest
import urllib.error
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.cnipa_preview import codeset, library_process
from core.cnipa_preview.models import RendererState


_YML_WITH_BASE_PATH = """server:
  port: 9999
xml2pdf-plugin:
  codeset:
    base-path: http://127.0.0.1:9999/public-base/codeset/findByCode
"""


class _FakeResponse:
    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *_exc) -> bool:
        return False

    def read(self, _limit: int) -> bytes:
        return self._body


class _FakeOpener:
    def __init__(self, effect) -> None:
        self.effect = effect
        self.calls: list[tuple[str, float]] = []

    def open(self, request, timeout=None):
        self.calls.append((request.full_url, timeout))
        if isinstance(self.effect, BaseException):
            raise self.effect
        return self.effect


class CodesetConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def _write_yml(self, text: str) -> None:
        path = self.root / codeset.APPLICATION_YML_RELATIVE_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test_loopback_base_path_wins_over_server_port(self) -> None:
        self._write_yml(
            "server:\n  port: 8080\nxml2pdf-plugin:\n  codeset:\n"
            "    base-path: http://localhost:9999/public-base/codeset/findByCode\n"
        )
        self.assertEqual(
            "http://localhost:9999/public-base/codeset/findByCode",
            codeset.resolve_codeset_endpoint(self.root),
        )

    def test_server_port_builds_the_loopback_path_when_base_path_is_missing(self) -> None:
        self._write_yml("server:\n  port: 9999\n")
        self.assertEqual(
            "http://127.0.0.1:9999/public-base/codeset/findByCode",
            codeset.resolve_codeset_endpoint(self.root),
        )

    def test_non_loopback_base_path_is_not_used_but_server_port_still_is(self) -> None:
        self._write_yml(
            "server:\n  port: 9999\nxml2pdf-plugin:\n  codeset:\n"
            "    base-path: http://10.160.1.246:8001/base/codeset/findByCode\n"
        )
        self.assertEqual(
            "http://127.0.0.1:9999/public-base/codeset/findByCode",
            codeset.resolve_codeset_endpoint(self.root),
        )

    def test_unusable_configuration_reports_no_endpoint(self) -> None:
        cases = {
            "非 loopback 地址且没有端口": "xml2pdf-plugin:\n  codeset:\n    base-path: http://10.160.1.246:8001/base/codeset/findByCode\n",
            "端口不是数字": "server:\n  port: 不是端口\n",
            "层级缺失": "xml2pdf-plugin:\n  other: 1\n",
            "空文档": "",
        }
        for label, text in cases.items():
            with self.subTest(label):
                self._write_yml(text)
                self.assertIsNone(codeset.resolve_codeset_endpoint(self.root))
                state = codeset.detect_codeset_state(self.root, probe=Mock(), start_local=lambda: "")
                self.assertFalse(state.available)
                self.assertEqual(codeset.UNREACHABLE_BASE_PATH, state.base)
                self.assertFalse(state.local_table)

    def test_missing_and_malformed_config_never_raise(self) -> None:
        self.assertIsNone(codeset.read_codeset_endpoint(self.root))
        self.assertIsNone(codeset.resolve_codeset_endpoint(self.root))
        self._write_yml("server:\n  port: 9999\n\tbad-tab: 1\n: : :\n")
        self.assertIsNone(codeset.read_codeset_endpoint(self.root))
        self.assertIsNone(codeset.resolve_codeset_endpoint(self.root))
        (self.root / codeset.APPLICATION_YML_RELATIVE_PATH).write_bytes(b"\xff\xfe\x00binary")
        self.assertIsNone(codeset.read_codeset_endpoint(self.root))


class CodesetProbeTests(unittest.TestCase):
    def test_probe_accepts_a_short_plain_text_answer(self) -> None:
        opener = _FakeOpener(_FakeResponse(200, "中国".encode("utf-8")))
        with patch.object(codeset, "_OPENER", opener):
            self.assertTrue(codeset.probe_endpoint("http://127.0.0.1:9999/public-base/codeset/findByCode"))
        url, timeout = opener.calls[0]
        self.assertIn("codeType=GUOBIE", url)
        self.assertIn("code=CN", url)
        self.assertEqual(codeset.PROBE_TIMEOUT_SECONDS, timeout)

    def test_probe_rejects_http_errors_empty_bodies_and_timeouts(self) -> None:
        cases = {
            "404": _FakeResponse(404, b"not found"),
            "500": _FakeResponse(500, b"boom"),
            "空响应体": _FakeResponse(200, b"   "),
            "连接超时": TimeoutError("timed out"),
            "拒绝连接": urllib.error.URLError(ConnectionRefusedError("refused")),
        }
        for label, effect in cases.items():
            with self.subTest(label), patch.object(codeset, "_OPENER", _FakeOpener(effect)):
                self.assertFalse(codeset.probe_endpoint("http://127.0.0.1:1/base/codeset/findByCode"))


class CodesetStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        path = self.root / codeset.APPLICATION_YML_RELATIVE_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_YML_WITH_BASE_PATH, encoding="utf-8")

    def test_reachable_service_is_used_verbatim(self) -> None:
        start_local = Mock(return_value="http://127.0.0.1:5000/public-base/codeset/findByCode")
        state = codeset.detect_codeset_state(
            self.root, probe=lambda _endpoint, **_kwargs: True, start_local=start_local,
        )
        self.assertTrue(state.available)
        self.assertEqual("http://127.0.0.1:9999/public-base/codeset/findByCode", state.base)
        self.assertIn("9999", state.detail)
        self.assertFalse(state.local_table)
        start_local.assert_not_called()

    def test_unreachable_client_service_switches_to_the_shipped_local_table(self) -> None:
        local_base = "http://127.0.0.1:5000/public-base/codeset/findByCode"
        state = codeset.detect_codeset_state(
            self.root, probe=lambda _endpoint, **_kwargs: False, start_local=lambda: local_base,
        )
        self.assertTrue(state.available)
        self.assertEqual(local_base, state.base)
        self.assertTrue(state.local_table)
        self.assertIn("本机码表", state.detail)
        self.assertIn(local_base, state.detail)

    def test_unreachable_client_service_falls_back_to_the_unroutable_base_without_the_local_table(self) -> None:
        state = codeset.detect_codeset_state(
            self.root, probe=lambda _endpoint, **_kwargs: False, start_local=lambda: "",
        )
        self.assertFalse(state.available)
        self.assertEqual(codeset.UNREACHABLE_BASE_PATH, state.base)
        self.assertFalse(state.local_table)
        self.assertIn("不", state.detail)

    def test_missing_configuration_never_probes(self) -> None:
        probe = Mock()
        state = codeset.detect_codeset_state(self.root / "missing", probe=probe, start_local=lambda: "")
        self.assertFalse(state.available)
        self.assertEqual(codeset.UNREACHABLE_BASE_PATH, state.base)
        probe.assert_not_called()

    def test_missing_configuration_still_uses_the_shipped_local_table(self) -> None:
        local_base = "http://127.0.0.1:5001/public-base/codeset/findByCode"
        state = codeset.detect_codeset_state(
            self.root / "missing", probe=Mock(), start_local=lambda: local_base,
        )
        self.assertTrue(state.available)
        self.assertEqual(local_base, state.base)
        self.assertTrue(state.local_table)

    def test_java_options_cover_available_unavailable_and_explicit_base(self) -> None:
        available = codeset.CodesetState(True, "http://127.0.0.1:9999/public-base/codeset/findByCode", "ok")
        unavailable = codeset.CodesetState(False, codeset.UNREACHABLE_BASE_PATH, "down")
        self.assertEqual(
            (
                "-Decloud.service.base=http://127.0.0.1:9999/public-base/codeset/findByCode",
                "-Dsun.net.client.defaultConnectTimeout=1500",
                "-Dsun.net.client.defaultReadTimeout=5000",
            ),
            codeset.java_options(available),
        )
        self.assertIn(f"-Decloud.service.base={codeset.UNREACHABLE_BASE_PATH}", codeset.java_options(unavailable))
        self.assertIn(f"-Decloud.service.base={codeset.UNREACHABLE_BASE_PATH}", codeset.java_options())
        self.assertIn("-Decloud.service.base=http://127.0.0.1:9999/x", codeset.java_options("http://127.0.0.1:9999/x"))


class _LibraryManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.java = self.root / "java.exe"
        self.java.write_text("stub", encoding="utf-8")
        self.client = SimpleNamespace(
            root=self.root, java=self.java, libraries=(), watched=(), signature=(),
        )
        self.manager = library_process.InstalledLibraryManager()
        self.manager._client = self.client

    def _run(self) -> None:
        self.manager._process = Mock()
        self.manager._process.poll.return_value = None
        self.manager._state = RendererState.RUNNING

    def test_command_line_carries_codeset_address_and_bounded_timeouts(self) -> None:
        available = codeset.CodesetState(True, "http://127.0.0.1:9999/public-base/codeset/findByCode", "ok")
        command = library_process.build_java_command(self.client, self.root, 1024, available.base)
        self.assertIn("-Decloud.service.base=http://127.0.0.1:9999/public-base/codeset/findByCode", command)
        self.assertIn("-Dsun.net.client.defaultConnectTimeout=1500", command)
        self.assertIn("-Dsun.net.client.defaultReadTimeout=5000", command)
        self.assertEqual(str(self.java), command[0])
        self.assertIn("-Xmx1024m", command)
        self.assertIn(str(self.root / "classpath.jar"), command)
        self.assertEqual("groovy.ui.GroovyMain", command[-2])
        self.assertEqual(str(self.root / "render.groovy"), command[-1])

    def test_unavailable_codeset_uses_the_unroutable_fallback_address(self) -> None:
        command = library_process.build_java_command(
            self.client, self.root, 768, codeset.UNREACHABLE_BASE_PATH, extra_flags=("-Dx=y",),
        )
        self.assertIn(f"-Decloud.service.base={codeset.UNREACHABLE_BASE_PATH}", command)
        self.assertIn("-Dx=y", command)

    def test_start_once_launches_java_with_the_detected_codeset_address(self) -> None:
        self.manager._codeset = codeset.CodesetState(
            True, "http://127.0.0.1:9999/public-base/codeset/findByCode", "ok",
        )
        popen = Mock(return_value=SimpleNamespace(stdout=iter(()), stdin=Mock(), poll=lambda: None))
        with (
            patch.object(library_process, "get_user_data_dir", return_value=str(self.root)),
            patch.object(library_process.subprocess, "Popen", popen),
            patch.object(self.manager, "_wait", return_value={"ready": True}),
        ):
            self.manager._start_once(self.client, heap_mib=1024, java_data_model=64)
            self.addCleanup(self.manager._workspace.cleanup)
        command = popen.call_args.args[0]
        self.assertIn("-Decloud.service.base=http://127.0.0.1:9999/public-base/codeset/findByCode", command)
        self.assertIn("-Dsun.net.client.defaultConnectTimeout=1500", command)
        self.assertIn("-Dsun.net.client.defaultReadTimeout=5000", command)
        self.assertEqual(RendererState.RUNNING, self.manager.state_info().state)

    def test_codeset_change_restarts_the_running_jvm_and_unchanged_state_reuses_it(self) -> None:
        self._run()
        self.manager._codeset = codeset.CodesetState(False, codeset.UNREACHABLE_BASE_PATH, "down")
        ready = codeset.CodesetState(True, "http://127.0.0.1:9999/public-base/codeset/findByCode", "up")
        with (
            patch.object(library_process, "detect_codeset_state", return_value=ready) as detect,
            patch.object(self.manager, "_start") as start,
            patch.object(self.manager, "_stop") as stop,
        ):
            self.manager._ensure_ready()
            start.assert_called_once()
            self.assertEqual(ready.base, self.manager.codeset_state().base)
            self.assertTrue(self.manager.codeset_state().available)
            stop.assert_called_once()
            self.manager._ensure_ready()
            self.assertEqual(1, start.call_count)
            self.assertEqual(2, detect.call_count)

    def test_document_render_does_not_probe_the_codeset_service_again(self) -> None:
        self._run()
        with (
            patch.object(library_process, "detect_codeset_state") as detect,
            patch.object(self.manager, "_start") as start,
        ):
            self.manager._ensure_ready(refresh_codeset=False)
        detect.assert_not_called()
        start.assert_not_called()

    def test_switching_between_client_and_local_table_restarts_the_jvm(self) -> None:
        self._run()
        local = codeset.CodesetState(
            True, "http://127.0.0.1:5000/public-base/codeset/findByCode", "本机码表", local_table=True,
        )
        client = codeset.CodesetState(True, "http://127.0.0.1:9999/public-base/codeset/findByCode", "客户端")
        with (
            patch.object(library_process, "detect_codeset_state", return_value=local),
            patch.object(self.manager, "_start") as start,
            patch.object(self.manager, "_stop") as stop,
        ):
            self.manager._ensure_ready()
            self.assertTrue(self.manager.codeset_state().local_table)
            self.assertEqual(local.base, self.manager.codeset_state().base)
            stop.assert_called_once()
            with patch.object(library_process, "detect_codeset_state", return_value=client):
                self.manager._ensure_ready()
            self.assertEqual(2, start.call_count)
            self.assertEqual(2, stop.call_count)

    def test_prewarm_path_starts_the_shipped_local_table_when_the_client_is_silent(self) -> None:
        self.addCleanup(library_process.stop_local_codeset_server)
        with patch.object(self.manager, "_start") as start:
            self.manager._ensure_ready()
        start.assert_called_once()
        state = self.manager.codeset_state()
        self.assertTrue(state.available)
        self.assertTrue(state.local_table)
        self.assertTrue(state.base.startswith("http://127.0.0.1:"))

    def test_shutdown_stops_the_shipped_local_table(self) -> None:
        with patch.object(library_process, "stop_local_codeset_server") as stop:
            self.manager.shutdown()
        stop.assert_called_once()


if __name__ == "__main__":
    unittest.main()
