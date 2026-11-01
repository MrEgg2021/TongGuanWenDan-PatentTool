from __future__ import annotations

import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Callable

from core.config import sanitize_filename

from .forms import write_correction_form_xml, write_response_form_xml
from .manifest import ManifestEntry, count_claims, generate_case_id, make_entry, write_manifest
from .models import CorrectionPackageRequest, PackageResult, ResponsePackageRequest, SlotInput
from .slot_conversion import convert_document_slot
from .xml_normalize import normalize_claims_for_response_correction, normalize_opinion_body_xml

_SLOT_ORDER = ("100001", "100002", "100003", "100004")
ProgressCallback = Callable[[int, str, str], None]
_SLOT_DISPLAY_NAMES = {
    "100001": "权利要求书",
    "100002": "说明书",
    "100003": "说明书附图",
    "100004": "说明书摘要",
    "100012_body": "意见陈述书",
}
_PACKAGE_PREFIX_BY_SCENE = {
    "notice_response": "答复审查意见",
    "notice_correction": "答复补正",
    "active_response": "主动答复",
    "active_correction": "主动补正",
}


def _report_progress(progress_callback: ProgressCallback | None, percent: int, primary: str, detail: str) -> None:
    if not callable(progress_callback):
        return
    progress_callback(int(percent), str(primary or ""), str(detail or ""))


def _primary_for_stage(fallback: str, stage: str) -> str:
    mapping = {
        "prepare": "正在准备案卷包",
        "opinion": "正在处理意见陈述书",
        "slots": "正在处理四书",
        "form": "正在生成主 XML",
        "manifest": "正在生成 list.xml",
        "zip": "正在打包案卷",
        "cleanup": "正在清理临时文件",
    }
    return mapping.get(str(stage or "").strip(), str(fallback or "").strip() or "正在处理案卷包")


def _scaled_percent(start_percent: int, end_percent: int, current_percent: int) -> int:
    bounded = max(0, min(100, int(current_percent)))
    return int(start_percent + ((end_percent - start_percent) * bounded / 100))


def _section_display_name(section_key: str) -> str:
    return {
        "claims": "权利要求书",
        "description": "说明书",
        "drawings": "说明书附图",
        "abstract": "摘要",
    }.get(str(section_key or "").strip(), str(section_key or "").strip() or "正文")


def _slot_stage_text(display_name: str, action: str) -> str:
    return f"四书槽位（{display_name}）：{action}"


def _file_progress_prefix(*, files_total: int, file_index: int, file_name: str) -> str:
    safe_total = max(1, int(files_total or 1))
    safe_index = max(1, min(safe_total, int(file_index or 1)))
    return f"共 {safe_total} 个文件，正在处理第 {safe_index}/{safe_total} 个文件：{file_name}"


def _file_progress_detail(
    *,
    files_total: int,
    file_index: int,
    file_name: str,
    stage_text: str,
    paragraph_current: int | None = None,
    paragraph_total: int | None = None,
) -> str:
    detail = f"{_file_progress_prefix(files_total=files_total, file_index=file_index, file_name=file_name)} | {stage_text}"
    if paragraph_current is not None and paragraph_total is not None and paragraph_total > 0:
        detail += f" | 第 {paragraph_current}/{paragraph_total} 段"
    return detail


def _post_file_stage_detail(*, files_total: int, stage_text: str) -> str:
    return f"共 {max(1, int(files_total or 1))} 个文件，文件处理已完成 | {stage_text}"


def _conversion_stage_percent(stage: str, payload: dict) -> int:
    stage_key = str(stage or "").strip()
    fixed = {
        "init_load_config": 4,
        "init_modules": 8,
        "init_start_word": 12,
        "start": 18,
        "section_plan_ready": 24,
        "scan_ready": 32,
        "before_generate": 92,
        "generate_110101": 96,
        "done": 100,
    }
    if stage_key == "paragraph":
        try:
            index = int(payload.get("index") or 0)
            total = max(1, int(payload.get("total") or 1))
        except Exception:
            index = 0
            total = 1
        return 38 + int(48 * max(0, min(total, index)) / total)
    return fixed.get(stage_key, 24)


def _conversion_stage_detail(
    stage: str,
    payload: dict,
    *,
    source_path: str,
    display_name: str,
    files_total: int,
    file_index: int,
) -> str:
    file_name = Path(str(source_path or "")).name
    stage_key = str(stage or "").strip()
    if stage_key == "scan_ready":
        total = int(payload.get("total_paragraphs") or 0)
        stage_text = f"分析文件内容（{display_name}）"
        if total > 0:
            stage_text += f"，共 {total} 段"
        return _file_progress_detail(
            files_total=files_total,
            file_index=file_index,
            file_name=file_name,
            stage_text=stage_text,
        )
    if stage_key == "paragraph":
        try:
            index = int(payload.get("index") or 0)
            total = max(1, int(payload.get("total") or 1))
        except Exception:
            index = 0
            total = 1
        section_text = _section_display_name(str(payload.get("section") or ""))
        return _file_progress_detail(
            files_total=files_total,
            file_index=file_index,
            file_name=file_name,
            stage_text=f"正在处理段落（{display_name} / {section_text}）",
            paragraph_current=index,
            paragraph_total=total,
        )
    if stage_key == "before_generate":
        return _file_progress_detail(
            files_total=files_total,
            file_index=file_index,
            file_name=file_name,
            stage_text=f"正在生成 XML（{display_name}）",
        )
    if stage_key == "generate_110101":
        return _file_progress_detail(
            files_total=files_total,
            file_index=file_index,
            file_name=file_name,
            stage_text=f"正在生成请求 XML（{display_name}）",
        )
    if stage_key == "done":
        return _file_progress_detail(
            files_total=files_total,
            file_index=file_index,
            file_name=file_name,
            stage_text=f"转换完成（{display_name}）",
        )
    message = str(payload.get("message") or "").strip()
    if message:
        return _file_progress_detail(
            files_total=files_total,
            file_index=file_index,
            file_name=file_name,
            stage_text=f"{display_name}：{message}",
        )
    return _file_progress_detail(
        files_total=files_total,
        file_index=file_index,
        file_name=file_name,
        stage_text=f"正在处理{display_name}",
    )


def _conversion_progress_adapter(
    progress_callback: ProgressCallback | None,
    *,
    primary_text: str,
    display_name: str,
    source_path: str,
    files_total: int,
    file_index: int,
    start_percent: int,
    end_percent: int,
):
    if not callable(progress_callback):
        return None

    def _callback(stage: str, payload: dict) -> None:
        safe_payload = payload if isinstance(payload, dict) else {}
        percent = _scaled_percent(start_percent, end_percent, _conversion_stage_percent(stage, safe_payload))
        detail = _conversion_stage_detail(
            stage,
            safe_payload,
            source_path=source_path,
            display_name=display_name,
            files_total=files_total,
            file_index=file_index,
        )
        _report_progress(progress_callback, percent, primary_text, detail)

    return _callback


def _copy_file(src: str, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(src), str(dst))


def _copy_slot(
    slot_code: str,
    slot: SlotInput,
    case_root: Path,
    *,
    patent_type: str,
    case_id: str,
    progress_callback: ProgressCallback | None = None,
    primary_text: str = "正在生成答复/补正包",
    files_total: int = 1,
    file_index: int = 1,
    progress_start: int = 0,
    progress_end: int = 100,
) -> ManifestEntry:
    folder = case_root / slot_code
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{slot_code}.xml"
    file_name = Path(slot.path).name
    display_name = _SLOT_DISPLAY_NAMES.get(slot_code, slot_code)
    if Path(slot.path).suffix.lower() == ".xml":
        _report_progress(
            progress_callback,
            progress_start,
            primary_text,
            _file_progress_detail(
                files_total=files_total,
                file_index=file_index,
                file_name=file_name,
                stage_text=_slot_stage_text(display_name, "复制预转换 XML"),
            ),
        )
        _copy_file(slot.path, target)
        if slot_code == "100001":
            normalize_claims_for_response_correction(target)
    else:
        _report_progress(
            progress_callback,
            progress_start,
            primary_text,
            _file_progress_detail(
                files_total=files_total,
                file_index=file_index,
                file_name=file_name,
                stage_text=_slot_stage_text(display_name, "分析文件内容"),
            ),
        )
        result = convert_document_slot(
            slot.path,
            slot_code,
            str(folder),
            patent_type=patent_type,
            case_id=case_id,
            progress_callback=_conversion_progress_adapter(
                progress_callback,
                primary_text=primary_text,
                display_name=display_name,
                source_path=slot.path,
                files_total=files_total,
                file_index=file_index,
                start_percent=progress_start,
                end_percent=progress_end,
            ),
        )
        if Path(result.xml_path).resolve() != target.resolve():
            _copy_file(result.xml_path, target)
    _report_progress(
        progress_callback,
        progress_end,
        primary_text,
        _file_progress_detail(
            files_total=files_total,
            file_index=file_index,
            file_name=file_name,
            stage_text=_slot_stage_text(display_name, "当前文件处理完成"),
        ),
    )
    counts = count_claims(str(target)) if slot_code == "100001" else 0
    return make_entry(slot_code, counts=counts)


def _zip_dir(source_dir: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(source_dir.rglob("*")):
            if file_path.is_file():
                zf.write(file_path, file_path.relative_to(source_dir.parent).as_posix())


def _outer_zip(inner_zip: Path, output_dir: Path, *, prefix: str) -> Path:
    safe_prefix = sanitize_filename(prefix) or "答复包"
    outer = output_dir / f"{safe_prefix}.zip"
    counter = 2
    while outer.exists():
        outer = output_dir / f"{safe_prefix} ({counter}).zip"
        counter += 1
    with zipfile.ZipFile(outer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(inner_zip, inner_zip.name)
    return outer


def _package_prefix(submission_scene: str, request_notice) -> str:
    prefix = _PACKAGE_PREFIX_BY_SCENE.get(str(submission_scene or "").strip(), "答复补正")
    parts = [prefix]
    invention_title = str(getattr(request_notice, "invention_title", "") or "").strip()
    application_no = str(getattr(request_notice, "application_no", "") or "").strip()
    notice_name = str(getattr(request_notice, "notice_name", "") or "").strip()
    if invention_title:
        parts.append(invention_title)
    if application_no:
        parts.append(application_no)
    if str(submission_scene or "").strip() in {"notice_response", "notice_correction"} and notice_name:
        parts.append(notice_name)
    cleaned = [sanitize_filename(part) for part in parts if str(part or "").strip()]
    return "+".join(part for part in cleaned if part) or sanitize_filename(prefix) or "答复包"


def _prepare_case_root(*, case_id: str) -> tuple[Path, Path]:
    work = Path(tempfile.mkdtemp(prefix="response_correction_work_")).resolve()
    case_root = work / case_id
    case_root.mkdir(parents=True, exist_ok=True)
    return work, case_root


def _cleanup_work_root(work_root: Path) -> None:
    try:
        shutil.rmtree(work_root, ignore_errors=True)
    except Exception:
        pass


def _finish_package(
    output_dir: Path,
    work_root: Path,
    case_root: Path,
    *,
    case_id: str,
    prefix: str,
    files_total: int,
    generated_files: list[str],
    progress_callback: ProgressCallback | None = None,
    primary_text: str = "正在生成答复/补正包",
) -> PackageResult:
    inner_zip = work_root / f"{case_id}.zip"
    _report_progress(
        progress_callback,
        88,
        _primary_for_stage(primary_text, "zip"),
        _post_file_stage_detail(files_total=files_total, stage_text="正在打 inner zip"),
    )
    _zip_dir(case_root, inner_zip)
    _report_progress(
        progress_callback,
        94,
        _primary_for_stage(primary_text, "zip"),
        _post_file_stage_detail(files_total=files_total, stage_text="正在打 outer zip"),
    )
    outer = _outer_zip(inner_zip, output_dir, prefix=prefix)
    return PackageResult(
        outer_zip_path=str(outer),
        inner_zip_path="",
        case_root="",
        generated_files=(str(outer),),
    )


def _response_file_plan(request: ResponsePackageRequest) -> list[tuple[str, str, str]]:
    items: list[tuple[str, str, str]] = [("100012_body", _SLOT_DISPLAY_NAMES["100012_body"], request.opinion_body.path)]
    for code in _SLOT_ORDER:
        slot = request.slots.get(code)
        if slot:
            items.append((code, _SLOT_DISPLAY_NAMES.get(code, code), slot.path))
    return items


def _correction_file_plan(request: CorrectionPackageRequest) -> list[tuple[str, str, str]]:
    items: list[tuple[str, str, str]] = []
    for code in _SLOT_ORDER:
        slot = request.slots.get(code)
        if slot:
            items.append((code, _SLOT_DISPLAY_NAMES.get(code, code), slot.path))
    return items


def _slot_entries(
    slots: dict[str, SlotInput],
    case_root: Path,
    *,
    patent_type: str,
    case_id: str,
    files_total: int,
    start_file_index: int,
    progress_callback: ProgressCallback | None = None,
    primary_text: str = "正在生成答复/补正包",
    start_percent: int = 45,
    end_percent: int = 70,
) -> list[ManifestEntry]:
    entries: list[ManifestEntry] = []
    active_codes = [code for code in _SLOT_ORDER if slots.get(code)]
    total = max(1, len(active_codes))
    for code in _SLOT_ORDER:
        slot = slots.get(code)
        if not slot:
            continue
        item_start = start_percent + int((end_percent - start_percent) * len(entries) / total)
        item_end = start_percent + int((end_percent - start_percent) * (len(entries) + 1) / total)
        file_index = start_file_index + len(entries)
        entries.append(
            _copy_slot(
                code,
                slot,
                case_root,
                patent_type=patent_type,
                case_id=case_id,
                files_total=files_total,
                file_index=file_index,
                progress_callback=progress_callback,
                primary_text=primary_text,
                progress_start=item_start,
                progress_end=max(item_start, item_end),
            )
        )
    return entries


def build_response_package(
    request: ResponsePackageRequest,
    *,
    progress_callback: ProgressCallback | None = None,
) -> PackageResult:
    primary_text = "正在生成审查意见答复包"
    file_plan = _response_file_plan(request)
    files_total = max(1, len(file_plan))
    _report_progress(progress_callback, 5, primary_text, _post_file_stage_detail(files_total=files_total, stage_text="准备工作目录"))
    case_id = generate_case_id()
    out = Path(str(request.output_dir or "")).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    work_root, case_root = _prepare_case_root(case_id=case_id)
    generated: list[str] = []
    try:
        form_dir = case_root / "100012"
        form_dir.mkdir(parents=True, exist_ok=True)

        body_target = form_dir / "section_1.xml"
        body_file_name = Path(request.opinion_body.path).name
        _report_progress(
            progress_callback,
            18,
            primary_text,
            _file_progress_detail(
                files_total=files_total,
                file_index=1,
                file_name=body_file_name,
                stage_text="分析文件内容（意见陈述书正文）",
            ),
        )
        if request.opinion_body.preconverted or Path(request.opinion_body.path).suffix.lower() == ".xml":
            _copy_file(request.opinion_body.path, body_target)
            normalize_opinion_body_xml(body_target)
            _report_progress(
                progress_callback,
                28,
                _primary_for_stage(primary_text, "opinion"),
                _file_progress_detail(
                    files_total=files_total,
                    file_index=1,
                    file_name=body_file_name,
                    stage_text="复制预转换 XML（意见陈述书正文）",
                ),
            )
        else:
            result = convert_document_slot(
                request.opinion_body.path,
                "100012_body",
                str(form_dir),
                patent_type=request.notice.patent_type,
                disable_centering=True,
                case_id=case_id,
                progress_callback=_conversion_progress_adapter(
                    progress_callback,
                    primary_text=_primary_for_stage(primary_text, "opinion"),
                    display_name=_SLOT_DISPLAY_NAMES["100012_body"],
                    source_path=request.opinion_body.path,
                    files_total=files_total,
                    file_index=1,
                    start_percent=20,
                    end_percent=40,
                ),
            )
            if Path(result.xml_path).resolve() != body_target.resolve():
                _copy_file(result.xml_path, body_target)
        _report_progress(
            progress_callback,
            40,
            _primary_for_stage(primary_text, "opinion"),
            _file_progress_detail(
                files_total=files_total,
                file_index=1,
                file_name=body_file_name,
                stage_text="当前文件处理完成（意见陈述书正文）",
            ),
        )
        generated.append(str(body_target))

        entries = [make_entry("100012", pages=1)]
        attachment_names: list[tuple[str, str]] = []

        slot_entries = _slot_entries(
            request.slots,
            case_root,
            patent_type=request.notice.patent_type,
            case_id=case_id,
            files_total=files_total,
            start_file_index=2,
            progress_callback=progress_callback,
            primary_text=_primary_for_stage(primary_text, "slots"),
            start_percent=45,
            end_percent=68,
        )
        entries.extend(slot_entries)
        for slot_entry in slot_entries:
            attachment_names.append((slot_entry.display_name, slot_entry.display_name))

        _report_progress(
            progress_callback,
            74,
            _primary_for_stage(primary_text, "form"),
            _post_file_stage_detail(files_total=files_total, stage_text="生成主 XML"),
        )
        form_path = write_response_form_xml(
            form_dir / "100012.xml",
            notice=request.notice,
            attachment_names=attachment_names,
            submission_scene=request.submission_scene,
            signature=request.signature,
            signature_year=request.signature_year,
            signature_month=request.signature_month,
            signature_day=request.signature_day,
        )
        generated.append(form_path)
        _report_progress(
            progress_callback,
            84,
            _primary_for_stage(primary_text, "manifest"),
            _post_file_stage_detail(files_total=files_total, stage_text="生成 list.xml"),
        )
        write_manifest(
            case_root,
            case_id=case_id,
            submission_scene=request.submission_scene,
            notice=request.notice,
            entries=entries,
        )
        return _finish_package(
            out,
            work_root,
            case_root,
            case_id=case_id,
            prefix=_package_prefix(request.submission_scene, request.notice),
            files_total=files_total,
            generated_files=generated,
            progress_callback=progress_callback,
            primary_text=primary_text,
        )
    finally:
        _report_progress(
            progress_callback,
            100,
            _primary_for_stage(primary_text, "cleanup"),
            _post_file_stage_detail(files_total=files_total, stage_text="完成并清理临时文件"),
        )
        _cleanup_work_root(work_root)


def build_correction_package(
    request: CorrectionPackageRequest,
    *,
    progress_callback: ProgressCallback | None = None,
) -> PackageResult:
    primary_text = "正在生成补正答复包"
    file_plan = _correction_file_plan(request)
    files_total = max(1, len(file_plan))
    _report_progress(progress_callback, 5, primary_text, _post_file_stage_detail(files_total=files_total, stage_text="准备工作目录"))
    case_id = generate_case_id()
    out = Path(str(request.output_dir or "")).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    work_root, case_root = _prepare_case_root(case_id=case_id)
    generated: list[str] = []
    try:
        entries = [make_entry("100006", pages=1)]
        attachment_names: list[tuple[str, str]] = []
        form_dir = case_root / "100006"
        form_dir.mkdir(parents=True, exist_ok=True)

        slot_entries = _slot_entries(
            request.slots,
            case_root,
            patent_type=request.notice.patent_type,
            case_id=case_id,
            files_total=files_total,
            start_file_index=1,
            progress_callback=progress_callback,
            primary_text=_primary_for_stage(primary_text, "slots"),
            start_percent=22,
            end_percent=50,
        )
        entries.extend(slot_entries)
        for slot_entry in slot_entries:
            attachment_names.append((slot_entry.display_name, slot_entry.display_name))

        _report_progress(
            progress_callback,
            72,
            _primary_for_stage(primary_text, "form"),
            _post_file_stage_detail(files_total=files_total, stage_text="生成主 XML"),
        )
        form_path = write_correction_form_xml(
            form_dir / "100006.xml",
            notice=request.notice,
            correction_items=tuple(request.correction_items or ()),
            attachment_names=attachment_names,
            submission_scene=request.submission_scene,
            signature=request.signature,
            signature_year=request.signature_year,
            signature_month=request.signature_month,
            signature_day=request.signature_day,
        )
        generated.append(form_path)
        _report_progress(
            progress_callback,
            84,
            _primary_for_stage(primary_text, "manifest"),
            _post_file_stage_detail(files_total=files_total, stage_text="生成 list.xml"),
        )
        write_manifest(
            case_root,
            case_id=case_id,
            submission_scene=request.submission_scene,
            notice=request.notice,
            entries=entries,
        )
        return _finish_package(
            out,
            work_root,
            case_root,
            case_id=case_id,
            prefix=_package_prefix(request.submission_scene, request.notice),
            files_total=files_total,
            generated_files=generated,
            progress_callback=progress_callback,
            primary_text=primary_text,
        )
    finally:
        _report_progress(
            progress_callback,
            100,
            _primary_for_stage(primary_text, "cleanup"),
            _post_file_stage_detail(files_total=files_total, stage_text="完成并清理临时文件"),
        )
        _cleanup_work_root(work_root)


__all__ = ["build_correction_package", "build_response_package"]
