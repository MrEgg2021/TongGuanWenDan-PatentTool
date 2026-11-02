"""Shared ZIP path and uncompressed-byte limits for imported archives."""

from __future__ import annotations

import ntpath
import stat
import zipfile
from pathlib import PurePosixPath
from typing import BinaryIO


MAX_MEMBERS = 10_000
MAX_MEMBER_BYTES = 256 * 1024 * 1024
MAX_TOTAL_BYTES = 2 * 1024 * 1024 * 1024
_WINDOWS_DEVICES = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"} | {
    f"{prefix}{number}" for prefix in ("COM", "LPT") for number in (*range(1, 10), "¹", "²", "³")
}


class ArchiveSafetyError(ValueError):
    pass


class ArchivePathError(ArchiveSafetyError):
    pass


def safe_member_path(name: str) -> PurePosixPath:
    raw = str(name or "").replace("\\", "/")
    parts = raw.rstrip("/").split("/")
    if not raw or raw.startswith("/") or ntpath.splitdrive(raw)[0] or any(
        part in ("", ".", "..")
        or part != part.rstrip(" .")
        or part.split(".", 1)[0].rstrip(" ").upper() in _WINDOWS_DEVICES
        or ":" in part
        or "\x00" in part
        for part in parts
    ):
        raise ArchivePathError(f"ZIP 成员路径不安全：{name!r}")
    return PurePosixPath(*parts)


class ArchiveBudget:
    def __init__(
        self,
        *,
        max_members: int = MAX_MEMBERS,
        max_member_bytes: int = MAX_MEMBER_BYTES,
        max_total_bytes: int = MAX_TOTAL_BYTES,
    ) -> None:
        self.max_members = max_members
        self.max_member_bytes = max_member_bytes
        self.max_total_bytes = max_total_bytes
        self._members = 0
        self._declared = 0
        self._read = 0

    def validate(self, archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
        """Reject every unsafe member before the caller writes any extracted file.

        目录条目（名称以 / 结尾，含部分官方导出包写出的根目录 "/"）不承载数据、也不会被解包
        写出，因此不参与路径校验；否则一个目录标记就会让整包被拒绝。文件条目仍逐一校验。
        """
        infos = archive.infolist()
        count = self._members + len(infos)
        declared = self._declared
        if count > self.max_members:
            raise ArchiveSafetyError("ZIP 成员数量超出限制")
        seen: set[str] = set()
        for info in infos:
            if info.is_dir():
                continue
            name = safe_member_path(info.filename).as_posix()
            if name.casefold() in seen:
                raise ArchiveSafetyError(f"ZIP 包含重复成员：{name!r}")
            seen.add(name.casefold())
            mode = (info.external_attr >> 16) & 0xFFFF
            if stat.S_IFMT(mode) == stat.S_IFLNK or (info.create_system == 0 and mode & 0x400):
                raise ArchiveSafetyError(f"ZIP 不允许链接成员：{info.filename!r}")
            if info.file_size < 0 or info.file_size > self.max_member_bytes:
                raise ArchiveSafetyError(f"ZIP 成员解压大小超出限制：{info.filename!r}")
            declared += info.file_size
            if declared > self.max_total_bytes:
                raise ArchiveSafetyError("ZIP 总解压大小超出限制")
        self._members = count
        self._declared = declared
        return infos

    def copy(self, archive: zipfile.ZipFile, info: zipfile.ZipInfo, output: BinaryIO) -> int:
        """Copy with actual-byte accounting, including corrupt or false ZIP headers."""
        size = 0
        with archive.open(info, "r") as source:
            while chunk := source.read(1024 * 1024):
                size += len(chunk)
                self._read += len(chunk)
                if size > self.max_member_bytes or self._read > self.max_total_bytes:
                    raise ArchiveSafetyError(f"ZIP 实际解压大小超出限制：{info.filename!r}")
                output.write(chunk)
        return size
