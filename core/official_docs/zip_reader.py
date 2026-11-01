from __future__ import annotations

import io
import os
import tempfile
import zipfile
from dataclasses import dataclass
from typing import BinaryIO

from core.archive_safety import ArchiveBudget


def _has_box_drawing(text: str) -> bool:
    for ch in text or "":
        cp = ord(ch)
        if 0x2500 <= cp <= 0x257F:
            return True
    return False


def _count_cjk(text: str) -> int:
    n = 0
    for ch in text or "":
        cp = ord(ch)
        if 0x4E00 <= cp <= 0x9FFF:
            n += 1
    return n


def decode_zip_name(name: str, info: zipfile.ZipInfo | None = None) -> str:
    """Best-effort decode for CP437-misdecoded filenames in CNIPA zip files.

    zipfile decodes entry names using CP437 when UTF-8 flag is not set. Many CN zips store GBK/GB18030
    bytes without the UTF-8 bit, resulting in garbled box-drawing characters.
    """

    raw = str(name or "")
    if not raw:
        return ""

    try:
        if info is not None and bool(int(getattr(info, "flag_bits", 0)) & 0x800):
            return raw
    except Exception:
        pass

    # If the current name already looks fine (contains CJK and no box drawing), keep it.
    if _count_cjk(raw) > 0 and not _has_box_drawing(raw):
        return raw

    try:
        candidate = raw.encode("cp437").decode("gb18030")
    except Exception:
        return raw

    if not candidate:
        return raw

    # Prefer decoded candidate when it reduces garbling and/or introduces CJK.
    if _has_box_drawing(raw) and not _has_box_drawing(candidate):
        return candidate
    if _count_cjk(candidate) > _count_cjk(raw):
        return candidate
    return raw


def _is_file_info(info: zipfile.ZipInfo) -> bool:
    try:
        if getattr(info, "is_dir", lambda: False)():
            return False
    except Exception:
        pass
    try:
        name = str(getattr(info, "filename", "") or "")
    except Exception:
        name = ""
    if not name:
        return False
    if name.endswith("/") or name.endswith("\\"):
        return False
    return True


@dataclass
class ZipEntry:
    raw_name: str
    display_name: str
    info: zipfile.ZipInfo


_IMAGE_EXTENSIONS = {".tif", ".tiff", ".jpg", ".jpeg", ".png", ".bmp", ".webp"}


class NoticeZipReader:
    """Open an official notice ZIP, transparently handling the common "outer zip -> single inner zip" layout."""

    def __init__(self, zip_path: str) -> None:
        self.zip_path = str(zip_path or "")
        self._outer: zipfile.ZipFile | None = None
        self._inner: zipfile.ZipFile | None = None
        self._inner_buf: BinaryIO | None = None
        self._active: zipfile.ZipFile | None = None
        self._budget = ArchiveBudget()

    def __enter__(self) -> "NoticeZipReader":
        if not self.zip_path or not os.path.isfile(self.zip_path):
            raise FileNotFoundError(self.zip_path)

        self._budget = ArchiveBudget()
        try:
            outer = zipfile.ZipFile(self.zip_path, "r")
            self._outer = outer
            file_infos = [i for i in self._budget.validate(outer) if _is_file_info(i)]
            active: zipfile.ZipFile = outer
            if len(file_infos) == 1 and file_infos[0].filename.lower().endswith(".zip"):
                buf = tempfile.TemporaryFile()
                self._inner_buf = buf
                self._budget.copy(outer, file_infos[0], buf)
                buf.seek(0)
                inner = zipfile.ZipFile(buf, "r")
                self._inner = inner
                self._budget.validate(inner)
                active = inner
            self._active = active
            return self
        except Exception:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if self._inner is not None:
                self._inner.close()
        except Exception:
            pass
        try:
            if self._outer is not None:
                self._outer.close()
        except Exception:
            pass
        try:
            if self._inner_buf is not None:
                self._inner_buf.close()
        except Exception:
            pass

        self._inner = None
        self._outer = None
        self._inner_buf = None
        self._active = None

    @property
    def active_zip(self) -> zipfile.ZipFile:
        if self._active is None:
            raise RuntimeError("zip not opened")
        return self._active

    def iter_entries(self) -> list[ZipEntry]:
        zf = self.active_zip
        out: list[ZipEntry] = []
        for info in zf.infolist():
            if not _is_file_info(info):
                continue
            raw = ""
            try:
                raw = str(info.filename or "")
            except Exception:
                raw = ""
            if not raw:
                continue
            display = decode_zip_name(raw, info)
            out.append(ZipEntry(raw_name=raw, display_name=display, info=info))
        return out

    def read_bytes(self, raw_name: str) -> bytes:
        output = io.BytesIO()
        self._budget.copy(self.active_zip, self.active_zip.getinfo(raw_name), output)
        return output.getvalue()

    def find_list_xml(self) -> ZipEntry | None:
        cands = []
        for e in self.iter_entries():
            try:
                if os.path.basename(e.raw_name.replace("\\", "/")).lower() == "list.xml":
                    cands.append(e)
            except Exception:
                continue
        if not cands:
            return None
        # Prefer root-level list.xml
        cands.sort(key=lambda x: len(x.raw_name.replace("\\", "/").split("/")))
        return cands[0]

    def iter_pdfs(self) -> list[ZipEntry]:
        pdfs: list[ZipEntry] = []
        for e in self.iter_entries():
            try:
                if e.raw_name.lower().endswith(".pdf"):
                    pdfs.append(e)
            except Exception:
                continue
        return pdfs

    def iter_images(self) -> list[ZipEntry]:
        images: list[ZipEntry] = []
        for e in self.iter_entries():
            try:
                ext = os.path.splitext(str(e.raw_name or ""))[1].lower()
            except Exception:
                ext = ""
            if ext in _IMAGE_EXTENSIONS:
                images.append(e)
        return images


__all__ = ["NoticeZipReader", "ZipEntry", "decode_zip_name"]
