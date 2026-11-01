from __future__ import annotations

import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import BinaryIO

from core.archive_safety import ArchiveBudget
from core.conversion import run_conversion

from .manifest import count_claims, generate_case_id
from .models import SlotResult
from .xml_normalize import normalize_claims_for_response_correction, normalize_opinion_body_xml

_SLOT_TO_SECTION = {
    "100001": "claims",
    "100002": "description",
    "100003": "drawings",
    "100004": "abstract",
    "100012_body": "abstract",
}

_SLOT_TO_CONVERSION_FOLDER = {
    "100001": "100001",
    "100002": "100002",
    "100003": "100003",
    "100004": "100004",
    "100012_body": "100004",
}

_SUPPORTED_PACKAGE_SLOTS = frozenset({"100001", "100002", "100003", "100004"})


def _file_infos(zf: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    items: list[zipfile.ZipInfo] = []
    for info in zf.infolist():
        try:
            is_dir = bool(info.is_dir())
        except Exception:
            raw_name = str(getattr(info, "filename", "") or "")
            is_dir = raw_name.endswith("/") or raw_name.endswith("\\")
        if not is_dir:
            items.append(info)
    return items


def _normalized_zip_name(info: zipfile.ZipInfo) -> str:
    return str(getattr(info, "filename", "") or "").replace("\\", "/").strip("/")


def _slot_xml_match(raw_name: str) -> tuple[str, str] | None:
    parts = [part for part in str(raw_name or "").replace("\\", "/").split("/") if part]
    if len(parts) < 2:
        return None
    if len(parts) == 2:
        slot_code, filename = parts
        folder_parts: list[str] = [slot_code]
    elif len(parts) == 3:
        _case_id, slot_code, filename = parts
        folder_parts = parts[:2]
    else:
        return None
    if slot_code not in _SUPPORTED_PACKAGE_SLOTS:
        return None
    if filename != f"{slot_code}.xml":
        return None
    return slot_code, "/".join(folder_parts)


def _open_preconverted_package(zip_path: str) -> tuple[zipfile.ZipFile, BinaryIO | None, zipfile.ZipFile | None, ArchiveBudget]:
    outer = zipfile.ZipFile(zip_path, "r")
    inner_buf: BinaryIO | None = None
    inner_zip: zipfile.ZipFile | None = None
    budget = ArchiveBudget()
    try:
        budget.validate(outer)
        direct_matches = [_slot_xml_match(_normalized_zip_name(info)) for info in _file_infos(outer)]
        if any(match is not None for match in direct_matches):
            return outer, None, None, budget

        infos = _file_infos(outer)
        zip_infos = [info for info in infos if _normalized_zip_name(info).lower().endswith(".zip")]
        non_zip_infos = [info for info in infos if not _normalized_zip_name(info).lower().endswith(".zip")]
        if len(zip_infos) == 1 and not non_zip_infos:
            inner_buf = tempfile.TemporaryFile()
            budget.copy(outer, zip_infos[0], inner_buf)
            inner_buf.seek(0)
            inner_zip = zipfile.ZipFile(inner_buf, "r")
            budget.validate(inner_zip)
            return inner_zip, inner_buf, outer, budget

        return outer, None, None, budget
    except Exception:
        if inner_zip is not None:
            inner_zip.close()
        if inner_buf is not None:
            inner_buf.close()
        outer.close()
        raise


def _copy_preconverted(input_path: str, output_dir: str, filename: str, slot_code: str) -> SlotResult:
    src = Path(input_path)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    dst = out / filename
    shutil.copy2(str(src), str(dst))
    _normalize_slot_xml(dst, slot_code)
    return SlotResult(slot_code=slot_code, xml_path=str(dst), pages=1, counts=0)


def extract_preconverted_slot_package(input_zip: str, expected_slot_code: str, output_dir: str) -> SlotResult:
    if expected_slot_code not in _SUPPORTED_PACKAGE_SLOTS:
        raise ValueError(f"不支持的预转好文书槽位：{expected_slot_code}")

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    active_zip: zipfile.ZipFile | None = None
    inner_buf: BinaryIO | None = None
    outer_zip: zipfile.ZipFile | None = None
    try:
        active_zip, inner_buf, outer_zip, budget = _open_preconverted_package(input_zip)
        matches: list[tuple[str, str, zipfile.ZipInfo]] = []
        slot_codes: set[str] = set()
        for info in _file_infos(active_zip):
            normalized = _normalized_zip_name(info)
            matched = _slot_xml_match(normalized)
            if matched is None:
                continue
            slot_code, folder_prefix = matched
            slot_codes.add(slot_code)
            matches.append((slot_code, folder_prefix, info))

        if len(slot_codes) > 1:
            raise ValueError("案卷包结构不明确：检测到多个文书槽位")
        if not slot_codes:
            raise ValueError("案卷包缺少目标 XML")
        found_slot = next(iter(slot_codes))
        if found_slot != expected_slot_code:
            raise ValueError("所选文件类型与案卷包内容不一致")

        _slot_code, folder_prefix, _info = matches[0]
        prefix = folder_prefix.strip("/") + "/"
        selected: list[tuple[zipfile.ZipInfo, str, Path]] = []
        root = out.resolve()
        for info in _file_infos(active_zip):
            normalized = _normalized_zip_name(info)
            if not normalized.startswith(prefix):
                continue
            rel_name = normalized[len(prefix):].strip("/")
            if not rel_name:
                continue
            target = out / rel_name
            try:
                target.resolve().relative_to(root)
            except ValueError as exc:
                raise ValueError(f"ZIP 成员路径越出槽位目录：{info.filename!r}") from exc
            selected.append((info, rel_name, target))
        copied_xml = out / f"{expected_slot_code}.xml"
        with tempfile.TemporaryDirectory(prefix=".slot_extract_", dir=out) as staging_dir:
            staging_root = Path(staging_dir)
            for info, rel_name, _target in selected:
                staged = staging_root / rel_name
                staged.parent.mkdir(parents=True, exist_ok=True)
                with staged.open("wb") as dst:
                    budget.copy(active_zip, info, dst)
            staged_xml = staging_root / f"{expected_slot_code}.xml"
            if not staged_xml.is_file():
                raise ValueError("案卷包缺少目标 XML")
            _normalize_slot_xml(staged_xml, expected_slot_code)
            counts = count_claims(str(staged_xml)) if expected_slot_code == "100001" else 0
            for _info, rel_name, target in selected:
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(staging_root / rel_name, target)

        media = tuple(str(p) for p in sorted(out.rglob("*")) if p.is_file() and p != copied_xml)
        return SlotResult(slot_code=expected_slot_code, xml_path=str(copied_xml), pages=1, counts=counts, media_files=media)
    finally:
        try:
            active_zip.close()
        except Exception:
            pass
        try:
            if outer_zip is not None:
                outer_zip.close()
        except Exception:
            pass
        try:
            if inner_buf is not None:
                inner_buf.close()
        except Exception:
            pass


def _enabled_sections_for(section_key: str) -> dict[str, bool]:
    return {
        "claims": section_key == "claims",
        "description": section_key == "description",
        "drawings": section_key == "drawings",
        "abstract": section_key == "abstract",
        "request_form": False,
    }


def _copy_converted_folder(source_folder: Path, target_folder: Path, source_xml: Path, target_xml: Path) -> None:
    target_folder.mkdir(parents=True, exist_ok=True)
    for source_file in source_folder.iterdir():
        if not source_file.is_file():
            continue
        if source_file == source_xml:
            continue
        shutil.copy2(str(source_file), str(target_folder / source_file.name))
    if source_xml.resolve() != target_xml.resolve():
        shutil.copy2(str(source_xml), str(target_xml))


def _normalize_slot_xml(xml_path: Path, slot_code: str) -> None:
    if slot_code == "100012_body":
        normalize_opinion_body_xml(xml_path)
    elif slot_code == "100001":
        normalize_claims_for_response_correction(xml_path)


def convert_document_slot(
    input_path: str,
    slot_code: str,
    output_dir: str,
    *,
    patent_type: str,
    progress_callback=None,
    disable_centering: bool = False,
    case_id: str | None = None,
) -> SlotResult:
    """Convert one user-selected document slot to XML.

    Pre-converted XML packages are extracted directly for four-book slots.
    Word files are routed through the existing conversion pipeline with a
    forced section key so user-selected slots do not depend on section headers.
    """
    source = Path(str(input_path or ""))
    if not source.is_file():
        raise FileNotFoundError(str(source))
    if slot_code not in _SLOT_TO_SECTION:
        raise ValueError(f"不支持的答复/补正文书槽位：{slot_code}")
    suffix = source.suffix.lower()
    if suffix == ".xml":
        target_name = "section_1.xml" if slot_code == "100012_body" else f"{slot_code}.xml"
        return _copy_preconverted(str(source), output_dir, target_name, slot_code)
    if suffix == ".zip":
        if slot_code == "100012_body":
            raise ValueError("意见陈述正文仅支持 Word 文档")
        return extract_preconverted_slot_package(str(source), slot_code, output_dir)
    if slot_code == "100012_body" and not disable_centering:
        raise ValueError("意见陈述正文转档必须禁用居中处理")

    section_key = _SLOT_TO_SECTION[slot_code]
    conversion_folder = _SLOT_TO_CONVERSION_FOLDER[slot_code]
    target_folder = Path(output_dir)
    target_name = "section_1.xml" if slot_code == "100012_body" else f"{slot_code}.xml"
    target_xml = target_folder / target_name
    resolved_case_id = str(case_id or "").strip() or generate_case_id()

    with tempfile.TemporaryDirectory(prefix="response_correction_slot_") as td:
        temp_root = Path(td)
        temp_output = (temp_root / "output").resolve()
        temp_processing = (temp_root / "temp_processing").resolve()
        temp_output.mkdir(parents=True, exist_ok=True)
        temp_processing.mkdir(parents=True, exist_ok=True)
        output_body_root_tags = {"abstract": "cn-other-file"} if slot_code == "100012_body" else None
        image_prefix_overrides = {"abstract": "zjwj"} if slot_code == "100012_body" else None

        result = run_conversion(
            str(source),
            progress_callback=progress_callback,
            optimize_equation_centering=False if disable_centering else None,
            optimize_table_image_centering=False if disable_centering else None,
            case_id=resolved_case_id,
            patent_type=patent_type,
            enabled_sections=_enabled_sections_for(section_key),
            forced_section_key=section_key,
            output_dir_override=str(temp_output),
            temp_dir_override=str(temp_processing),
            output_body_root_tags=output_body_root_tags,
            image_prefix_overrides=image_prefix_overrides,
        )

        case_root = result.get("case_root") if isinstance(result, dict) else None
        source_folder = (Path(case_root) if case_root else temp_output / resolved_case_id) / conversion_folder
        source_xml = source_folder / f"{conversion_folder}.xml"
        if not source_xml.is_file():
            raise RuntimeError(f"槽位转档未生成预期 XML：{source_xml}")

        target_folder.mkdir(parents=True, exist_ok=True)
        if slot_code == "100012_body":
            shutil.copy2(str(source_xml), str(target_xml))
            _normalize_slot_xml(target_xml, slot_code)
            for source_file in source_folder.iterdir():
                if source_file.is_file() and source_file != source_xml:
                    shutil.copy2(str(source_file), str(target_folder / source_file.name))
        else:
            _copy_converted_folder(source_folder, target_folder, source_xml, target_xml)
            _normalize_slot_xml(target_xml, slot_code)

    counts = count_claims(str(target_xml)) if slot_code == "100001" else 0
    media = tuple(str(p) for p in sorted(target_folder.rglob("*")) if p.is_file() and p != target_xml)
    return SlotResult(slot_code=slot_code, xml_path=str(target_xml), pages=1, counts=counts, media_files=media)


__all__ = ["convert_document_slot", "extract_preconverted_slot_package"]
