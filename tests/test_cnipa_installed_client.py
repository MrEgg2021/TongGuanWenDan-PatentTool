from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.cnipa_preview import installed_client as source
from core.cnipa_preview import library_process as runtime
from core.cnipa_preview.form_renderer import FormRenderCancelled
from core.cnipa_preview.models import RendererState
from core.cnipa_preview.runtime import PreviewRuntimeError


class InstalledClientTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.java = self.root / "commons/jre/win32/jre8/bin/java.exe"
        self.config = self.root / "plugins/as/cpc-main-as/bin/win32/wrapper.conf"
        self.jar = self.root / "commons/groovy-all-test.jar"
        for path in (self.java, self.config, self.jar):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("test", encoding="utf-8")
        self.config.write_text(
            "wrapper.java.classpath.2=%COMMONS_HOME%/groovy-all-test.jar\n"
            "wrapper.java.classpath.1=%APP_HOME%/conf\n", encoding="utf-8")

    def test_inspection_manifest_and_missing_components(self):
        client = source.inspect_installed_client(self.root)
        self.assertEqual((self.jar,), client.libraries)
        manifest = source.java_classpath_manifest(client).decode("ascii").replace("\r\n ", "")
        self.assertIn(self.jar.as_uri(), manifest)
        self.assertNotIn("/conf", manifest)
        self.jar.unlink()
        with self.assertRaisesRegex(PreviewRuntimeError, "预览组件缺失"):
            source.inspect_installed_client(self.root)

    def test_heap_policy_uses_java_data_model_and_safe_fallback(self):
        manager = runtime.InstalledLibraryManager()
        with patch.object(
            runtime.subprocess,
            "run",
            return_value=SimpleNamespace(stdout="    sun.arch.data.model = 32\n"),
        ) as run:
            self.assertEqual(32, manager._java_data_model(self.java))
            run.assert_called_once()
        self.assertEqual((1536, 1024), manager._heap_candidates(64))
        self.assertEqual((1024, 768), manager._heap_candidates(32))
        self.assertEqual((1024, 768), manager._heap_candidates(0))

    def test_heap_reservation_failure_retries_with_smaller_heap(self):
        manager = runtime.InstalledLibraryManager()
        client = source.inspect_installed_client(self.root)
        with (
            patch.object(manager, "_java_data_model", return_value=32),
            patch.object(
                manager,
                "_start_once",
                side_effect=[PreviewRuntimeError("Could not reserve enough space for 1048576KB object heap"), None],
            ) as start_once,
            patch.object(manager, "_stop") as stop,
        ):
            manager._start(client)
        self.assertEqual(
            [
                ((client,), {"heap_mib": 1024, "java_data_model": 32, "cancelled": None, "startup_wait_callback": None}),
                ((client,), {"heap_mib": 768, "java_data_model": 32, "cancelled": None, "startup_wait_callback": None}),
            ],
            start_once.call_args_list,
        )
        stop.assert_called_once()

    def test_saved_path_avoids_discovery_and_update_reinspects(self):
        manager = runtime.InstalledLibraryManager()
        with (
            patch.object(runtime, "remembered_client_path", return_value=str(self.root)),
            patch.object(runtime, "detect_client") as detect,
            patch.object(runtime, "inspect_installed_client", wraps=source.inspect_installed_client) as inspect,
            patch.object(manager, "_stop") as stop,
        ):
            original = manager._resolve_client()
            self.assertIs(original, manager._resolve_client())
            inspect.assert_called_once()
            self.jar.write_text("updated-library", encoding="utf-8")
            self.assertNotEqual(original.signature, manager._resolve_client().signature)
            self.assertEqual(2, inspect.call_count)
            stop.assert_called_once()
            detect.assert_not_called()

    def test_missing_client_is_not_repeatedly_discovered_and_manual_choice_recovers(self):
        manager = runtime.InstalledLibraryManager()
        with (
            patch.object(runtime, "remembered_client_path", return_value=None),
            patch.object(runtime, "detect_client", side_effect=PreviewRuntimeError(source.CLIENT_MISSING)) as detect,
            patch.object(runtime, "remember_client") as remember,
        ):
            for _ in range(2):
                with self.assertRaisesRegex(PreviewRuntimeError, "没有检测到已安装"):
                    manager._resolve_client()
            detect.assert_called_once()
            manager.configure(str(self.root))
            remember.assert_called_once()
            self.assertEqual("", manager.configuration_error())
            self.assertEqual(self.root, manager._resolve_client().root)

    def test_configuring_unchanged_client_preserves_running_process(self):
        manager = runtime.InstalledLibraryManager()
        manager._client = source.inspect_installed_client(self.root)
        manager._process = Mock()
        manager._process.poll.return_value = None
        manager._state = RendererState.RUNNING
        with (
            patch.object(runtime, "remember_client") as remember,
            patch.object(manager, "_stop") as stop,
        ):
            configured = manager.configure(str(self.root))
        self.assertEqual(self.root, configured.root)
        self.assertTrue(manager.is_running())
        stop.assert_not_called()
        remember.assert_called_once_with(configured)

    def test_configuring_updated_client_stops_running_process(self):
        manager = runtime.InstalledLibraryManager()
        manager._client = source.inspect_installed_client(self.root)
        original_signature = manager._client.signature
        self.jar.write_text("updated-library", encoding="utf-8")
        with (
            patch.object(runtime, "remember_client"),
            patch.object(manager, "_stop") as stop,
        ):
            configured = manager.configure(str(self.root))
        self.assertNotEqual(original_signature, configured.signature)
        self.assertEqual(configured.signature, manager._client.signature)
        stop.assert_called_once()

    def test_missing_cached_component_requires_reselection(self):
        manager = runtime.InstalledLibraryManager()
        manager._client = source.inspect_installed_client(self.root)
        self.java.unlink()
        with patch.object(runtime, "detect_client") as detect:
            with self.assertRaisesRegex(PreviewRuntimeError, "重新检测"):
                manager._resolve_client()
            self.assertEqual(RendererState.FAILED, manager.state_info().state)
            detect.assert_not_called()

    def test_render_paths_are_forward_slash_and_cancel_stops_owned_process(self):
        manager = runtime.InstalledLibraryManager()
        manager._client = source.inspect_installed_client(self.root)
        manager._workspace = SimpleNamespace(name=str(self.root))
        manager._process = Mock()
        xml = self.root / "100001.xml"
        xml.write_text("<x/>", encoding="utf-8")
        def reply(**_kwargs):
            (self.root / "output.pdf").write_bytes(b"%PDF-test")
            return {"ok": True}
        with patch.object(manager, "_ensure_ready"), patch.object(manager, "_wait", side_effect=reply):
            self.assertEqual(b"%PDF-test", manager.render_document(xml, "100001"))
        request = json.loads(manager._process.stdin.write.call_args.args[0])
        self.assertNotIn("\\", request["output"])
        self.assertEqual(xml.as_posix(), request["xml"])
        with patch.object(manager, "_ensure_ready"), patch.object(manager, "_stop") as stop:
            with self.assertRaises(FormRenderCancelled):
                manager.render_document(xml, "100001", cancelled=lambda: True)
            stop.assert_called_once()

    def test_startup_is_reused_and_shutdown_cancels_waiters(self):
        manager = runtime.InstalledLibraryManager()
        client = source.inspect_installed_client(self.root)
        running = False
        def start(*_args, **_kwargs):
            nonlocal running
            running = True
        with (
            patch.object(manager, "_resolve_client", return_value=client),
            patch.object(manager, "is_running", side_effect=lambda: running),
            patch.object(manager, "_start", side_effect=start) as launch,
            patch.object(manager, "_stop"),
        ):
            manager.prewarm()
            with manager.library_session():
                self.assertTrue(manager.is_rendering())
            self.assertFalse(manager.is_rendering())
            launch.assert_called_once()
            manager.shutdown()
            with self.assertRaises(FormRenderCancelled):
                manager.prewarm()

    def test_update_during_render_rejects_output_and_timeout_stops_process(self):
        manager = runtime.InstalledLibraryManager()
        manager._client = source.inspect_installed_client(self.root)
        manager._workspace = SimpleNamespace(name=str(self.root))
        manager._process = Mock()
        manager._process.poll.return_value = None
        xml = self.root / "100001.xml"
        def updated_reply(**_kwargs):
            self.jar.write_text("client-updated-during-render", encoding="utf-8")
            return {"ok": True}
        with (
            patch.object(manager, "_ensure_ready"),
            patch.object(manager, "_wait", side_effect=updated_reply),
            patch.object(manager, "_stop") as stop,
        ):
            with self.assertRaisesRegex(PreviewRuntimeError, "预览期间发生变化"):
                manager.render_document(xml, "100001")
            stop.assert_called_once()

    def test_memory_failure_stops_owned_process_and_preserves_configuration(self):
        manager = runtime.InstalledLibraryManager()
        manager._client = source.inspect_installed_client(self.root)
        manager._workspace = SimpleNamespace(name=str(self.root))
        manager._process = Mock()
        manager._process.poll.return_value = None

        def memory_failure(**_kwargs):
            manager._memory_exhausted = True
            return {"ok": False, "message": "XmlParseException"}

        with (
            patch.object(manager, "_ensure_ready"),
            patch.object(manager, "_wait", side_effect=memory_failure),
            patch.object(manager, "_stop") as stop,
        ):
            with self.assertRaisesRegex(PreviewRuntimeError, "内存不足"):
                manager.render_document(self.root / "100002.xml", "100002")
            stop.assert_called_once()
        self.assertEqual(manager.configuration_error(), "")
        with (
            patch.object(manager, "_ensure_ready"),
            patch.object(manager, "_wait", side_effect=TimeoutError("timeout")),
            patch.object(manager, "_stop") as stop,
        ):
            with self.assertRaises(TimeoutError):
                manager.render_document(self.root / "100001.xml", "100001")
            stop.assert_called_once()


if __name__ == "__main__":
    unittest.main()
