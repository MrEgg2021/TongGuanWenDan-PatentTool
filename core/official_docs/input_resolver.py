from __future__ import annotations

import hashlib
import os
import tempfile
import zipfile
from dataclasses import dataclass, field
from typing import Iterable

from core.config import sanitize_filename
from core.archive_safety import ArchiveBudget

from .zip_reader import _is_file_info, decode_zip_name


_MERGEABLE_IMAGE_EXTENSIONS = {".tif", ".tiff", ".jpg", ".jpeg", ".png", ".bmp", ".webp"}


@dataclass(frozen=True)
class NoticeInputLeaf:
    id: str
    zip_path: str
    display_name: str
    source_path: str
    bundle_key: str = ""
    bundle_name: str = ""
    inner_zip_name: str = ""
    source_label: str = ""


@dataclass(frozen=True)
class NoticeInputBundle:
    key: str
    display_name: str
    source_path: str
    children: list[NoticeInputLeaf] = field(default_factory=list)


@dataclass(frozen=True)
class NoticeInputIgnored:
    source_path: str
    display_name: str
    reason: str


@dataclass(frozen=True)
class NoticeInputResolveResult:
    nodes: list[NoticeInputBundle | NoticeInputLeaf] = field(default_factory=list)
    leaves: list[NoticeInputLeaf] = field(default_factory=list)
    ignored: list[NoticeInputIgnored] = field(default_factory=list)


def normalize_notice_input_paths(paths: Iterable[str] | None) -> list[str]:
    out: list[str] = []
    for raw in paths or []:
        p = str(raw or "").strip()
        if not p:
            continue
        if os.path.isdir(p):
            for dirpath, _dirnames, filenames in os.walk(p):
                for fn in filenames:
                    if str(fn or "").lower().endswith(".zip"):
                        out.append(os.path.join(dirpath, fn))
            continue
        if os.path.isfile(p) and p.lower().endswith(".zip"):
            out.append(p)

    seen: set[str] = set()
    uniq: list[str] = []
    for p in out:
        try:
            ap = os.path.abspath(p)
        except Exception:
            ap = str(p or "")
        if not ap:
            continue
        key = ap.lower()
        if key in seen:
            continue
        seen.add(key)
        uniq.append(ap)
    uniq.sort()
    return uniq


def _hash_id(*parts: str) -> str:
    src = "|".join([str(p or "") for p in parts])
    return hashlib.sha1(src.encode("utf-8", errors="ignore")).hexdigest()[:16]


def _leaf_name_from_path(path: str) -> str:
    base = ""
    try:
        base = os.path.splitext(os.path.basename(path))[0]
    except Exception:
        base = str(path or "")
    return sanitize_filename(base) or "notice"


def _source_label(source_path: str, inner_name: str = "") -> str:
    outer = ""
    try:
        outer = os.path.basename(str(source_path or "").replace("\\", "/"))
    except Exception:
        outer = str(source_path or "")
    inner = ""
    try:
        inner = os.path.basename(str(inner_name or "").replace("\\", "/"))
    except Exception:
        inner = str(inner_name or "")
    if outer and inner:
        return f"{outer} > {inner}"
    return outer


def _scan_outer_entries(path: str, budget: ArchiveBudget) -> tuple[bool, list[tuple[str, str]], list[tuple[str, str]], list[tuple[str, str]]]:
    has_list_xml = False
    inner_infos: list[tuple[str, str]] = []
    loose_pdfs: list[tuple[str, str]] = []
    loose_images: list[tuple[str, str]] = []
    with zipfile.ZipFile(path, "r") as zf:
        for info in budget.validate(zf):
            if info.is_dir():
                continue
            raw_name = info.filename
            display = decode_zip_name(raw_name, info)
            lowered = raw_name.lower()
            base_lower = os.path.basename(raw_name.replace("\\", "/")).lower()
            if base_lower == "list.xml":
                has_list_xml = True
                continue
            if lowered.endswith(".zip"):
                inner_infos.append((raw_name, display))
                continue
            ext = os.path.splitext(lowered)[1]
            if ext == ".pdf":
                loose_pdfs.append((raw_name, display))
                continue
            if ext in _MERGEABLE_IMAGE_EXTENSIONS:
                loose_images.append((raw_name, display))
    return has_list_xml, inner_infos, loose_pdfs, loose_images


def _extract_inner_zip(
    *,
    outer_zip_path: str,
    inner_raw_name: str,
    leaf_id: str,
    temp_root_dir: str,
    budget: ArchiveBudget,
) -> str:
    os.makedirs(temp_root_dir, exist_ok=True)
    out_path = os.path.join(temp_root_dir, f"{leaf_id}.zip")
    fd, staging = tempfile.mkstemp(prefix=f".{leaf_id}-", suffix=".tmp", dir=temp_root_dir)
    try:
        with os.fdopen(fd, "wb") as output, zipfile.ZipFile(outer_zip_path, "r") as zf:
            budget.copy(zf, zf.getinfo(inner_raw_name), output)
        with zipfile.ZipFile(staging, "r") as inner_zf:
            files = [info for info in budget.validate(inner_zf) if _is_file_info(info)]
            if len(files) == 1 and files[0].filename.lower().endswith(".zip"):
                with tempfile.TemporaryFile() as nested_file:
                    budget.copy(inner_zf, files[0], nested_file)
                    nested_file.seek(0)
                    with zipfile.ZipFile(nested_file, "r") as nested_zf:
                        budget.validate(nested_zf)
        os.replace(staging, out_path)
        return out_path
    finally:
        if os.path.exists(staging):
            os.unlink(staging)


def _extract_single_entry_as_zip(
    *,
    outer_zip_path: str,
    entry_raw_name: str,
    entry_display_name: str,
    leaf_id: str,
    temp_root_dir: str,
    budget: ArchiveBudget,
) -> str:
    os.makedirs(temp_root_dir, exist_ok=True)

    out_path = os.path.join(temp_root_dir, f"{leaf_id}.zip")
    arc_name = ""
    try:
        arc_name = os.path.basename(str(entry_display_name or entry_raw_name).replace("\\", "/"))
    except Exception:
        arc_name = ""
    if not arc_name:
        arc_name = os.path.basename(str(entry_raw_name or "").replace("\\", "/")) or "notice.pdf"
    fd, staging = tempfile.mkstemp(prefix=f".{leaf_id}-", suffix=".tmp", dir=temp_root_dir)
    try:
        with os.fdopen(fd, "wb") as output, zipfile.ZipFile(outer_zip_path, "r") as outer_zf:
            with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as out_zf:
                with out_zf.open(arc_name, "w") as member:
                    budget.copy(outer_zf, outer_zf.getinfo(entry_raw_name), member)
        os.replace(staging, out_path)
        return out_path
    finally:
        if os.path.exists(staging):
            os.unlink(staging)


def _normalize_no_list_multi_pdf_mode(mode: str) -> str:
    value = str(mode or "").strip().lower()
    if value == "merge_all":
        return "merge_all"
    return "split_each_pdf"


def resolve_notice_inputs(
    input_paths: Iterable[str] | None,
    *,
    temp_root_dir: str,
    no_list_multi_pdf_mode: str = "split_each_pdf",
) -> NoticeInputResolveResult:
    nodes: list[NoticeInputBundle | NoticeInputLeaf] = []
    leaves: list[NoticeInputLeaf] = []
    ignored: list[NoticeInputIgnored] = []
    mode = _normalize_no_list_multi_pdf_mode(no_list_multi_pdf_mode)

    for zip_path in normalize_notice_input_paths(input_paths):
        budget = ArchiveBudget()
        try:
            has_list_xml, inner_infos, loose_pdfs, loose_images = _scan_outer_entries(zip_path, budget)
        except (OSError, zipfile.BadZipFile, ValueError) as exc:
            ignored.append(NoticeInputIgnored(
                source_path=zip_path,
                display_name=os.path.basename(zip_path) or _leaf_name_from_path(zip_path),
                reason=f"ZIP 无法导入：{exc}",
            ))
            continue
        has_mixed_child_and_loose = (not has_list_xml) and bool(inner_infos) and bool(loose_pdfs or loose_images)
        if has_mixed_child_and_loose:
            ignored.append(
                NoticeInputIgnored(
                    source_path=zip_path,
                    display_name=os.path.basename(zip_path) or _leaf_name_from_path(zip_path),
                    reason="检测到子 ZIP 与平铺 PDF 混合，需先拆分后再导入",
                )
            )
            continue

        if (not has_list_xml) and len(inner_infos) >= 2:
            bundle_key = f"bundle:{_hash_id(zip_path)}"
            bundle_name = _leaf_name_from_path(zip_path)
            children: list[NoticeInputLeaf] = []
            for inner_raw_name, inner_display in inner_infos:
                display_base = ""
                try:
                    display_base = os.path.splitext(os.path.basename(inner_display.replace("\\", "/")))[0]
                except Exception:
                    display_base = ""
                if not display_base:
                    display_base = _leaf_name_from_path(inner_raw_name)
                leaf_id = f"leaf:{_hash_id(zip_path, inner_raw_name)}"
                try:
                    leaf_zip_path = _extract_inner_zip(
                        outer_zip_path=zip_path,
                        inner_raw_name=inner_raw_name,
                        leaf_id=leaf_id.replace("leaf:", ""),
                        temp_root_dir=temp_root_dir,
                        budget=budget,
                    )
                except (OSError, zipfile.BadZipFile, ValueError, RuntimeError) as exc:
                    ignored.append(NoticeInputIgnored(
                        source_path=zip_path,
                        display_name=inner_display,
                        reason=f"子 ZIP 无法导入：{exc}",
                    ))
                    continue
                leaf = NoticeInputLeaf(
                    id=leaf_id,
                    zip_path=leaf_zip_path,
                    display_name=display_base,
                    source_path=zip_path,
                    bundle_key=bundle_key,
                    bundle_name=bundle_name,
                    inner_zip_name=inner_display,
                    source_label=_source_label(zip_path, inner_display),
                )
                children.append(leaf)
                leaves.append(leaf)
            if children:
                nodes.append(
                    NoticeInputBundle(
                        key=bundle_key,
                        display_name=bundle_name,
                        source_path=zip_path,
                        children=children,
                    )
                )
            continue

        if (not has_list_xml) and len(loose_pdfs) >= 2 and (not loose_images) and mode == "split_each_pdf":
            bundle_key = f"bundle:{_hash_id(zip_path, 'flat-pdf')}"
            bundle_name = _leaf_name_from_path(zip_path)
            children: list[NoticeInputLeaf] = []
            for entry_raw_name, entry_display in loose_pdfs:
                leaf_id = f"leaf:{_hash_id(zip_path, entry_raw_name)}"
                try:
                    leaf_zip_path = _extract_single_entry_as_zip(
                        outer_zip_path=zip_path,
                        entry_raw_name=entry_raw_name,
                        entry_display_name=entry_display,
                        leaf_id=leaf_id.replace("leaf:", ""),
                        temp_root_dir=temp_root_dir,
                        budget=budget,
                    )
                except (OSError, zipfile.BadZipFile, ValueError, RuntimeError) as exc:
                    ignored.append(NoticeInputIgnored(
                        source_path=zip_path,
                        display_name=entry_display,
                        reason=f"PDF 无法导入：{exc}",
                    ))
                    continue
                leaf = NoticeInputLeaf(
                    id=leaf_id,
                    zip_path=leaf_zip_path,
                    display_name=_leaf_name_from_path(entry_display),
                    source_path=zip_path,
                    bundle_key=bundle_key,
                    bundle_name=bundle_name,
                    inner_zip_name=os.path.basename(entry_display.replace("\\", "/")) or entry_display,
                    source_label=_source_label(zip_path, entry_display),
                )
                children.append(leaf)
                leaves.append(leaf)
            if children:
                nodes.append(
                    NoticeInputBundle(
                        key=bundle_key,
                        display_name=bundle_name,
                        source_path=zip_path,
                        children=children,
                    )
                )
            continue

        leaf_id = f"leaf:{_hash_id(zip_path)}"
        leaf = NoticeInputLeaf(
            id=leaf_id,
            zip_path=zip_path,
            display_name=_leaf_name_from_path(zip_path),
            source_path=zip_path,
        )
        nodes.append(leaf)
        leaves.append(leaf)

    return NoticeInputResolveResult(nodes=nodes, leaves=leaves, ignored=ignored)


__all__ = [
    "NoticeInputBundle",
    "NoticeInputIgnored",
    "NoticeInputLeaf",
    "NoticeInputResolveResult",
    "normalize_notice_input_paths",
    "resolve_notice_inputs",
]
