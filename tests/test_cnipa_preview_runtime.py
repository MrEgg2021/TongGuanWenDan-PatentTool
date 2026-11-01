from __future__ import annotations

import json
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from core.cnipa_preview.models import RendererState, RuntimeImportDisposition, RuntimeImportPhase, RuntimeSourceKind
from core.cnipa_preview.runtime import (
    ACTIVE_RUNTIME_STATE_NAME,
    CnipaRuntimeManager,
    IMPORT_FREE_SPACE_MARGIN_BYTES,
    MANAGED_RUNTIME_FILES_NAME,
    PreviewRuntimeError,
    REQUIRED_RUNTIME_FILES,
    REQUIRED_RUNTIME_SOURCE_PATHS,
    RuntimeImportBusyError,
    RuntimeImportCancelled,
    RuntimeInsufficientSpaceError,
    _runtime_import_lock,
    _write_loopback_server_config,
    discover_installed_client_candidates,
    get_active_managed_runtime,
    import_runtime_source,
    inspect_runtime_source,
    reconcile_managed_runtime_residue,
)


_FILE_PATHS = {
    "commons/NOTICE",
    "plugins/as/cpc-main-as/bin/wrapper.jar",
    "plugins/as/cpc-main-as/bin/win32/wrapper.exe",
    "plugins/as/cpc-main-as/bin/win32/wrapper.dll",
    "plugins/as/cpc-main-as/bin/win32/wrapper.conf",
    "plugins/as/cpc-main-as/db/cpc.ini",
    "plugins/as/cpc-main-as/db/dzsq-guojia.db",
}


def _write_client(root: Path, *, marker: str = "one", missing: str = "") -> None:
    for relative in REQUIRED_RUNTIME_SOURCE_PATHS:
        target = root / Path(relative)
        if relative == missing:
            continue
        if relative in _FILE_PATHS:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(f"{relative}:{marker}", encoding="utf-8")
        else:
            target.mkdir(parents=True, exist_ok=True)
            placeholder = target / "payload.bin"
            placeholder.write_bytes(f"{relative}:{marker}".encode("utf-8"))
    for relative in REQUIRED_RUNTIME_FILES:
        target = root / Path(relative)
        if relative == missing or any(relative.startswith(missing.rstrip("/") + "/") for _ in (0,) if missing):
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if relative.endswith("application.yml"):
            target.write_text("server:\n  port: 9999\nspring:\n  application:\n    name: test\n", encoding="utf-8")
        else:
            target.write_bytes(f"{relative}:{marker}".encode("utf-8"))


def _write_archive(client_root: Path, destination: Path, *, unsafe: str = "") -> None:
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("runtime-manifest.json", json.dumps({"version": "test-runtime"}))
        for path in sorted(client_root.rglob("*")):
            if path.is_file():
                archive.write(path, (Path("CNIPAClient") / path.relative_to(client_root)).as_posix())
        if unsafe == "traversal":
            archive.writestr("../outside.txt", "forbidden")
        elif unsafe == "duplicate":
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                archive.writestr("CNIPAClient/commons/NOTICE", "duplicate")
        elif unsafe == "link":
            link = zipfile.ZipInfo("CNIPAClient/commons/link")
            link.create_system = 3
            link.external_attr = 0o120777 << 16
            archive.writestr(link, "../outside")


def _plenty_of_space(_path) -> SimpleNamespace:
    return SimpleNamespace(free=8 * 1024 * 1024 * 1024)


class CnipaPreviewRuntimeInspectionTests(unittest.TestCase):
    def test_inspects_complete_directory_and_missing_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            client = root / "CNIPAClient"
            _write_client(client)

            complete = inspect_runtime_source(client, RuntimeSourceKind.INSTALLED_CLIENT)
            missing = inspect_runtime_source(root / "wrong", RuntimeSourceKind.INSTALLED_CLIENT)

            self.assertTrue(complete.compatible)
            self.assertGreater(complete.total_bytes, 0)
            self.assertFalse(missing.compatible)
            self.assertIn("CNIPAClient 根目录", missing.missing_items)

    def test_discovers_remembered_and_standard_paths_without_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            drive = Path(tmpdir)
            client = drive / "Program Files (x86)" / "CNIPAClient"
            _write_client(client)

            results = discover_installed_client_candidates(
                remembered_path=client,
                registry_paths=(client,),
                fixed_drives=(drive,),
            )

            self.assertEqual(1, len(results))
            self.assertTrue(results[0].compatible)
            self.assertEqual(client.resolve(), Path(results[0].source_path))

    def test_reports_missing_required_subtree(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            client = Path(tmpdir) / "CNIPAClient"
            _write_client(client, missing="plugins/as/cpc-main-as/data/fop-plugin")

            result = inspect_runtime_source(client)

            self.assertFalse(result.compatible)
            self.assertIn("plugins/as/cpc-main-as/data/fop-plugin", result.missing_items)

    def test_rejects_unsafe_duplicate_and_link_archive_members(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            client = root / "CNIPAClient"
            _write_client(client)
            for unsafe, expected in (("traversal", "不安全路径"), ("duplicate", "重复成员"), ("link", "链接成员")):
                archive = root / f"{unsafe}.zip"
                _write_archive(client, archive, unsafe=unsafe)
                inspection = inspect_runtime_source(archive, RuntimeSourceKind.ARCHIVE)
                self.assertFalse(inspection.compatible)
                self.assertIn(expected, "；".join(inspection.diagnostics))


class CnipaPreviewRuntimeImportTests(unittest.TestCase):
    def test_same_content_reimport_reuses_active_runtime_without_creating_a_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            client = root / "CNIPAClient"
            storage = root / "storage"
            _write_client(client)
            first = import_runtime_source(
                client,
                storage_root=storage,
                health_check=lambda _root: True,
                disk_usage=_plenty_of_space,
            )
            phases = []

            def unexpected_health(_root: Path) -> bool:
                raise AssertionError("same content must not start another health probe")

            second = import_runtime_source(
                client,
                storage_root=storage,
                health_check=unexpected_health,
                disk_usage=lambda _path: (_ for _ in ()).throw(AssertionError("reuse must not check free space")),
                phase_progress=phases.append,
            )

            self.assertEqual(RuntimeImportDisposition.REUSED, second.disposition)
            self.assertEqual(first.runtime_id, second.runtime.runtime_id)
            self.assertEqual([Path(first.private_root)], list(storage.glob("runtime-*")))
            self.assertEqual(RuntimeImportPhase.DONE, phases[-1].phase)

    def test_directory_and_zip_import_have_same_layout_and_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            client = root / "CNIPAClient"
            archive = root / "runtime.zip"
            storage = root / "storage"
            _write_client(client)
            _write_archive(client, archive)

            first = import_runtime_source(
                client,
                storage_root=storage,
                health_check=lambda _root: True,
                disk_usage=_plenty_of_space,
            )
            second = import_runtime_source(
                archive,
                RuntimeSourceKind.ARCHIVE,
                storage_root=storage,
                health_check=lambda _root: True,
                disk_usage=_plenty_of_space,
                force=True,
            )

            self.assertEqual(first.content_fingerprint, second.content_fingerprint)
            self.assertFalse(Path(first.private_root).exists())
            self.assertTrue((Path(second.private_root) / MANAGED_RUNTIME_FILES_NAME).is_file())
            active = get_active_managed_runtime(storage)
            self.assertIsNotNone(active)
            self.assertEqual(second.runtime_id, active.runtime_id)

    def test_insufficient_space_stops_before_staging(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            client = root / "CNIPAClient"
            storage = root / "storage"
            _write_client(client)

            with self.assertRaises(RuntimeInsufficientSpaceError):
                import_runtime_source(
                    client,
                    storage_root=storage,
                    health_check=lambda _root: True,
                    disk_usage=lambda _path: SimpleNamespace(free=IMPORT_FREE_SPACE_MARGIN_BYTES - 1),
                )

            self.assertFalse(any(storage.glob(".staging-*")))
            self.assertFalse((storage / ACTIVE_RUNTIME_STATE_NAME).exists())

    def test_cancel_removes_staging_and_keeps_active_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            client = root / "CNIPAClient"
            storage = root / "storage"
            _write_client(client)
            first = import_runtime_source(
                client,
                storage_root=storage,
                health_check=lambda _root: True,
                disk_usage=_plenty_of_space,
            )
            requested = False

            def progress(_copied: int, _total: int, _label: str) -> None:
                nonlocal requested
                requested = True

            with self.assertRaises(RuntimeImportCancelled):
                import_runtime_source(
                    client,
                    storage_root=storage,
                    progress=progress,
                    cancelled=lambda: requested,
                    health_check=lambda _root: True,
                    disk_usage=_plenty_of_space,
                    force=True,
                )

            self.assertEqual(first.runtime_id, get_active_managed_runtime(storage).runtime_id)
            self.assertFalse(any(storage.glob(".staging-*")))

    def test_health_failure_preserves_old_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            client = root / "CNIPAClient"
            storage = root / "storage"
            _write_client(client, marker="old")
            first = import_runtime_source(
                client,
                storage_root=storage,
                health_check=lambda _root: True,
                disk_usage=_plenty_of_space,
            )
            _write_client(client, marker="new")

            with self.assertRaisesRegex(PreviewRuntimeError, "健康检查"):
                import_runtime_source(
                    client,
                    storage_root=storage,
                    health_check=lambda _root: False,
                    disk_usage=_plenty_of_space,
                )

            active = get_active_managed_runtime(storage)
            self.assertEqual(first.runtime_id, active.runtime_id)
            self.assertTrue(Path(first.private_root).is_dir())

    def test_cleanup_failure_keeps_new_runtime_and_reports_residue(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            client = root / "CNIPAClient"
            storage = root / "storage"
            _write_client(client, marker="old")
            first = import_runtime_source(
                client,
                storage_root=storage,
                health_check=lambda _root: True,
                disk_usage=_plenty_of_space,
            )
            _write_client(client, marker="new")

            def cleanup(path: Path, *args, **kwargs) -> None:
                if Path(path) == Path(first.private_root):
                    raise OSError("locked")
                import shutil

                shutil.rmtree(path, *args, **kwargs)

            second = import_runtime_source(
                client,
                storage_root=storage,
                health_check=lambda _root: True,
                disk_usage=_plenty_of_space,
                cleanup_tree=cleanup,
            )

            self.assertEqual(first.private_root, second.cleanup_warning_path)
            self.assertEqual(second.runtime_id, get_active_managed_runtime(storage).runtime_id)

    def test_corrupt_pointer_and_missing_file_are_not_reported_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            client = root / "CNIPAClient"
            storage = root / "storage"
            _write_client(client)
            info = import_runtime_source(
                client,
                storage_root=storage,
                health_check=lambda _root: True,
                disk_usage=_plenty_of_space,
            )
            (Path(info.private_root) / "CNIPAClient" / Path(REQUIRED_RUNTIME_FILES[0])).unlink()
            self.assertEqual("invalid", get_active_managed_runtime(storage).status)
            (storage / ACTIVE_RUNTIME_STATE_NAME).write_text("not-json", encoding="utf-8")
            with self.assertRaisesRegex(PreviewRuntimeError, "指针损坏"):
                get_active_managed_runtime(storage)

    def test_import_lock_rejects_concurrent_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            client = root / "CNIPAClient"
            storage = root / "storage"
            _write_client(client)
            with _runtime_import_lock(storage, 0.0):
                with self.assertRaises(RuntimeImportBusyError):
                    import_runtime_source(
                        client,
                        storage_root=storage,
                        health_check=lambda _root: True,
                        disk_usage=_plenty_of_space,
                    )

    def test_source_files_are_not_modified_and_loopback_config_is_private(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            client = root / "CNIPAClient"
            storage = root / "storage"
            _write_client(client)
            source_config = client / "plugins/as/cpc-main-as/conf/application.yml"
            before = source_config.read_bytes()
            info = import_runtime_source(
                client,
                storage_root=storage,
                health_check=lambda _root: True,
                disk_usage=_plenty_of_space,
            )
            private_config = Path(info.private_root) / "CNIPAClient/plugins/as/cpc-main-as/conf/application.yml"
            _write_loopback_server_config(private_config, 19099)

            self.assertEqual(before, source_config.read_bytes())
            self.assertIn("address: 127.0.0.1", private_config.read_text(encoding="utf-8"))
            self.assertIn("port: 19099", private_config.read_text(encoding="utf-8"))


class CnipaPreviewRuntimeReuseTests(unittest.TestCase):
    def test_healthy_managed_process_is_reused_without_starting_another_one(self) -> None:
        class _Process:
            @staticmethod
            def poll():
                return None

        class _Response:
            status_code = 200

        started = False

        def process_factory(*_args, **_kwargs):
            nonlocal started
            started = True
            raise AssertionError("a healthy managed renderer must be reused")

        manager = CnipaRuntimeManager(
            request_get=lambda *_args, **_kwargs: _Response(),
            process_factory=process_factory,
        )
        manager._process = _Process()
        manager._base_url = "http://127.0.0.1:19123"
        manager._runtime_id = "runtime"
        manager._state = RendererState.RUNNING

        with patch.object(manager, "ensure_runtime", return_value=SimpleNamespace(version="runtime")):
            self.assertTrue(manager.is_running())
            self.assertEqual("http://127.0.0.1:19123", manager.ensure_running())
        self.assertFalse(started)

    def test_runtime_identity_mismatch_is_not_reused(self) -> None:
        class _Process:
            @staticmethod
            def poll():
                return None

        class _Response:
            status_code = 200

        manager = CnipaRuntimeManager(request_get=lambda *_args, **_kwargs: _Response())
        manager._process = _Process()
        manager._base_url = "http://127.0.0.1:19123"
        manager._runtime_id = "old-runtime"
        manager._state = RendererState.RUNNING

        with patch.object(manager, "ensure_runtime", return_value=SimpleNamespace(version="new-runtime")):
            self.assertFalse(manager.is_running())

    def test_candidate_renderer_is_handed_to_session_manager_without_second_start(self) -> None:
        class _Process:
            @staticmethod
            def poll():
                return None

        manager = CnipaRuntimeManager()
        candidate = CnipaRuntimeManager()
        old_process = _Process()
        candidate_process = _Process()
        manager._process = old_process
        manager._base_url = "http://127.0.0.1:19121"
        manager._runtime_id = "runtime-old"
        manager._state = RendererState.RUNNING
        candidate._process = candidate_process
        candidate._base_url = "http://127.0.0.1:19122"
        candidate._runtime_id = "runtime-new"
        candidate._state = RendererState.RUNNING

        with patch.object(manager, "_stop_process") as stop_process:
            manager.adopt_candidate(candidate)

        stop_process.assert_called_once_with(old_process)
        self.assertIs(candidate_process, manager._process)
        self.assertEqual("http://127.0.0.1:19122", manager._base_url)
        self.assertEqual("runtime-new", manager._runtime_id)
        self.assertEqual(RendererState.RUNNING, manager.state_info().state)
        self.assertEqual(RendererState.STOPPED, candidate.state_info().state)

    def test_render_session_blocks_reimport_while_pdf_generation_is_active(self) -> None:
        manager = CnipaRuntimeManager()
        with patch.object(manager, "ensure_running", return_value="http://127.0.0.1:19123"):
            with manager.render_session() as base_url:
                self.assertEqual("http://127.0.0.1:19123", base_url)
                self.assertTrue(manager.is_rendering())
                with self.assertRaisesRegex(RuntimeImportBusyError, "正在生成 PDF"):
                    with manager.render_session():
                        pass
        self.assertFalse(manager.is_rendering())


class CnipaPreviewRuntimeResidueTests(unittest.TestCase):
    def _prepare_active_runtime(self, root: Path):
        client = root / "CNIPAClient"
        storage = root / "storage"
        _write_client(client)
        active = import_runtime_source(
            client,
            storage_root=storage,
            health_check=lambda _root: True,
            disk_usage=_plenty_of_space,
        )
        return storage, active

    @staticmethod
    def _private_wrapper(runtime_root: Path) -> Path:
        wrapper = runtime_root / "CNIPAClient/plugins/as/cpc-main-as/bin/win32/wrapper.exe"
        wrapper.parent.mkdir(parents=True, exist_ok=True)
        wrapper.write_bytes(b"wrapper")
        return wrapper

    def test_reconcile_stops_current_user_old_private_renderer_and_removes_its_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            storage, active = self._prepare_active_runtime(Path(tmpdir))
            old_root = storage / "runtime-old"
            wrapper = self._private_wrapper(old_root)
            stopped: list[int] = []
            process = SimpleNamespace(
                info={
                    "pid": 1234,
                    "exe": str(wrapper),
                    "cmdline": [str(wrapper), "-c", "wrapper.conf"],
                    "username": "current-user",
                }
            )

            result = reconcile_managed_runtime_residue(
                storage,
                process_iter=lambda: (process,),
                current_user="current-user",
                stop_process_tree=stopped.append,
            )

            self.assertEqual([1234], stopped)
            self.assertIn(str(old_root), result.removed_paths)
            self.assertFalse(old_root.exists())
            self.assertTrue(Path(active.private_root).exists())

    def test_reconcile_preserves_another_users_private_renderer(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            storage, _active = self._prepare_active_runtime(Path(tmpdir))
            old_root = storage / "runtime-other-user"
            wrapper = self._private_wrapper(old_root)
            process = SimpleNamespace(
                info={
                    "pid": 4321,
                    "exe": str(wrapper),
                    "cmdline": [str(wrapper), "-c", "wrapper.conf"],
                    "username": "other-user",
                }
            )

            result = reconcile_managed_runtime_residue(
                storage,
                process_iter=lambda: (process,),
                current_user="current-user",
                stop_process_tree=lambda _pid: self.fail("other user process must not be stopped"),
            )

            self.assertIn(str(old_root), result.residual_paths)
            self.assertTrue(old_root.exists())


if __name__ == "__main__":
    unittest.main()
