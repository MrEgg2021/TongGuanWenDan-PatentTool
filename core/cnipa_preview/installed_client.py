from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.app_preferences import get_cnipa_runtime_source_v1, set_cnipa_runtime_source_v1

from .runtime import PreviewRuntimeError, discover_installed_client_candidates


CLIENT_MISSING = "没有检测到已安装的专利业务办理系统客户端（CNIPA），暂无法使用全量预览。请先安装客户端，再点击重新检测；已安装的用户也可以手动选择 CNIPAClient 目录。"


@dataclass(frozen=True)
class InstalledClient:
    root: Path
    java: Path
    libraries: tuple[Path, ...]
    watched: tuple[Path, ...]
    signature: tuple[tuple[int, int], ...]


def component_signature(paths: tuple[Path, ...]) -> tuple[tuple[int, int], ...]:
    return tuple((s.st_size, s.st_mtime_ns) for s in (path.stat() for path in paths))


def inspect_installed_client(path: str | Path) -> InstalledClient:
    root = Path(path).resolve()
    main = root / "plugins/as/cpc-main-as"
    config = main / "bin/win32/wrapper.conf"
    java = root / "commons/jre/win32/jre8/bin/java.exe"
    try:
        entries = []
        for line in config.read_text(encoding="utf-8").splitlines():
            if line.startswith("wrapper.java.classpath."):
                key, value = line.split("=", 1)
                entries.append((int(key.rsplit(".", 1)[1]), value))
        libraries = []
        for _, value in sorted(entries):
            value = value.replace("%APP_HOME%", str(main)).replace("%COMMONS_HOME%", str(root / "commons"))
            if "%" in value:
                raise PreviewRuntimeError("客户端组件路径含未识别变量，请重新检测或选择客户端目录。")
            for entry in value.split(";"):
                library = Path(entry).resolve()
                library.relative_to(root)
                # Never load the official logging/application configuration.
                if library.suffix.lower() == ".jar":
                    if not library.is_file():
                        raise PreviewRuntimeError("客户端预览组件缺失，请修复客户端后重新检测。")
                    libraries.append(library)
        if not libraries or not any(p.name.startswith("groovy-all-") for p in libraries):
            raise PreviewRuntimeError("客户端预览组件不完整，请修复客户端后重新检测。")
        if not java.is_file():
            raise PreviewRuntimeError("客户端缺少 Java 运行环境，请修复客户端后重新检测。")
        watched = (java, config, *libraries)
        return InstalledClient(root, java, tuple(libraries), watched, component_signature(watched))
    except (OSError, ValueError) as exc:
        raise PreviewRuntimeError(f"{CLIENT_MISSING}\n目录：{root}\n原因：{exc}") from exc


def remembered_client_path() -> str | None:
    source = get_cnipa_runtime_source_v1()
    if source and source["source_kind"] == "installed_client":
        return source["source_path"]
    return None


def remember_client(client: InstalledClient) -> None:
    set_cnipa_runtime_source_v1("installed_client", str(client.root))


def detect_client() -> InstalledClient:
    for candidate in discover_installed_client_candidates():
        try:
            return inspect_installed_client(candidate.source_path)
        except PreviewRuntimeError:
            continue
    raise PreviewRuntimeError(CLIENT_MISSING)


def java_classpath_manifest(client: InstalledClient) -> bytes:
    # Manifest continuation lines avoid Windows' command-line length limit.
    value = "Class-Path: " + " ".join(path.as_uri() for path in client.libraries)
    chunks = [value[:70]]
    value = value[70:]
    while value:
        chunks.append(" " + value[:69])
        value = value[69:]
    return ("Manifest-Version: 1.0\r\n" + "\r\n".join(chunks) + "\r\n\r\n").encode("ascii")
