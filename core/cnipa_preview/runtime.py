from __future__ import annotations

import atexit
import contextlib
import ctypes
import hashlib
import json
import os
import getpass
import shutil
import socket
import stat
import subprocess
import threading
import time
import uuid
import zipfile
from collections.abc import Callable, Iterable, Iterator
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any

import requests

if TYPE_CHECKING:
    from .library_process import InstalledLibraryManager

from core.paths_utils import get_machine_data_dir, get_user_data_dir

from .models import (
    ManagedRuntimeInfo,
    RendererState,
    RendererStateInfo,
    RuntimeCleanupReport,
    RuntimeImportDisposition,
    RuntimeImportPhase,
    RuntimeImportProgress,
    RuntimeImportResult,
    RuntimeSourceInspection,
    RuntimeSourceKind,
)


RUNTIME_MANIFEST_NAME = "runtime-manifest.json"
MANAGED_RUNTIME_METADATA_NAME = "managed-runtime.json"
MANAGED_RUNTIME_FILES_NAME = "runtime-files.json"
ACTIVE_RUNTIME_STATE_NAME = "active-runtime.json"
IMPORT_LOCK_NAME = ".runtime-import.lock"
IMPORT_FREE_SPACE_MARGIN_BYTES = 512 * 1024 * 1024
RUNTIME_START_TIMEOUT_SECONDS = 300.0

# Paths are relative to a selected CNIPAClient root. Inspection, import and the
# support-archive builder all use this one contract.
REQUIRED_RUNTIME_SOURCE_PATHS = (
    "commons/NOTICE",
    "commons/jre",
    "commons/lib",
    "plugins/as/cpc-main-as/bin/wrapper.jar",
    "plugins/as/cpc-main-as/bin/win32/wrapper.exe",
    "plugins/as/cpc-main-as/bin/win32/wrapper.dll",
    "plugins/as/cpc-main-as/bin/win32/wrapper.conf",
    "plugins/as/cpc-main-as/conf",
    "plugins/as/cpc-main-as/lib",
    "plugins/as/cpc-main-as/db/cpc.ini",
    "plugins/as/cpc-main-as/db/dzsq-guojia.db",
    "plugins/as/cpc-main-as/data/fop-plugin",
)

REQUIRED_RUNTIME_FILES = (
    "commons/jre/win32/jre8/bin/java.exe",
    "commons/lib/ecloud-plugin-xml2pdf-forms-1.0.0-20220823.041550-626.jar",
    "plugins/as/cpc-main-as/bin/win32/wrapper.exe",
    "plugins/as/cpc-main-as/bin/win32/wrapper.conf",
    "plugins/as/cpc-main-as/conf/application.yml",
    "plugins/as/cpc-main-as/db/dzsq-guojia.db",
    "plugins/as/cpc-main-as/data/fop-plugin/fop-plugin.xml",
)

_SOURCE_FILE_PATHS = frozenset(
    {
        "commons/NOTICE",
        "plugins/as/cpc-main-as/bin/wrapper.jar",
        "plugins/as/cpc-main-as/bin/win32/wrapper.exe",
        "plugins/as/cpc-main-as/bin/win32/wrapper.dll",
        "plugins/as/cpc-main-as/bin/win32/wrapper.conf",
        "plugins/as/cpc-main-as/db/cpc.ini",
        "plugins/as/cpc-main-as/db/dzsq-guojia.db",
    }
)

ProgressCallback = Callable[[int, int, str], None]
ImportProgressCallback = Callable[[RuntimeImportProgress], None]
CancellationCheck = Callable[[], bool]
HealthCheck = Callable[[Path], bool | None]


class PreviewRuntimeError(RuntimeError):
    pass


class RuntimeImportCancelled(PreviewRuntimeError):
    pass


class RuntimeImportBusyError(PreviewRuntimeError):
    pass


class RuntimeInsufficientSpaceError(PreviewRuntimeError):
    pass


class RuntimeLayout:
    def __init__(self, runtime_id: str, version_root: Path) -> None:
        self.version = runtime_id
        self.version_root = version_root
        self.client_root = version_root / "CNIPAClient"
        self.app_root = self.client_root / "plugins" / "as" / "cpc-main-as"
        self.wrapper_executable = self.app_root / "bin" / "win32" / "wrapper.exe"
        self.wrapper_config = self.app_root / "bin" / "win32" / "wrapper.conf"
        self.application_config = self.app_root / "conf" / "application.yml"


def get_managed_runtime_storage_root() -> Path:
    return Path(get_machine_data_dir()) / "cpr"


def _source_kind(value: RuntimeSourceKind | str | None, source_path: Path) -> RuntimeSourceKind:
    if value is not None:
        try:
            return RuntimeSourceKind(value)
        except ValueError as exc:
            raise PreviewRuntimeError(f"不支持的运行时来源类型：{value}") from exc
    return RuntimeSourceKind.ARCHIVE if source_path.is_file() else RuntimeSourceKind.INSTALLED_CLIENT


def _normalise_archive_member(name: str) -> PurePosixPath:
    raw = str(name or "").replace("\\", "/")
    path = PurePosixPath(raw)
    if path.is_absolute() or not path.parts:
        raise PreviewRuntimeError(f"运行时 ZIP 包含不安全路径：{name!r}")
    if any(part in ("", ".", "..") or ":" in part for part in path.parts):
        raise PreviewRuntimeError(f"运行时 ZIP 包含不安全路径：{name!r}")
    return path


def _zip_member_is_link(info: zipfile.ZipInfo) -> bool:
    unix_mode = (int(info.external_attr) >> 16) & 0xFFFF
    return stat.S_IFMT(unix_mode) == stat.S_IFLNK


def _validated_zip_members(archive: zipfile.ZipFile) -> dict[str, tuple[PurePosixPath, zipfile.ZipInfo]]:
    members: dict[str, tuple[PurePosixPath, zipfile.ZipInfo]] = {}
    for info in archive.infolist():
        path = _normalise_archive_member(info.filename)
        key = path.as_posix().casefold()
        if key in members:
            raise PreviewRuntimeError(f"运行时 ZIP 包含重复成员：{path.as_posix()}")
        if _zip_member_is_link(info):
            raise PreviewRuntimeError(f"运行时 ZIP 不允许链接成员：{path.as_posix()}")
        members[key] = (path, info)
    return members


def _read_archive_manifest(archive: zipfile.ZipFile, members: dict[str, tuple[PurePosixPath, zipfile.ZipInfo]]) -> dict[str, Any]:
    entry = members.get(RUNTIME_MANIFEST_NAME.casefold())
    if entry is None or entry[1].is_dir():
        raise PreviewRuntimeError("运行时 ZIP 缺少有效清单。")
    try:
        value = json.loads(archive.read(entry[1]).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, OSError, RuntimeError) as exc:
        raise PreviewRuntimeError("运行时 ZIP 清单无法解析。") from exc
    if not isinstance(value, dict):
        raise PreviewRuntimeError("运行时 ZIP 清单格式无效。")
    version = value.get("version")
    if not isinstance(version, str) or not version.strip():
        raise PreviewRuntimeError("运行时 ZIP 清单缺少版本号。")
    return value


def _path_is_link_like(path: Path) -> bool:
    try:
        attributes = int(getattr(path.lstat(), "st_file_attributes", 0))
    except OSError:
        return False
    reparse_flag = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    return path.is_symlink() or bool(attributes & reparse_flag)


def _assert_path_inside(root: Path, path: Path) -> Path:
    resolved_root = root.resolve()
    resolved_path = path.resolve()
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise PreviewRuntimeError(f"运行时来源路径越出所选根目录：{path}") from exc
    cursor = path
    while cursor != root and cursor != cursor.parent:
        if _path_is_link_like(cursor):
            raise PreviewRuntimeError(f"运行时来源不允许链接或重解析点：{cursor}")
        cursor = cursor.parent
    return resolved_path


def _iter_source_files(client_root: Path) -> Iterator[tuple[Path, PurePosixPath]]:
    seen: set[str] = set()
    for relative_text in REQUIRED_RUNTIME_SOURCE_PATHS:
        relative = PurePosixPath(relative_text)
        source = client_root.joinpath(*relative.parts)
        _assert_path_inside(client_root, source)
        if relative_text in _SOURCE_FILE_PATHS:
            candidates: Iterable[Path] = (source,)
        else:
            candidates = sorted(path for path in source.rglob("*") if path.is_file() or _path_is_link_like(path))
        for path in candidates:
            _assert_path_inside(client_root, path)
            if not path.is_file():
                raise PreviewRuntimeError(f"运行时来源包含非普通文件：{path}")
            item_relative = PurePosixPath(path.relative_to(client_root).as_posix())
            key = item_relative.as_posix().casefold()
            if key in seen:
                raise PreviewRuntimeError(f"运行时来源产生重复目标文件：{item_relative.as_posix()}")
            seen.add(key)
            yield path, item_relative


def _directory_inspection(source_path: Path) -> RuntimeSourceInspection:
    missing: list[str] = []
    diagnostics: list[str] = []
    total_bytes = 0
    if not source_path.is_dir():
        return RuntimeSourceInspection(
            RuntimeSourceKind.INSTALLED_CLIENT,
            str(source_path),
            missing_items=("CNIPAClient 根目录",),
            diagnostics=("所选路径不是可读取的 CNIPAClient 目录。",),
        )
    try:
        for relative in REQUIRED_RUNTIME_SOURCE_PATHS:
            candidate = source_path.joinpath(*PurePosixPath(relative).parts)
            valid = candidate.is_file() if relative in _SOURCE_FILE_PATHS else candidate.is_dir()
            if not valid:
                missing.append(relative)
        for relative in REQUIRED_RUNTIME_FILES:
            if not source_path.joinpath(*PurePosixPath(relative).parts).is_file():
                missing.append(relative)
        if not missing:
            for source, _relative in _iter_source_files(source_path):
                total_bytes += source.stat().st_size
    except (OSError, PreviewRuntimeError) as exc:
        diagnostics.append(str(exc))
    missing = list(dict.fromkeys(missing))
    compatible = not missing and not diagnostics
    if compatible:
        diagnostics.append("已找到完整的 CNIPA 官方渲染运行时子集。")
    return RuntimeSourceInspection(
        RuntimeSourceKind.INSTALLED_CLIENT,
        str(source_path.resolve()),
        missing_items=tuple(missing),
        total_bytes=total_bytes,
        compatible=compatible,
        diagnostics=tuple(diagnostics),
    )


def _archive_included_file(path: PurePosixPath) -> PurePosixPath | None:
    if not path.parts or path.parts[0].casefold() != "cnipaclient":
        return None
    relative = PurePosixPath(*path.parts[1:])
    relative_text = relative.as_posix()
    for included in REQUIRED_RUNTIME_SOURCE_PATHS:
        if relative_text == included or relative_text.startswith(included.rstrip("/") + "/"):
            return relative
    return None


def _archive_inspection(source_path: Path) -> RuntimeSourceInspection:
    missing: list[str] = []
    diagnostics: list[str] = []
    total_bytes = 0
    version = ""
    try:
        with zipfile.ZipFile(source_path, "r") as archive:
            members = _validated_zip_members(archive)
            manifest = _read_archive_manifest(archive, members)
            version = str(manifest["version"]).strip()
            file_paths = {
                path.as_posix().casefold(): info
                for path, info in members.values()
                if not info.is_dir()
            }
            for relative in REQUIRED_RUNTIME_SOURCE_PATHS:
                expected = f"CNIPAClient/{relative}".casefold()
                if relative in _SOURCE_FILE_PATHS:
                    valid = expected in file_paths
                else:
                    valid = any(name.startswith(expected.rstrip("/") + "/") for name in file_paths)
                if not valid:
                    missing.append(relative)
            for relative in REQUIRED_RUNTIME_FILES:
                if f"CNIPAClient/{relative}".casefold() not in file_paths:
                    missing.append(relative)
            if not missing:
                total_bytes = sum(
                    int(info.file_size)
                    for path, info in members.values()
                    if not info.is_dir() and _archive_included_file(path) is not None
                )
    except (OSError, zipfile.BadZipFile, PreviewRuntimeError) as exc:
        diagnostics.append(str(exc))
    missing = list(dict.fromkeys(missing))
    compatible = not missing and not diagnostics
    if compatible:
        diagnostics.append("运行时 ZIP 结构和必需文件检查通过。")
    return RuntimeSourceInspection(
        RuntimeSourceKind.ARCHIVE,
        str(source_path.resolve()),
        missing_items=tuple(missing),
        total_bytes=total_bytes,
        compatible=compatible,
        diagnostics=tuple(diagnostics),
        version=version,
    )


def inspect_runtime_source(
    source_path: str | os.PathLike[str],
    source_kind: RuntimeSourceKind | str | None = None,
) -> RuntimeSourceInspection:
    path = Path(source_path).expanduser()
    kind = _source_kind(source_kind, path)
    return _archive_inspection(path) if kind is RuntimeSourceKind.ARCHIVE else _directory_inspection(path)


def _discover_uninstall_registry_paths() -> tuple[Path, ...]:
    if os.name != "nt":
        return ()
    try:
        import winreg
    except ImportError:
        return ()
    found: list[Path] = []
    bases = (
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
    )
    for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for base in bases:
            try:
                with winreg.OpenKey(root, base) as uninstall:
                    for index in range(int(winreg.QueryInfoKey(uninstall)[0])):
                        try:
                            with winreg.OpenKey(uninstall, winreg.EnumKey(uninstall, index)) as entry:
                                display_name = str(winreg.QueryValueEx(entry, "DisplayName")[0] or "")
                                if "CNIPA" not in display_name.upper() and "专利" not in display_name:
                                    continue
                                location = str(winreg.QueryValueEx(entry, "InstallLocation")[0] or "").strip()
                                if location:
                                    candidate = Path(location)
                                    found.append(candidate / "CNIPAClient" if candidate.name.casefold() != "cnipaclient" else candidate)
                        except OSError:
                            continue
            except OSError:
                continue
    return tuple(found)


def _fixed_drive_roots() -> tuple[Path, ...]:
    if os.name != "nt":
        return ()
    mask = int(ctypes.windll.kernel32.GetLogicalDrives())
    roots: list[Path] = []
    for index in range(26):
        if mask & (1 << index):
            root = f"{chr(ord('A') + index)}:\\"
            if int(ctypes.windll.kernel32.GetDriveTypeW(root)) == 3:
                roots.append(Path(root))
    return tuple(roots)


def discover_installed_client_candidates(
    *,
    remembered_path: str | os.PathLike[str] | None = None,
    registry_paths: Iterable[str | os.PathLike[str]] | None = None,
    fixed_drives: Iterable[str | os.PathLike[str]] | None = None,
) -> tuple[RuntimeSourceInspection, ...]:
    candidates: list[Path] = []
    if remembered_path:
        candidates.append(Path(remembered_path))
    candidates.extend(Path(path) for path in (registry_paths if registry_paths is not None else _discover_uninstall_registry_paths()))
    for drive in (Path(path) for path in (fixed_drives if fixed_drives is not None else _fixed_drive_roots())):
        candidates.append(drive / "Program Files" / "CNIPAClient")
        candidates.append(drive / "Program Files (x86)" / "CNIPAClient")
    results: list[RuntimeSourceInspection] = []
    seen: set[str] = set()
    for candidate in candidates:
        try:
            normalized = str(candidate.resolve()).casefold()
        except OSError:
            normalized = os.path.normcase(os.path.abspath(str(candidate))).casefold()
        if normalized in seen or not candidate.is_dir():
            continue
        seen.add(normalized)
        results.append(inspect_runtime_source(candidate, RuntimeSourceKind.INSTALLED_CLIENT))
    return tuple(results)


def _atomic_write_json(path: Path, value: dict[str, Any] | list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _check_cancelled(cancelled: CancellationCheck | None) -> None:
    if cancelled is not None and cancelled():
        raise RuntimeImportCancelled("运行时导入已取消。")


def _copy_stream(
    source,
    destination,
    *,
    copied: int,
    total: int,
    label: str,
    progress: ProgressCallback | None,
    cancelled: CancellationCheck | None,
) -> tuple[int, str]:
    digest = hashlib.sha256()
    while True:
        _check_cancelled(cancelled)
        block = source.read(1024 * 1024)
        if not block:
            break
        destination.write(block)
        digest.update(block)
        copied += len(block)
        if progress is not None:
            progress(copied, total, label)
    return copied, digest.hexdigest()


def _materialise_directory(
    inspection: RuntimeSourceInspection,
    staging: Path,
    *,
    progress: ProgressCallback | None,
    cancelled: CancellationCheck | None,
) -> list[dict[str, Any]]:
    root = Path(inspection.source_path)
    copied = 0
    entries: list[dict[str, Any]] = []
    for source, relative in _iter_source_files(root):
        target = staging / "CNIPAClient" / Path(*relative.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        with source.open("rb") as source_stream, target.open("xb") as destination:
            copied, digest = _copy_stream(
                source_stream,
                destination,
                copied=copied,
                total=inspection.total_bytes,
                label=relative.as_posix(),
                progress=progress,
                cancelled=cancelled,
            )
        entries.append({"path": f"CNIPAClient/{relative.as_posix()}", "size": source.stat().st_size, "sha256": digest})
    return entries


def _materialise_archive(
    inspection: RuntimeSourceInspection,
    staging: Path,
    *,
    progress: ProgressCallback | None,
    cancelled: CancellationCheck | None,
) -> list[dict[str, Any]]:
    copied = 0
    entries: list[dict[str, Any]] = []
    with zipfile.ZipFile(inspection.source_path, "r") as archive:
        members = _validated_zip_members(archive)
        _read_archive_manifest(archive, members)
        for path, info in sorted(members.values(), key=lambda item: item[0].as_posix().casefold()):
            if info.is_dir():
                continue
            relative = _archive_included_file(path)
            if relative is None:
                continue
            target = staging / "CNIPAClient" / Path(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info, "r") as source_stream, target.open("xb") as destination:
                copied, digest = _copy_stream(
                    source_stream,
                    destination,
                    copied=copied,
                    total=inspection.total_bytes,
                    label=relative.as_posix(),
                    progress=progress,
                    cancelled=cancelled,
                )
            entries.append({"path": f"CNIPAClient/{relative.as_posix()}", "size": int(info.file_size), "sha256": digest})
    return entries


def _content_fingerprint(entries: list[dict[str, Any]]) -> str:
    canonical = json.dumps(sorted(entries, key=lambda item: str(item["path"]).casefold()), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _emit_import_progress(
    callback: ImportProgressCallback | None,
    phase: RuntimeImportPhase,
    *,
    completed_bytes: int = 0,
    total_bytes: int = 0,
    detail: str = "",
    elapsed_seconds: float = 0.0,
    cancellable: bool = True,
) -> None:
    if callback is not None:
        callback(
            RuntimeImportProgress(
                phase=phase,
                completed_bytes=completed_bytes,
                total_bytes=total_bytes,
                detail=detail,
                elapsed_seconds=elapsed_seconds,
                cancellable=cancellable,
            )
        )


def _digest_stream(
    source,
    *,
    copied: int,
    total: int,
    label: str,
    progress: ImportProgressCallback | None,
    cancelled: CancellationCheck | None,
) -> tuple[int, str]:
    digest = hashlib.sha256()
    while True:
        _check_cancelled(cancelled)
        block = source.read(1024 * 1024)
        if not block:
            break
        digest.update(block)
        copied += len(block)
        _emit_import_progress(
            progress,
            RuntimeImportPhase.COMPARING,
            completed_bytes=copied,
            total_bytes=total,
            detail=label,
        )
    return copied, digest.hexdigest()


def _source_entries(
    inspection: RuntimeSourceInspection,
    *,
    progress: ImportProgressCallback | None,
    cancelled: CancellationCheck | None,
) -> list[dict[str, Any]]:
    copied = 0
    entries: list[dict[str, Any]] = []
    _emit_import_progress(progress, RuntimeImportPhase.COMPARING, total_bytes=inspection.total_bytes)
    if inspection.source_kind is RuntimeSourceKind.INSTALLED_CLIENT:
        root = Path(inspection.source_path)
        for source_path, relative in _iter_source_files(root):
            with source_path.open("rb") as source:
                copied, digest = _digest_stream(
                    source,
                    copied=copied,
                    total=inspection.total_bytes,
                    label=relative.as_posix(),
                    progress=progress,
                    cancelled=cancelled,
                )
            entries.append(
                {
                    "path": f"CNIPAClient/{relative.as_posix()}",
                    "size": source_path.stat().st_size,
                    "sha256": digest,
                }
            )
        return entries

    with zipfile.ZipFile(inspection.source_path, "r") as archive:
        members = _validated_zip_members(archive)
        _read_archive_manifest(archive, members)
        for path, info in sorted(members.values(), key=lambda item: item[0].as_posix().casefold()):
            if info.is_dir():
                continue
            relative = _archive_included_file(path)
            if relative is None:
                continue
            with archive.open(info, "r") as source:
                copied, digest = _digest_stream(
                    source,
                    copied=copied,
                    total=inspection.total_bytes,
                    label=relative.as_posix(),
                    progress=progress,
                    cancelled=cancelled,
                )
            entries.append(
                {
                    "path": f"CNIPAClient/{relative.as_posix()}",
                    "size": int(info.file_size),
                    "sha256": digest,
                }
            )
    return entries


def _is_machine_shared_storage(storage_root: Path) -> bool:
    try:
        storage_root.resolve().relative_to(Path(get_user_data_dir()).resolve())
    except ValueError:
        return True
    return False


@contextlib.contextmanager
def _runtime_import_lock(storage_root: Path, timeout_seconds: float) -> Iterator[None]:
    storage_root.mkdir(parents=True, exist_ok=True)
    handle = (storage_root / IMPORT_LOCK_NAME).open("a+b")
    handle.seek(0, os.SEEK_END)
    if handle.tell() == 0:
        handle.write(b"0")
        handle.flush()
    deadline = time.monotonic() + max(0.0, timeout_seconds)
    acquired = False
    try:
        while not acquired:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except OSError as exc:
                if time.monotonic() >= deadline:
                    raise RuntimeImportBusyError("另一个程序实例正在导入全量预览运行时。") from exc
                time.sleep(0.1)
        yield
    finally:
        if acquired:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        handle.close()


def _read_managed_metadata(runtime_root: Path) -> dict[str, Any]:
    try:
        value = json.loads((runtime_root / MANAGED_RUNTIME_METADATA_NAME).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PreviewRuntimeError(f"全量预览运行时管理清单损坏：{runtime_root}") from exc
    if not isinstance(value, dict):
        raise PreviewRuntimeError(f"全量预览运行时管理清单格式无效：{runtime_root}")
    return value


def _managed_info_from_root(runtime_root: Path, metadata: dict[str, Any], *, machine_shared: bool) -> ManagedRuntimeInfo:
    diagnostics: list[str] = []
    for relative in REQUIRED_RUNTIME_FILES:
        if not (runtime_root / "CNIPAClient" / Path(*PurePosixPath(relative).parts)).is_file():
            diagnostics.append(f"缺少：{relative}")
    if not (runtime_root / MANAGED_RUNTIME_FILES_NAME).is_file():
        diagnostics.append(f"缺少：{MANAGED_RUNTIME_FILES_NAME}")
    try:
        source_kind = RuntimeSourceKind(str(metadata["source_kind"]))
        runtime_id = str(metadata["runtime_id"])
        source_path = str(metadata["source_path"])
        imported_at = str(metadata["imported_at"])
    except (KeyError, ValueError) as exc:
        raise PreviewRuntimeError(f"全量预览运行时管理清单字段无效：{runtime_root}") from exc
    return ManagedRuntimeInfo(
        runtime_id=runtime_id,
        private_root=str(runtime_root),
        source_kind=source_kind,
        source_path=source_path,
        imported_at=imported_at,
        status="ready" if not diagnostics else "invalid",
        content_fingerprint=str(metadata.get("content_fingerprint", "")),
        diagnostics=tuple(diagnostics),
        cleanup_warning_path=str(metadata.get("cleanup_warning_path", "") or ""),
        machine_shared=machine_shared,
    )


def get_active_managed_runtime(storage_root: str | os.PathLike[str] | None = None) -> ManagedRuntimeInfo | None:
    root = Path(storage_root) if storage_root is not None else get_managed_runtime_storage_root()
    state_path = root / ACTIVE_RUNTIME_STATE_NAME
    if not state_path.exists():
        return None
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PreviewRuntimeError(f"全量预览活动运行时指针损坏：{state_path}") from exc
    runtime_id = state.get("runtime_id") if isinstance(state, dict) else None
    if not isinstance(runtime_id, str) or not runtime_id or Path(runtime_id).name != runtime_id:
        raise PreviewRuntimeError(f"全量预览活动运行时指针无效：{state_path}")
    runtime_root = root / runtime_id
    try:
        runtime_root.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise PreviewRuntimeError("全量预览活动运行时越出管理目录。") from exc
    if not runtime_root.is_dir():
        raise PreviewRuntimeError(f"全量预览活动运行时目录不存在：{runtime_root}")
    metadata = _read_managed_metadata(runtime_root)
    if str(metadata.get("runtime_id", "")) != runtime_id:
        raise PreviewRuntimeError("全量预览活动指针与运行时清单不一致。")
    return _managed_info_from_root(runtime_root, metadata, machine_shared=_is_machine_shared_storage(root))


def _write_loopback_server_config(config_path: Path, port: int) -> None:
    try:
        original = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PreviewRuntimeError(f"无法读取全量预览渲染器配置：{exc}") from exc
    lines = original.splitlines(keepends=True)
    result: list[str] = []
    replaced = False
    index = 0
    while index < len(lines):
        line = lines[index]
        if not replaced and line.strip() == "server:" and not line.startswith((" ", "\t")):
            result.extend(["server:\n", "  address: 127.0.0.1\n", f"  port: {port}\n"])
            replaced = True
            index += 1
            while index < len(lines):
                child = lines[index]
                if child.strip() and not child.startswith((" ", "\t", "#")):
                    break
                index += 1
            continue
        result.append(line)
        index += 1
    if not replaced:
        result = ["server:\n", "  address: 127.0.0.1\n", f"  port: {port}\n", "\n"] + result
    try:
        config_path.write_text("".join(result), encoding="utf-8")
    except OSError as exc:
        raise PreviewRuntimeError(f"无法写入全量预览渲染器回环配置：{exc}") from exc


class CnipaRuntimeManager:
    """Owns only a private managed renderer process."""

    def __init__(
        self,
        *,
        runtime_root: str | os.PathLike[str] | None = None,
        storage_root: str | os.PathLike[str] | None = None,
        request_get: Callable[..., requests.Response] = requests.get,
        process_factory: Callable[..., subprocess.Popen] = subprocess.Popen,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._runtime_root = Path(runtime_root) if runtime_root is not None else None
        self._storage_root = Path(storage_root) if storage_root is not None else get_managed_runtime_storage_root()
        self._request_get = request_get
        self._process_factory = process_factory
        self._monotonic = monotonic
        self._sleep = sleep
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        self._render_lock = threading.Lock()
        self._process: subprocess.Popen | None = None
        self._base_url = ""
        self._runtime_id = ""
        self._state = RendererState.STOPPED
        self._state_detail = ""
        self._startup_generation = 0
        self._maintenance_done = False

    def ensure_runtime(self) -> RuntimeLayout:
        if self._runtime_root is not None:
            runtime_root = self._runtime_root
            runtime_id = runtime_root.name
            for relative in REQUIRED_RUNTIME_FILES:
                if not (runtime_root / "CNIPAClient" / Path(*PurePosixPath(relative).parts)).is_file():
                    raise PreviewRuntimeError(f"全量预览运行时缺少必需文件：{relative}")
        else:
            info = get_active_managed_runtime(self._storage_root)
            if info is None:
                raise PreviewRuntimeError("尚未配置全量预览运行时。")
            if info.status != "ready":
                raise PreviewRuntimeError("全量预览运行时已损坏，请重新导入：" + "；".join(info.diagnostics))
            runtime_root = Path(info.private_root)
            runtime_id = info.runtime_id
        layout = RuntimeLayout(runtime_id, runtime_root)
        try:
            (layout.app_root / "temp").mkdir(parents=True, exist_ok=True)
            (layout.app_root / "logs").mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise PreviewRuntimeError(f"无法创建全量预览运行目录：{exc}") from exc
        return layout

    def is_running(self) -> bool:
        """Return whether this manager still owns a healthy renderer process."""
        try:
            expected_runtime_id = self.ensure_runtime().version
        except PreviewRuntimeError:
            return False
        with self._lock:
            return bool(
                self._runtime_id == expected_runtime_id
                and self._state is RendererState.RUNNING
                and self._process is not None
                and self._process.poll() is None
                and self._base_url
                and self._ping(self._base_url)
            )

    def state_info(self) -> RendererStateInfo:
        with self._lock:
            return RendererStateInfo(
                state=self._state,
                runtime_id=self._runtime_id,
                base_url=self._base_url,
                detail=self._state_detail,
            )

    def is_rendering(self) -> bool:
        return self._render_lock.locked()

    def prewarm(
        self,
        *,
        startup_wait_callback: Callable[[float], None] | None = None,
        cancelled: CancellationCheck | None = None,
    ) -> str:
        return self.ensure_running(startup_wait_callback=startup_wait_callback, cancelled=cancelled)

    def ensure_running(
        self,
        *,
        startup_wait_callback: Callable[[float], None] | None = None,
        cancelled: CancellationCheck | None = None,
    ) -> str:
        if self._runtime_root is None and not self._maintenance_done:
            self.reconcile_residue()
        while True:
            layout = self.ensure_runtime()
            with self._condition:
                if self._is_healthy_locked(layout.version):
                    return self._base_url
                if self._state is RendererState.STARTING:
                    while self._state is RendererState.STARTING:
                        _check_cancelled(cancelled)
                        self._condition.wait(0.25)
                    continue
                old_process = self._take_process_locked()
                self._state = RendererState.STARTING
                self._state_detail = "正在启动全量预览官方渲染器。"
                self._startup_generation += 1
                generation = self._startup_generation

            if old_process is not None:
                self._stop_process(old_process)
            process = None
            try:
                _check_cancelled(cancelled)
                port = self._reserve_loopback_port()
                _write_loopback_server_config(layout.application_config, port)
                process = self._start_process(layout)
                base_url = f"http://127.0.0.1:{port}"
                if not self._wait_until_ready(
                    process,
                    base_url,
                    timeout_seconds=RUNTIME_START_TIMEOUT_SECONDS,
                    startup_wait_callback=startup_wait_callback,
                    cancelled=cancelled,
                ):
                    return_code = process.poll()
                    raise PreviewRuntimeError(
                        f"全量预览渲染器启动失败（port={port}, exit={return_code if return_code is not None else 'timeout'}）。"
                    )
                with self._condition:
                    if generation != self._startup_generation:
                        raise RuntimeImportCancelled("全量预览渲染器启动已停止。")
                    self._process = process
                    self._base_url = base_url
                    self._runtime_id = layout.version
                    self._state = RendererState.RUNNING
                    self._state_detail = "本次程序会话中已就绪。"
                    self._condition.notify_all()
                    return base_url
            except Exception as exc:
                if process is not None:
                    self._stop_process(process)
                with self._condition:
                    if generation == self._startup_generation:
                        self._state = RendererState.STOPPED if isinstance(exc, RuntimeImportCancelled) else RendererState.FAILED
                        self._state_detail = str(exc)
                        self._condition.notify_all()
                raise

    def shutdown(self) -> None:
        with self._condition:
            self._startup_generation += 1
            process = self._take_process_locked()
            self._state = RendererState.STOPPING if process is not None else RendererState.STOPPED
            self._state_detail = "正在停止全量预览官方渲染器。" if process is not None else ""
        if process is not None:
            self._stop_process(process)
        with self._condition:
            self._state = RendererState.STOPPED
            self._state_detail = ""
            self._condition.notify_all()

    @contextlib.contextmanager
    def render_session(
        self,
        *,
        startup_wait_callback: Callable[[float], None] | None = None,
        cancelled: CancellationCheck | None = None,
    ) -> Iterator[str]:
        if not self._render_lock.acquire(blocking=False):
            raise RuntimeImportBusyError("全量预览正在生成 PDF，请完成或取消后再执行此操作。")
        try:
            yield self.ensure_running(startup_wait_callback=startup_wait_callback, cancelled=cancelled)
        finally:
            self._render_lock.release()

    def adopt_candidate(self, candidate: "CnipaRuntimeManager") -> None:
        if self.is_rendering():
            raise RuntimeImportBusyError("全量预览正在生成 PDF，请完成或取消后再重新导入。")
        process, base_url, runtime_id = candidate._detach_for_adoption()
        if process is None or not base_url or not runtime_id:
            raise PreviewRuntimeError("新导入的全量预览渲染器未能保持健康状态。")
        self.shutdown()
        with self._condition:
            self._process = process
            self._base_url = base_url
            self._runtime_id = runtime_id
            self._state = RendererState.RUNNING
            self._state_detail = "新导入运行时已在本次程序会话中就绪。"
            self._condition.notify_all()

    def reconcile_residue(self) -> RuntimeCleanupReport:
        with self._lock:
            if self._maintenance_done:
                return RuntimeCleanupReport()
            self._maintenance_done = True
        return reconcile_managed_runtime_residue(self._storage_root)

    def _is_healthy_locked(self, runtime_id: str) -> bool:
        return bool(
            self._runtime_id == runtime_id
            and self._state is RendererState.RUNNING
            and self._process is not None
            and self._process.poll() is None
            and self._base_url
            and self._ping(self._base_url)
        )

    def _take_process_locked(self):
        process = self._process
        self._process = None
        self._base_url = ""
        self._runtime_id = ""
        return process

    def _detach_for_adoption(self):
        with self._condition:
            base_url = self._base_url
            runtime_id = self._runtime_id
            process = self._take_process_locked()
            self._state = RendererState.STOPPED
            self._condition.notify_all()
            return process, base_url, runtime_id

    @staticmethod
    def _reserve_loopback_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])

    def _start_process(self, layout: RuntimeLayout) -> subprocess.Popen:
        if not layout.wrapper_executable.is_file() or not layout.wrapper_config.is_file():
            raise PreviewRuntimeError("全量预览运行时启动器不完整。")
        kwargs: dict[str, object] = {
            "cwd": str(layout.wrapper_executable.parent),
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        try:
            return self._process_factory([str(layout.wrapper_executable), "-c", layout.wrapper_config.name], **kwargs)
        except OSError as exc:
            raise PreviewRuntimeError(f"无法启动全量预览渲染器：{exc}") from exc

    def _wait_until_ready(
        self,
        process: subprocess.Popen,
        base_url: str,
        *,
        timeout_seconds: float = 90.0,
        startup_wait_callback: Callable[[float], None] | None = None,
        cancelled: CancellationCheck | None = None,
    ) -> bool:
        started_at = self._monotonic()
        deadline = started_at + timeout_seconds
        next_report_at = 5.0
        while self._monotonic() < deadline:
            _check_cancelled(cancelled)
            if process.poll() is not None:
                return False
            if self._ping(base_url):
                return True
            elapsed = self._monotonic() - started_at
            if startup_wait_callback is not None and elapsed >= next_report_at:
                startup_wait_callback(elapsed)
                next_report_at = (int(elapsed // 5.0) + 1) * 5.0
            self._sleep(0.25)
        return False

    def _ping(self, base_url: str) -> bool:
        try:
            response = self._request_get(
                base_url.rstrip("/") + "/v2/api-docs",
                timeout=(2.0, 2.0),
                proxies={"http": None, "https": None},
            )
            return int(response.status_code) < 400
        except requests.RequestException:
            return False

    @staticmethod
    def _stop_process(process: subprocess.Popen) -> None:
        pid = getattr(process, "pid", None)
        if os.name == "nt" and pid:
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=6,
                )
                try:
                    process.wait(timeout=6)
                except (OSError, subprocess.SubprocessError):
                    pass
                time.sleep(0.5)
                return
            except (OSError, subprocess.SubprocessError):
                pass
        try:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=4)
        except (OSError, subprocess.SubprocessError):
            pass


def _private_runtime_root_for_process(storage_root: Path, executable: str, command_line: Iterable[str]) -> Path | None:
    try:
        executable_path = Path(executable).resolve()
        executable_path.relative_to(storage_root.resolve())
    except (OSError, ValueError):
        return None
    runtime_root = next((parent for parent in executable_path.parents if parent.parent == storage_root and parent.name.startswith("runtime-")), None)
    if runtime_root is None:
        return None
    wrapper = runtime_root / "CNIPAClient" / "plugins" / "as" / "cpc-main-as" / "bin" / "win32" / "wrapper.exe"
    java = runtime_root / "CNIPAClient" / "commons" / "jre" / "win32" / "jre8" / "bin" / "java.exe"
    command_text = " ".join(str(value) for value in command_line).casefold()
    if executable_path == wrapper.resolve() and "wrapper.conf" in command_text:
        return runtime_root
    if executable_path == java.resolve() and "wrapper.jar" in command_text:
        return runtime_root
    return None


def _current_windows_user() -> str:
    try:
        import psutil

        return str(psutil.Process().username() or "")
    except (ImportError, OSError):
        return getpass.getuser()


def _same_windows_user(left: str, right: str) -> bool:
    if not left or not right:
        return False
    return left.casefold() == right.casefold()


def _stop_private_process_tree(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=6,
        )


def reconcile_managed_runtime_residue(
    storage_root: str | os.PathLike[str] | None = None,
    *,
    process_iter: Callable[..., Iterable[Any]] | None = None,
    current_user: str | None = None,
    stop_process_tree: Callable[[int], None] = _stop_private_process_tree,
    cleanup_tree: Callable[..., Any] = shutil.rmtree,
) -> RuntimeCleanupReport:
    """Remove only stale, current-user private renderer residue under ``cpr``."""

    root = Path(storage_root) if storage_root is not None else get_managed_runtime_storage_root()
    if not root.is_dir():
        return RuntimeCleanupReport()
    try:
        active = get_active_managed_runtime(root)
    except PreviewRuntimeError as exc:
        return RuntimeCleanupReport(diagnostics=(f"未清理运行时残留：{exc}",))
    active_root = Path(active.private_root).resolve() if active is not None else None
    username = current_user or _current_windows_user()
    try:
        if process_iter is None:
            import psutil

            def process_iter() -> Iterable[Any]:
                return psutil.process_iter(["pid", "exe", "cmdline", "username"])
        processes = tuple(process_iter())
    except (ImportError, OSError) as exc:
        return RuntimeCleanupReport(diagnostics=(f"无法检查全量预览残留进程：{exc}",))

    protected_roots: set[Path] = set()
    diagnostics: list[str] = []
    for process in processes:
        try:
            info = getattr(process, "info", {}) or {}
            executable = str(info.get("exe") or "")
            command_line = tuple(info.get("cmdline") or ())
            owner = str(info.get("username") or "")
            pid = int(info.get("pid") or getattr(process, "pid"))
            runtime_root = _private_runtime_root_for_process(root, executable, command_line)
        except (AttributeError, OSError, TypeError, ValueError):
            continue
        if runtime_root is None:
            continue
        if active_root is not None and runtime_root.resolve() == active_root:
            protected_roots.add(runtime_root)
            continue
        if not _same_windows_user(owner, username):
            protected_roots.add(runtime_root)
            diagnostics.append(f"未清理其他 Windows 用户正在使用的私有运行时：{runtime_root}")
            continue
        try:
            stop_process_tree(pid)
        except (OSError, subprocess.SubprocessError) as exc:
            protected_roots.add(runtime_root)
            diagnostics.append(f"无法停止私有渲染器 PID {pid}：{exc}")

    removed: list[str] = []
    residual: list[str] = []
    try:
        with _runtime_import_lock(root, 0.0):
            for candidate in root.iterdir():
                if not candidate.is_dir() or not (candidate.name.startswith("runtime-") or candidate.name.startswith(".staging-")):
                    continue
                resolved = candidate.resolve()
                if active_root is not None and resolved == active_root:
                    continue
                if resolved in protected_roots:
                    residual.append(str(candidate))
                    continue
                try:
                    cleanup_tree(candidate)
                    removed.append(str(candidate))
                except OSError as exc:
                    residual.append(str(candidate))
                    diagnostics.append(f"无法清理私有运行时残留：{candidate}（{exc}）")
    except RuntimeImportBusyError as exc:
        diagnostics.append(str(exc))
    return RuntimeCleanupReport(tuple(removed), tuple(residual), tuple(dict.fromkeys(diagnostics)))


def _probe_managed_runtime(
    runtime_root: Path,
    *,
    cancelled: CancellationCheck | None = None,
    startup_wait_callback: Callable[[float], None] | None = None,
) -> bool:
    manager = CnipaRuntimeManager(runtime_root=runtime_root)
    try:
        manager.ensure_running(startup_wait_callback=startup_wait_callback, cancelled=cancelled)
        return True
    finally:
        manager.shutdown()


def _best_effort_remove_import_tree(path: Path, cleanup_tree: Callable[..., Any]) -> None:
    for delay_seconds in (0.0, 0.25, 0.75):
        if not path.exists():
            return
        if delay_seconds:
            time.sleep(delay_seconds)
        try:
            cleanup_tree(path)
            return
        except OSError:
            continue
    try:
        cleanup_tree(path, ignore_errors=True)
    except OSError:
        pass


def import_runtime_source(
    source_path: str | os.PathLike[str],
    source_kind: RuntimeSourceKind | str | None = None,
    *,
    storage_root: str | os.PathLike[str] | None = None,
    progress: ProgressCallback | None = None,
    phase_progress: ImportProgressCallback | None = None,
    cancelled: CancellationCheck | None = None,
    health_check: HealthCheck | None = None,
    runtime_manager: CnipaRuntimeManager | None = None,
    force: bool = False,
    disk_usage: Callable[[str | os.PathLike[str]], Any] = shutil.disk_usage,
    lock_timeout_seconds: float = 0.0,
    now: Callable[[], datetime] | None = None,
    cleanup_tree: Callable[..., Any] = shutil.rmtree,
) -> RuntimeImportResult:
    """导入运行时来源并返回导入结果；供测试与运维脚本直接调用。"""
    inspection = inspect_runtime_source(source_path, source_kind)
    if not inspection.compatible:
        detail = "；".join((*inspection.missing_items, *inspection.diagnostics))
        raise PreviewRuntimeError(f"运行时来源不兼容：{detail}")
    root = Path(storage_root) if storage_root is not None else get_managed_runtime_storage_root()
    root.mkdir(parents=True, exist_ok=True)
    source_entries = _source_entries(inspection, progress=phase_progress, cancelled=cancelled)
    source_fingerprint = _content_fingerprint(source_entries)
    _check_cancelled(cancelled)
    timestamp = (now or (lambda: datetime.now(timezone.utc)))()
    imported_at = timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    staging = root / f".staging-{uuid.uuid4().hex}"
    final_root: Path | None = None
    activated = False
    candidate_manager: CnipaRuntimeManager | None = None
    with _runtime_import_lock(root, lock_timeout_seconds):
        previous = get_active_managed_runtime(root)
        if (
            not force
            and previous is not None
            and previous.status == "ready"
            and previous.content_fingerprint
            and previous.content_fingerprint == source_fingerprint
        ):
            _emit_import_progress(phase_progress, RuntimeImportPhase.DONE, detail="现有运行时内容相同，已直接复用。", cancellable=False)
            return RuntimeImportResult(
                runtime=previous,
                disposition=RuntimeImportDisposition.REUSED,
                renderer_ready=bool(runtime_manager is not None and runtime_manager.is_running()),
            )
        if runtime_manager is not None and runtime_manager.is_rendering():
            raise RuntimeImportBusyError("全量预览正在生成 PDF，请完成或取消后再重新导入。")
        required_bytes = inspection.total_bytes + IMPORT_FREE_SPACE_MARGIN_BYTES
        available_bytes = int(disk_usage(root).free)
        if available_bytes < required_bytes:
            raise RuntimeInsufficientSpaceError(
                f"全量预览运行时需要 {required_bytes} 字节可用空间，当前仅 {available_bytes} 字节。"
            )
        try:
            _check_cancelled(cancelled)
            staging.mkdir(parents=False, exist_ok=False)
            _emit_import_progress(phase_progress, RuntimeImportPhase.COPYING, total_bytes=inspection.total_bytes)

            def report_copy(copied: int, total: int, name: str) -> None:
                if progress is not None:
                    progress(copied, total, name)
                _emit_import_progress(
                    phase_progress,
                    RuntimeImportPhase.COPYING,
                    completed_bytes=copied,
                    total_bytes=total,
                    detail=name,
                )

            if inspection.source_kind is RuntimeSourceKind.ARCHIVE:
                entries = _materialise_archive(inspection, staging, progress=report_copy, cancelled=cancelled)
            else:
                entries = _materialise_directory(inspection, staging, progress=report_copy, cancelled=cancelled)
            _check_cancelled(cancelled)
            _emit_import_progress(phase_progress, RuntimeImportPhase.VERIFYING, detail="正在验证导入后的运行时结构。")
            staged_inspection = _directory_inspection(staging / "CNIPAClient")
            if not staged_inspection.compatible:
                raise PreviewRuntimeError("导入后的全量预览运行时结构验证失败。")
            entries = sorted(entries, key=lambda item: str(item["path"]).casefold())
            fingerprint = _content_fingerprint(entries)
            if fingerprint != source_fingerprint:
                raise PreviewRuntimeError("运行时来源在比对和复制期间发生变化，请重新导入。")
            _atomic_write_json(staging / MANAGED_RUNTIME_FILES_NAME, entries)
            runtime_id = f"runtime-{timestamp.strftime('%Y%m%dT%H%M%SZ')}-{fingerprint[:12]}-{uuid.uuid4().hex[:6]}"
            final_root = root / runtime_id
            os.replace(staging, final_root)
            _check_cancelled(cancelled)
            startup_started_at = time.monotonic()

            def report_startup(elapsed_seconds: float) -> None:
                _emit_import_progress(
                    phase_progress,
                    RuntimeImportPhase.STARTING,
                    detail="正在启动并健康检查全量预览官方渲染器。",
                    elapsed_seconds=elapsed_seconds,
                )

            _emit_import_progress(phase_progress, RuntimeImportPhase.STARTING, detail="正在启动并健康检查全量预览官方渲染器。")
            if health_check is not None:
                if health_check(final_root) is False:
                    raise PreviewRuntimeError("新导入的全量预览运行时未通过回环健康检查。")
                renderer_ready = False
            elif runtime_manager is not None:
                candidate_manager = CnipaRuntimeManager(runtime_root=final_root)
                candidate_manager.ensure_running(startup_wait_callback=report_startup, cancelled=cancelled)
                renderer_ready = True
            else:
                if _probe_managed_runtime(final_root, cancelled=cancelled, startup_wait_callback=report_startup) is False:
                    raise PreviewRuntimeError("新导入的全量预览运行时未通过回环健康检查。")
                renderer_ready = False
            _emit_import_progress(
                phase_progress,
                RuntimeImportPhase.STARTING,
                detail="全量预览官方渲染器已通过健康检查。",
                elapsed_seconds=time.monotonic() - startup_started_at,
            )
            _check_cancelled(cancelled)
            _emit_import_progress(
                phase_progress,
                RuntimeImportPhase.ACTIVATING,
                detail="正在启用新的全量预览运行时。",
                cancellable=False,
            )
            metadata: dict[str, Any] = {
                "runtime_id": runtime_id,
                "source_kind": inspection.source_kind.value,
                "source_path": inspection.source_path,
                "imported_at": imported_at,
                "content_fingerprint": fingerprint,
                "cleanup_warning_path": "",
            }
            _atomic_write_json(final_root / MANAGED_RUNTIME_METADATA_NAME, metadata)
            _atomic_write_json(root / ACTIVE_RUNTIME_STATE_NAME, {"runtime_id": runtime_id})
            activated = True
            if runtime_manager is not None and candidate_manager is not None:
                runtime_manager.adopt_candidate(candidate_manager)
                candidate_manager = None
            _emit_import_progress(phase_progress, RuntimeImportPhase.CLEANING, detail="正在清理旧的私有运行时。", cancellable=False)
            cleanup_warning_path = ""
            cleanup_diagnostics: list[str] = []
            removed_paths: list[str] = []
            if previous is not None and previous.runtime_id != runtime_id:
                old_root = Path(previous.private_root)
                try:
                    old_root.resolve().relative_to(root.resolve())
                    cleanup_tree(old_root)
                    removed_paths.append(str(old_root))
                except (OSError, ValueError) as exc:
                    cleanup_warning_path = str(old_root)
                    cleanup_diagnostics.append(str(exc))
                    metadata["cleanup_warning_path"] = cleanup_warning_path
                    metadata["cleanup_warning"] = str(exc)
                    _atomic_write_json(final_root / MANAGED_RUNTIME_METADATA_NAME, metadata)
            info = ManagedRuntimeInfo(
                runtime_id=runtime_id,
                private_root=str(final_root),
                source_kind=inspection.source_kind,
                source_path=inspection.source_path,
                imported_at=imported_at,
                status="ready",
                content_fingerprint=fingerprint,
                cleanup_warning_path=cleanup_warning_path,
                machine_shared=_is_machine_shared_storage(root),
            )
            cleanup = RuntimeCleanupReport(
                removed_paths=tuple(removed_paths),
                residual_paths=(cleanup_warning_path,) if cleanup_warning_path else (),
                diagnostics=tuple(cleanup_diagnostics),
            )
            _emit_import_progress(phase_progress, RuntimeImportPhase.DONE, detail="导入并验证完成。", cancellable=False)
            return RuntimeImportResult(
                runtime=info,
                disposition=RuntimeImportDisposition.IMPORTED,
                cleanup=cleanup,
                renderer_ready=renderer_ready,
            )
        finally:
            if candidate_manager is not None:
                candidate_manager.shutdown()
            if staging.exists():
                _best_effort_remove_import_tree(staging, cleanup_tree)
            if final_root is not None and final_root.exists() and not activated:
                _best_effort_remove_import_tree(final_root, cleanup_tree)


_default_manager: InstalledLibraryManager | None = None
_default_manager_lock = threading.Lock()


def get_default_runtime_manager() -> InstalledLibraryManager:
    global _default_manager
    with _default_manager_lock:
        if _default_manager is None:
            from .library_process import InstalledLibraryManager

            _default_manager = InstalledLibraryManager()
        return _default_manager


def shutdown_default_runtime_manager() -> None:
    with _default_manager_lock:
        manager = _default_manager
    if manager is not None:
        manager.shutdown()


atexit.register(shutdown_default_runtime_manager)


__all__ = [
    "ACTIVE_RUNTIME_STATE_NAME",
    "CnipaRuntimeManager",
    "IMPORT_FREE_SPACE_MARGIN_BYTES",
    "MANAGED_RUNTIME_FILES_NAME",
    "MANAGED_RUNTIME_METADATA_NAME",
    "PreviewRuntimeError",
    "REQUIRED_RUNTIME_FILES",
    "REQUIRED_RUNTIME_SOURCE_PATHS",
    "RUNTIME_MANIFEST_NAME",
    "RuntimeImportBusyError",
    "RuntimeImportCancelled",
    "RuntimeInsufficientSpaceError",
    "RuntimeLayout",
    "discover_installed_client_candidates",
    "get_active_managed_runtime",
    "get_default_runtime_manager",
    "get_managed_runtime_storage_root",
    "import_runtime_source",
    "inspect_runtime_source",
    "reconcile_managed_runtime_residue",
    "shutdown_default_runtime_manager",
]
