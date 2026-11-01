from __future__ import annotations

import os
import shutil
import tempfile
import zipfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Iterator
from xml.etree import ElementTree as ET

from core.archive_safety import ArchiveBudget, ArchivePathError, ArchiveSafetyError, safe_member_path

from .attachments import IMAGE_SUFFIXES, looks_like_image, looks_like_pdf, unsupported_attachment_message
from .models import PreviewDocument, PreviewManifestResult


# These form codes are provided by the pinned official runtime.  The display-name
# fallback also keeps a newly introduced request form ahead of the technical
# documents until a later user-configurable ordering feature is added.
_REQUEST_FORM_CODES = frozenset(
    {
        "110101",
        "110301",
        "110401",
        "110402",
        "110403",
        "110404",
        "110405",
        "120101",
        "120701",
    }
)
_TECHNICAL_DOCUMENT_ORDER = {
    "100004": 0,  # 说明书摘要
    "100001": 1,  # 权利要求书
    "100002": 2,  # 说明书
    "100003": 3,  # 说明书附图
}
_TECHNICAL_DOCUMENT_NAMES = {
    "100001": "权利要求书",
    "100002": "说明书",
    "100003": "说明书附图",
    "100004": "说明书摘要",
}

_MEMBER_HEADER_BYTES = 4096


class PreviewPackageError(RuntimeError):
    pass


@dataclass(frozen=True)
class PreparedPreviewPackage:
    workspace: Path
    case_root: Path
    documents: tuple[PreviewDocument, ...]
    xml_paths_by_document_id: dict[str, Path] = field(default_factory=dict)
    pdf_paths_by_document_id: dict[str, Path] = field(default_factory=dict)
    errors_by_document_id: dict[str, str] = field(default_factory=dict)


def _normalise_archive_member(name: str) -> PurePosixPath:
    try:
        return safe_member_path(name)
    except ArchivePathError as exc:
        raise PreviewPackageError(f"ZIP contains an unsafe member path: {name!r}") from exc


def _extract_archive_safely(archive_path: Path, destination: Path, budget: ArchiveBudget) -> None:
    try:
        with zipfile.ZipFile(archive_path, "r") as archive:
            infos = budget.validate(archive)
            targets: list[tuple[zipfile.ZipInfo, Path]] = []
            for info in infos:
                member = _normalise_archive_member(info.filename)
                target = (destination.joinpath(*member.parts)).resolve()
                try:
                    target.relative_to(destination.resolve())
                except ValueError as exc:
                    raise PreviewPackageError(f"ZIP member escapes the preview workspace: {info.filename!r}") from exc
                targets.append((info, target))
            for info, target in targets:
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("wb") as output:
                    budget.copy(archive, info, output)
    except ArchivePathError as exc:
        raise PreviewPackageError(f"ZIP contains an unsafe member path: {exc}") from exc
    except ArchiveSafetyError as exc:
        raise PreviewPackageError(str(exc)) from exc
    except zipfile.BadZipFile as exc:
        raise PreviewPackageError("案卷 ZIP 无法打开或文件已损坏。") from exc


def _unwrap_single_nested_zip(archive_path: Path, workspace: Path, budget: ArchiveBudget, *, max_depth: int = 3) -> Path:
    current = archive_path
    for depth in range(max_depth):
        try:
            with zipfile.ZipFile(current, "r") as archive:
                files = [info for info in archive.infolist() if not info.is_dir()]
                zip_entries = [info for info in files if info.filename.lower().endswith(".zip")]
                if len(files) != 1 or len(zip_entries) != 1:
                    return current
                budget.validate(archive)
                nested_member = _normalise_archive_member(zip_entries[0].filename)
                nested = workspace / f"nested_{depth + 1}_{nested_member.name}"
                with nested.open("wb") as output:
                    budget.copy(archive, zip_entries[0], output)
                current = nested
        except ArchiveSafetyError as exc:
            raise PreviewPackageError(str(exc)) from exc
        except zipfile.BadZipFile as exc:
            raise PreviewPackageError("案卷 ZIP 无法打开或文件已损坏。") from exc
    return current


def _find_case_manifest(extracted_root: Path) -> Path | None:
    candidates = sorted(
        (path for path in extracted_root.rglob("list.xml") if path.is_file()),
        key=lambda path: (len(path.relative_to(extracted_root).parts), str(path).lower()),
    )
    if not candidates:
        return None
    if len(candidates) != 1:
        raise PreviewPackageError("案卷中存在多个 list.xml，无法确定要预览的案件。")
    return candidates[0]


def _child_text(element: ET.Element, tag_name: str) -> str:
    for child in list(element):
        tag = str(child.tag or "").rsplit("}", 1)[-1]
        if tag == tag_name:
            return str(child.text or "").strip()
    return ""


def _document_id(index: int, code: str, relative_path: str) -> str:
    return f"{index}:{code}:{relative_path}"


def _resolve_member_path(case_root: Path, relative_path: str) -> Path:
    """Resolve one manifest member inside the case root; XML entries and attachments share these checks."""
    try:
        normalized = _normalise_archive_member(relative_path)
    except PreviewPackageError as exc:
        raise PreviewPackageError("list.xml 中的文件路径不安全，已拒绝渲染。") from exc
    target = (case_root.joinpath(*normalized.parts)).resolve()
    try:
        target.relative_to(case_root.resolve())
    except ValueError as exc:
        raise PreviewPackageError("list.xml 中的文件路径越出了案卷目录。") from exc
    if not target.is_file():
        raise PreviewPackageError("list.xml 声明的文件在案卷中不存在。")
    return target


def _read_member_header(path: Path) -> bytes:
    with path.open("rb") as handle:
        return handle.read(_MEMBER_HEADER_BYTES)


def _classify_manifest_member(path: Path, header: bytes) -> str:
    """Route one entry by file content; the real suffix and the manifest GESHILX are only hints."""
    if looks_like_pdf(header) or looks_like_image(header):
        return "attachment"
    if path.suffix.lower() == ".xml" or header.lstrip().startswith(b"<"):
        return "xml"
    return "attachment"


def _attachment_format_error(path: Path, header: bytes) -> str:
    """Return the per-document message when an attachment cannot become a PDF, else an empty string."""
    if looks_like_pdf(header) or path.suffix.lower() in IMAGE_SUFFIXES or looks_like_image(header):
        return ""
    return unsupported_attachment_message(path.name)


def _preview_document_sort_key(document: PreviewDocument) -> tuple[int, int]:
    """Return the fixed default UI/export order while retaining manifest order within a group."""
    if document.code in _REQUEST_FORM_CODES or "请求书" in document.display_name:
        return (0, 0)
    technical_position = _TECHNICAL_DOCUMENT_ORDER.get(document.code)
    if technical_position is not None:
        return (1, technical_position)
    return (2, 0)


def _parse_manifest(manifest_path: Path) -> tuple[tuple[PreviewDocument, ...], dict[str, Path], dict[str, Path], dict[str, str]]:
    try:
        root = ET.parse(manifest_path).getroot()
    except (ET.ParseError, OSError) as exc:
        raise PreviewPackageError(f"无法解析案卷 list.xml：{exc}") from exc

    documents: list[PreviewDocument] = []
    xml_paths: dict[str, Path] = {}
    pdf_paths: dict[str, Path] = {}
    errors: dict[str, str] = {}
    case_root = manifest_path.parent.resolve()

    entries = [element for element in root.iter() if str(element.tag or "").rsplit("}", 1)[-1] == "BAONEIWJXX"]
    if not entries:
        raise PreviewPackageError("list.xml 未声明任何案卷文件。")

    for index, entry in enumerate(entries, start=1):
        code = _child_text(entry, "BIAOGEDM")
        relative_path = _child_text(entry, "XIANGDUILJ")
        file_name = _child_text(entry, "WENJIANBZ")
        display_name = _child_text(entry, "WENJIANMC") or Path(file_name or relative_path or code or "未命名文件").stem
        document = PreviewDocument(
            id=_document_id(index, code, relative_path or file_name),
            code=code,
            display_name=display_name,
            relative_path=relative_path or file_name,
        )
        documents.append(document)

        if not document.relative_path:
            errors[document.id] = "案卷清单缺少文件位置，无法读取该文件，请检查案卷内容或重新导出案卷。"
            continue
        try:
            member_path = _resolve_member_path(case_root, document.relative_path)
            header = _read_member_header(member_path)
        except PreviewPackageError as exc:
            errors[document.id] = str(exc)
            continue
        except OSError as exc:
            errors[document.id] = f"无法读取案卷文件：{document.relative_path}（{exc}）"
            continue
        if _classify_manifest_member(member_path, header) == "xml":
            if not code:
                errors[document.id] = "案卷清单缺少文书类型，无法生成该文件的预览，请检查案卷内容或重新导出案卷。"
                continue
            xml_paths[document.id] = member_path
            continue
        attachment_error = _attachment_format_error(member_path, header)
        if attachment_error:
            errors[document.id] = attachment_error
            continue
        pdf_paths[document.id] = member_path

    # Python sorting is stable, so same-priority request forms and all remaining
    # forms keep the order in which the official case manifest declared them.
    return (
        tuple(sorted(documents, key=_preview_document_sort_key)),
        xml_paths,
        pdf_paths,
        errors,
    )


def _discover_technical_documents(extracted_root: Path) -> tuple[tuple[PreviewDocument, ...], dict[str, Path]]:
    # Without a manifest, only the four official technical-document filenames
    # establish a form code. Keep their original directories for image references.
    candidates = sorted(
        (
            path for path in extracted_root.rglob("*")
            if path.is_file() and path.suffix.lower() == ".xml" and path.stem in _TECHNICAL_DOCUMENT_NAMES
        ),
        key=lambda path: path.relative_to(extracted_root).as_posix().lower(),
    )
    if not candidates:
        raise PreviewPackageError(
            "案卷中未找到 list.xml，也未找到四书 XML（100001.xml 至 100004.xml）。"
        )
    documents: list[PreviewDocument] = []
    xml_paths: dict[str, Path] = {}
    for index, path in enumerate(candidates, start=1):
        code = path.stem
        relative_path = path.relative_to(extracted_root).as_posix()
        document = PreviewDocument(
            id=_document_id(index, code, relative_path),
            code=code,
            display_name=_TECHNICAL_DOCUMENT_NAMES[code],
            relative_path=relative_path,
        )
        documents.append(document)
        xml_paths[document.id] = path.resolve()
    return tuple(sorted(documents, key=_preview_document_sort_key)), xml_paths


@contextmanager
def prepare_preview_package(zip_path: str | os.PathLike[str]) -> Iterator[PreparedPreviewPackage]:
    source = Path(zip_path).expanduser().resolve()
    if not source.is_file():
        raise PreviewPackageError("未找到可预览的案卷 ZIP 文件。")

    workspace = Path(tempfile.mkdtemp(prefix="cnipa_preview_"))
    try:
        budget = ArchiveBudget()
        active_archive = _unwrap_single_nested_zip(source, workspace, budget)
        extracted_root = workspace / "case"
        extracted_root.mkdir(parents=True, exist_ok=True)
        _extract_archive_safely(active_archive, extracted_root, budget)
        manifest_path = _find_case_manifest(extracted_root)
        if manifest_path is None:
            documents, xml_paths = _discover_technical_documents(extracted_root)
            pdf_paths: dict[str, Path] = {}
            errors = {}
            case_root = extracted_root.resolve()
        else:
            documents, xml_paths, pdf_paths, errors = _parse_manifest(manifest_path)
            case_root = manifest_path.parent.resolve()
        yield PreparedPreviewPackage(
            workspace=workspace,
            case_root=case_root,
            documents=documents,
            xml_paths_by_document_id=xml_paths,
            pdf_paths_by_document_id=pdf_paths,
            errors_by_document_id=errors,
        )
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def inspect_preview_package(zip_path: str | os.PathLike[str]) -> PreviewManifestResult:
    """Identify manifest entries or standalone four-book XML without starting the renderer."""
    with prepare_preview_package(zip_path) as package:
        return PreviewManifestResult(
            documents=package.documents,
            errors_by_document_id=dict(package.errors_by_document_id),
            passthrough_document_ids=frozenset(package.pdf_paths_by_document_id),
        )


__all__ = ["PreparedPreviewPackage", "PreviewPackageError", "inspect_preview_package", "prepare_preview_package"]
