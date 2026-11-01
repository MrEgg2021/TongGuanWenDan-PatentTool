from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import fitz
from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import QAbstractItemView, QApplication, QFileDialog

from core.config import sanitize_filename
from core.cnipa_preview.codeset import CODESET_UNAVAILABLE_NOTICE, LOCAL_CODESET_NOTICE
from core.cnipa_preview.package import _REQUEST_FORM_CODES
from core.cnipa_preview.runtime import get_default_runtime_manager
from core.app_preferences import get_pdf_preview_mode
from core.user_messages import user_error_text
from gui.dialog_utils import show_blocking_alert_modal
from gui.tools_ui import inspect_preview_case, preview_single_case
from gui.tools_ui_impl.preview_impl.legacy import LEGACY_PREVIEW_DOCUMENTS
from gui.ui_layout_impl.preview_page import (
    _PREVIEW_STATUS_ROLE,
    _PREVIEW_STATUS_TONE_ROLE,
    rebuild_preview_document_rows,
)


def _write_bytes(path: str, data: bytes) -> None:
    with open(path, "wb") as file_obj:
        file_obj.write(data)


def _export_selected_preview_pdfs(
    *,
    dest_path: str,
    base_name: str,
    pdf_map: dict[str, bytes],
    selected_document_ids: list[str] | None = None,
    selected_codes: list[str] | None = None,
    labels_by_document_id: dict[str, str] | None = None,
    write_bytes=_write_bytes,
) -> tuple[list[str], list[str]]:
    """Exports individual PDFs; ``selected_codes`` remains test-compatible."""

    document_ids = list(selected_document_ids if selected_document_ids is not None else (selected_codes or ()))
    labels = dict(labels_by_document_id or {})
    exported_paths: list[str] = []
    errors: list[str] = []
    dest_dir = os.path.dirname(os.path.abspath(dest_path))
    safe_base_name = sanitize_filename(str(base_name).strip()) or "preview"
    for document_id in document_ids:
        data = pdf_map.get(document_id)
        if not data:
            continue
        label = str(labels.get(document_id, document_id)).strip()
        safe_label = sanitize_filename(label) or document_id
        out_path = os.path.join(dest_dir, f"{safe_base_name}_{safe_label}.pdf")
        suffix = 2
        while os.path.exists(out_path):
            out_path = os.path.join(dest_dir, f"{safe_base_name}_{safe_label} ({suffix}).pdf")
            suffix += 1
        try:
            write_bytes(out_path, data)
            exported_paths.append(out_path)
        except OSError as exc:
            errors.append(f"{out_path}: {exc}")
    return exported_paths, errors


def _document_labels(window) -> dict[str, str]:
    return {
        str(document.id): str(document.display_name)
        for document in tuple(getattr(window, "_preview_documents", ()) or ())
    }


def _selected_document_ids_in_display_order(window, *, require_pdf: bool = False) -> list[str]:
    zip_path = str(getattr(window, "_preview_last_zip_path", "") or "")
    selected = set((getattr(window, "_preview_export_selections", {}) or {}).get(zip_path, set()) or ())
    pdf_map = dict(getattr(window, "_preview_pdf_map", {}) or {})
    return [
        str(document.id)
        for document in tuple(getattr(window, "_preview_documents", ()) or ())
        if str(document.id) in selected and (not require_pdf or str(document.id) in pdf_map)
    ]


def _apply_saved_preview_document_order(window, documents, zip_path: str):
    order = tuple((getattr(window, "_preview_document_orders", {}) or {}).get(str(zip_path), ()) or ())
    positions = {document_id: index for index, document_id in enumerate(order)}
    return tuple(
        sorted(
            tuple(documents or ()),
            key=lambda document: positions.get(str(document.id), len(positions)),
        )
    )


def _write_merged_pdf(destination: str | Path, document_ids: list[str], pdf_map: dict[str, bytes]) -> bool:
    merged = fitz.open()
    try:
        for document_id in document_ids:
            data = pdf_map[document_id]
            document = fitz.open(stream=data, filetype="pdf")
            try:
                merged.insert_pdf(document)
            finally:
                document.close()
        if merged.page_count <= 0:
            return False
        merged.save(str(destination))
        return True
    finally:
        merged.close()


def _preview_source_details(window) -> tuple[str, str]:
    source = str(window._preview_last_zip_path)
    lookup = getattr(window, "_get_preview_leaf_by_zip_path", None)
    if callable(lookup):
        parent, leaf = lookup(source)
        if parent and leaf:
            return str(leaf["name"]) + ".zip", str(Path(parent["source_path"]).parent)
    return source, str(Path(source).parent)


def _materialize_preview_pdf(window) -> str:
    pdf_map = dict(getattr(window, "_preview_pdf_map", {}) or {})
    document_ids = _selected_document_ids_in_display_order(window)
    if not document_ids or any(document_id not in pdf_map for document_id in document_ids):
        window._preview_merged_temp_pdf_path = ""
        return ""
    source_name, _ = _preview_source_details(window)
    filename = f"{sanitize_filename(Path(source_name).stem) or 'preview'}_预览.pdf"
    key = (filename, tuple((document_id, pdf_map[document_id]) for document_id in document_ids))
    existing = getattr(window, "_preview_merged_temp_pdf_path", "")
    if key == getattr(window, "_preview_materialized_key", None) and existing and Path(existing).is_file():
        return existing
    root = Path(window._ensure_preview_temp_root())
    target = Path(tempfile.mkdtemp(prefix="pdf-", dir=root)) / filename
    if len(document_ids) == 1:
        _write_bytes(str(target), pdf_map[document_ids[0]])
    elif not _write_merged_pdf(target, document_ids, pdf_map):
        return ""
    window._preview_merged_temp_pdf_path = str(target)
    window._preview_materialized_key = key
    return str(target)


def _open_preview_with_system_viewer(preview_path: str) -> None:
    """Open the local merged PDF through the Windows file association, never a browser URL."""
    start_file = getattr(os, "startfile", None)
    if not callable(start_file):
        raise RuntimeError("当前系统未提供默认 PDF 阅读器启动接口。")
    start_file(str(preview_path))


def _set_preview_action_summary(window, text: str) -> None:
    label = getattr(window, "preview_action_summary_label", None)
    if label is not None:
        label.setText(str(text or ""))


def _is_request_form_document(document) -> bool:
    """Request forms carry the code-set fields that need the client's local service."""
    return str(getattr(document, "code", "")) in _REQUEST_FORM_CODES or "请求书" in str(getattr(document, "display_name", ""))


def _codeset_notice() -> str:
    """One advisory line for request-form batches, or "" when the client's service answers."""
    reader = getattr(get_default_runtime_manager(), "codeset_state", None)
    state = reader() if callable(reader) else None
    if state is None:
        return ""
    if bool(getattr(state, "available", False)):
        return LOCAL_CODESET_NOTICE if bool(getattr(state, "local_table", False)) else ""
    return CODESET_UNAVAILABLE_NOTICE


def _append_codeset_notice(window) -> None:
    documents = tuple(getattr(window, "_preview_documents", ()) or ())
    if not any(_is_request_form_document(document) for document in documents):
        return
    notice = _codeset_notice()
    label = getattr(window, "preview_action_summary_label", None)
    if not notice or label is None:
        return
    current = str(label.text() or "")
    if notice in current:
        return
    label.setText(f"{current}\n{notice}" if current else notice)


def reset_preview_export_ui(window) -> None:
    window._preview_documents = ()
    window._preview_pdf_map = {}
    window._preview_pdf_errors = {}
    window._preview_manifest_errors = {}
    window._preview_passthrough_ids = frozenset()
    window._preview_merged_temp_pdf_path = ""
    window._preview_materialized_key = None
    window._preview_source_signature = None
    rebuild_preview_document_rows(window, ())
    if hasattr(window, "preview_export_button"):
        window.preview_export_button.setEnabled(False)
    if hasattr(window, "preview_start_button"):
        window.preview_start_button.setText("解析文件清单")
    _set_preview_action_summary(window, "选择案件后先识别文件；无 list.xml 的四书 ZIP 也可预览。")


def prepare_legacy_preview_case(window, zip_path: str) -> None:
    window._preview_last_zip_path = str(zip_path)
    documents = _apply_saved_preview_document_order(window, LEGACY_PREVIEW_DOCUMENTS, zip_path)
    window._preview_documents = documents
    window._preview_pdf_map = {}
    window._preview_pdf_errors = {}
    window._preview_manifest_errors = {}
    window._preview_passthrough_ids = frozenset()
    window._preview_merged_temp_pdf_path = ""
    window._preview_export_selections[str(zip_path)] = {document.id for document in documents}
    rebuild_preview_document_rows(window, documents)
    apply_preview_export_state(window)


def apply_preview_mode_ui(window) -> None:
    mode = get_pdf_preview_mode()
    legacy_button = getattr(window, "preview_legacy_mode_button", None)
    full_button = getattr(window, "preview_full_mode_button", None)
    for button, checked in ((legacy_button, mode == "legacy"), (full_button, mode == "full")):
        if button is not None:
            blocker = QSignalBlocker(button)
            button.setChecked(checked)
            blocker.unblock()
    subtitle = getattr(window, "preview_subtitle_label", None)
    document_list = getattr(window, "preview_document_list", None)
    if mode == "legacy":
        if subtitle is not None:
            subtitle.setText("轻量预览：需安装并启动官方预览插件，仅支持四书。")
        if document_list is not None:
            document_list.setDragDropMode(QAbstractItemView.InternalMove)
    else:
        if subtitle is not None:
            subtitle.setText("全量预览：需安装专利业务办理系统客户端（CNIPA），支持预览和导出案卷内全部文件。")
        if document_list is not None:
            document_list.setDragDropMode(QAbstractItemView.InternalMove)
    reset_preview_export_ui(window)
    try:
        _parent, leaf = window._get_selected_preview_leaf()
    except Exception:
        leaf = None
    zip_path = str((leaf or {}).get("zip_path") or "")
    if not zip_path or not os.path.isfile(zip_path) or bool(getattr(window, "_preview_in_progress", False)):
        if mode == "legacy" and hasattr(window, "preview_start_button"):
            window.preview_start_button.setText("开始轻量预览")
        return
    if mode == "legacy":
        prepare_legacy_preview_case(window, zip_path)
    else:
        inspect_preview_case(window, zip_path)


def on_preview_render_completed(window, result, zip_path: str) -> None:
    window._preview_last_zip_path = str(zip_path)
    result_documents = tuple(getattr(result, "documents", ()) or ())
    if result_documents:
        window._preview_documents = _apply_saved_preview_document_order(window, result_documents, zip_path)
    window._preview_pdf_map.update(dict(getattr(result, "pdf_by_document_id", {}) or {}))
    window._preview_pdf_errors = dict(getattr(result, "errors_by_document_id", {}) or {})
    window._preview_passthrough_ids = frozenset(getattr(result, "passthrough_document_ids", ()) or ())
    source_stat = Path(zip_path).stat()
    window._preview_source_signature = (source_stat.st_size, source_stat.st_mtime_ns)
    apply_preview_export_state(window)
    preview_path = str(getattr(window, "_preview_merged_temp_pdf_path", "") or "")
    if preview_path:
        try:
            _open_preview_with_system_viewer(preview_path)
            _set_preview_action_summary(window, f"已打开 {Path(preview_path).name}；可在阅读器中另存，或点击“另存预览 PDF”。")
        except Exception as exc:
            _set_preview_action_summary(window, f"PDF 已生成，但未能自动打开：{exc}")
    _append_codeset_notice(window)


def on_preview_legacy_completed(window, result, zip_path: str) -> None:
    render_result = result.render_result
    window._preview_last_zip_path = str(zip_path)
    window._preview_documents = _apply_saved_preview_document_order(window, render_result.documents, zip_path)
    window._preview_pdf_map = dict(render_result.pdf_by_document_id)
    window._preview_pdf_errors = dict(render_result.errors_by_document_id)
    window._preview_manifest_errors = {}
    window._preview_passthrough_ids = frozenset(getattr(render_result, "passthrough_document_ids", ()) or ())
    window._preview_export_selections[str(zip_path)] = {document.id for document in render_result.documents}
    rebuild_preview_document_rows(window, window._preview_documents)
    apply_preview_export_state(window)


def on_preview_manifest_completed(window, result, zip_path: str) -> None:
    window._preview_last_zip_path = str(zip_path)
    existing_ids = {str(document.id) for document in tuple(getattr(window, "_preview_documents", ()) or ())}
    documents = _apply_saved_preview_document_order(window, getattr(result, "documents", ()) or (), zip_path)
    window._preview_documents = documents
    window._preview_manifest_errors = dict(getattr(result, "errors_by_document_id", {}) or {})
    window._preview_passthrough_ids = frozenset(getattr(result, "passthrough_document_ids", ()) or ())
    window._preview_pdf_map = {}
    window._preview_pdf_errors = {}
    window._preview_merged_temp_pdf_path = ""
    source_stat = Path(zip_path).stat()
    window._preview_source_signature = (source_stat.st_size, source_stat.st_mtime_ns)
    rebuild_preview_document_rows(window, window._preview_documents)
    valid_ids = {str(document.id) for document in documents if str(document.id) not in window._preview_manifest_errors}
    selections = window._preview_export_selections.get(str(zip_path))
    if not isinstance(selections, set):
        window._preview_export_selections[str(zip_path)] = set(valid_ids)
    else:
        selections.intersection_update(valid_ids)
        selections.update(valid_ids - existing_ids)
    rebuild_preview_document_rows(window, documents)
    apply_preview_export_state(window)


def on_preview_doc_check_toggled(window, document_id: str, checked: bool) -> None:
    zip_path = str(getattr(window, "_preview_last_zip_path", "") or "")
    if not zip_path:
        return
    selections = window._preview_export_selections.get(zip_path)
    if not isinstance(selections, set):
        selections = set()
        window._preview_export_selections[zip_path] = selections
    if checked:
        selections.add(document_id)
    else:
        selections.discard(document_id)
    apply_preview_export_state(window)


def on_preview_documents_reordered(window) -> None:
    document_list = getattr(window, "preview_document_list", None)
    if document_list is None:
        return
    documents_by_id = {str(document.id): document for document in tuple(getattr(window, "_preview_documents", ()) or ())}
    ordered_ids = [
        str(document_list.item(index).data(Qt.UserRole) or "")
        for index in range(document_list.count())
    ]
    if len(ordered_ids) != len(documents_by_id) or any(document_id not in documents_by_id for document_id in ordered_ids):
        # A custom QListWidget row can briefly report an incomplete viewport while
        # Qt completes an internal move. Restore the authoritative document list
        # rather than leaving the user with a visually incomplete list.
        rebuild_preview_document_rows(window, tuple(getattr(window, "_preview_documents", ()) or ()))
        apply_preview_export_state(window)
        return
    window._preview_documents = tuple(documents_by_id[document_id] for document_id in ordered_ids)
    zip_path = str(getattr(window, "_preview_last_zip_path", "") or "")
    if zip_path:
        orders = getattr(window, "_preview_document_orders", None)
        if not isinstance(orders, dict):
            orders = {}
            window._preview_document_orders = orders
        orders[zip_path] = tuple(ordered_ids)
    apply_preview_export_state(window)


def apply_preview_export_state(window) -> None:
    zip_path = str(getattr(window, "_preview_last_zip_path", "") or "")
    document_list = getattr(window, "preview_document_list", None)
    items = dict(getattr(window, "preview_doc_items", {}) or {})
    pdf_map = dict(getattr(window, "_preview_pdf_map", {}) or {})
    errors = dict(getattr(window, "_preview_pdf_errors", {}) or {})
    manifest_errors = dict(getattr(window, "_preview_manifest_errors", {}) or {})
    passthrough_ids = frozenset(getattr(window, "_preview_passthrough_ids", ()) or ())
    documents = tuple(getattr(window, "_preview_documents", ()) or ())
    selected = window._preview_export_selections.get(zip_path)
    if not isinstance(selected, set):
        selected = {str(document.id) for document in documents if str(document.id) not in manifest_errors}
        if zip_path:
            window._preview_export_selections[zip_path] = selected

    any_selected_pdf = False
    codeset_notice = _codeset_notice()
    signal_blocker = QSignalBlocker(document_list) if document_list is not None else None
    try:
        for document_id, item in items.items():
            has_pdf = document_id in pdf_map
            is_selected = document_id in selected
            any_selected_pdf = any_selected_pdf or (has_pdf and is_selected)
            error_tooltip = ""
            is_attachment = document_id in passthrough_ids
            if has_pdf:
                status_text, status_tone = ("已并入", "info") if is_attachment else ("已渲染", "success")
            elif document_id in manifest_errors:
                status_text, status_tone = "无法生成", "error"
                error_tooltip = user_error_text(str(manifest_errors[document_id]))
            elif document_id in errors:
                status_text, status_tone = "渲染失败", "error"
                error_tooltip = user_error_text(str(errors[document_id]))
            elif is_attachment:
                status_text, status_tone = "待并入", "info"
            else:
                status_text, status_tone = "待生成", "pending"
            item.setData(_PREVIEW_STATUS_ROLE, status_text)
            item.setData(_PREVIEW_STATUS_TONE_ROLE, status_tone)
            item.setCheckState(Qt.Checked if is_selected else Qt.Unchecked)
            if document_id in manifest_errors:
                item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
            else:
                item.setFlags(item.flags() | Qt.ItemIsEnabled)
            document = next((candidate for candidate in documents if str(candidate.id) == document_id), None)
            base_tooltip = (
                f"{document.display_name}\n文件代码：{document.code or '未提供'}"
                if document is not None
                else document_id
            )
            if codeset_notice and document is not None and _is_request_form_document(document):
                error_tooltip = f"{error_tooltip}\n{codeset_notice}".strip()
            item.setToolTip(f"{base_tooltip}\n{error_tooltip}".rstrip())
    finally:
        del signal_blocker
    if document_list is not None:
        document_list.viewport().update()

    materialize_error = ""
    try:
        _materialize_preview_pdf(window)
    except (OSError, RuntimeError, ValueError) as exc:
        window._preview_merged_temp_pdf_path = ""
        materialize_error = str(exc)
    selected_ids = _selected_document_ids_in_display_order(window)
    pending_selected_ids = [document_id for document_id in selected_ids if document_id not in pdf_map]
    if hasattr(window, "preview_export_button"):
        window.preview_export_button.setEnabled(any_selected_pdf and not pending_selected_ids and not materialize_error)
        window.preview_export_button.setText("导出所选 PDF…" if get_pdf_preview_mode() == "legacy" else "另存预览 PDF…")
    if hasattr(window, "preview_start_button"):
        if not documents:
            window.preview_start_button.setText("解析文件清单")
        else:
            window.preview_start_button.setText("打开预览 PDF" if selected_ids and not pending_selected_ids else "生成并打开预览 PDF")
    if not documents:
        _set_preview_action_summary(window, "选择案件后先识别文件；无 list.xml 的四书 ZIP 也可预览。")
    elif not selected_ids:
        _set_preview_action_summary(window, "请至少勾选一份文件；可拖动左侧手柄调整合并顺序。")
    elif pending_selected_ids:
        _set_preview_action_summary(
            window,
            f"已选 {len(selected_ids)} 项，其中 {len(pending_selected_ids)} 项尚未生成 PDF；点击“生成并打开预览 PDF”。",
        )
    else:
        name = Path(getattr(window, "_preview_merged_temp_pdf_path", "")).name
        _set_preview_action_summary(window, f"已就绪：{name}。打开或另存直接使用此 PDF；调整勾选和顺序后无需重复渲染已完成的文件。")
    if materialize_error:
        _set_preview_action_summary(window, f"整理预览 PDF 失败：{materialize_error}")
    if get_pdf_preview_mode() == "legacy":
        if hasattr(window, "preview_start_button"):
            window.preview_start_button.setText("重新生成轻量预览" if pdf_map else "开始轻量预览")
        if pdf_map:
            _set_preview_action_summary(window, "浏览器预览已打开；下方只列出轻量服务支持的四书 PDF，可拖动调整本地合并和导出顺序。")
        else:
            _set_preview_action_summary(window, "轻量模式只处理 100001–100004 四书；点击按钮后会在默认浏览器打开官方预览。")


def on_preview_start_selected_case(window) -> None:
    if getattr(window, "_preview_in_progress", False):
        return
    cases = getattr(window, "_preview_cases", []) or []
    if not cases:
        show_blocking_alert_modal(window, "提示", "请先导入案卷 ZIP。", primary_text="关闭", secondary_text="关闭")
        return
    _parent, leaf = window._get_selected_preview_leaf()
    if not leaf:
        show_blocking_alert_modal(window, "提示", "请先选择一个案件（总包请展开后选择子 ZIP）。", primary_text="关闭", secondary_text="关闭")
        return
    zip_path = str(leaf.get("zip_path") or "")
    if not zip_path or not os.path.isfile(zip_path):
        show_blocking_alert_modal(window, "错误", "未找到该案件 ZIP 文件。", primary_text="关闭", secondary_text="关闭")
        return
    if get_pdf_preview_mode() == "legacy":
        prepare_legacy_preview_case(window, zip_path)
        preview_single_case(window, zip_path, mode="legacy")
        return
    if str(getattr(window, "_preview_last_zip_path", "") or "") != zip_path or not tuple(getattr(window, "_preview_documents", ()) or ()):
        reset_preview_export_ui(window)
        inspect_preview_case(window, zip_path)
        return

    document_ids = _selected_document_ids_in_display_order(window)
    if not document_ids:
        show_blocking_alert_modal(window, "提示", "请至少勾选一份可生成 PDF 的文件。", primary_text="关闭", secondary_text="关闭")
        return
    source_stat = Path(zip_path).stat()
    signature = (source_stat.st_size, source_stat.st_mtime_ns)
    if getattr(window, "_preview_source_signature", signature) != signature:
        reset_preview_export_ui(window)
        inspect_preview_case(window, zip_path)
        return
    pdf_map = getattr(window, "_preview_pdf_map", {})
    pending_ids = [document_id for document_id in document_ids if document_id not in pdf_map]
    if not pending_ids:
        try:
            preview_path = _materialize_preview_pdf(window)
            if preview_path:
                _open_preview_with_system_viewer(preview_path)
        except (OSError, RuntimeError, ValueError) as exc:
            show_blocking_alert_modal(window, "打开失败", str(exc), primary_text="关闭", secondary_text="关闭")
        return
    window._preview_pdf_errors = {}
    window._preview_merged_temp_pdf_path = ""
    apply_preview_export_state(window)
    preview_single_case(
        window,
        zip_path,
        documents=tuple(getattr(window, "_preview_documents", ()) or ()),
        selected_document_ids=tuple(pending_ids),
        mode="full",
    )


def on_preview_export_merged_pdf(window) -> None:
    if get_pdf_preview_mode() == "full":
        try:
            source_stat = Path(window._preview_last_zip_path).stat()
            signature = (source_stat.st_size, source_stat.st_mtime_ns)
            if getattr(window, "_preview_source_signature", signature) != signature:
                raise RuntimeError("案卷 ZIP 已发生变化，请点击生成预览，重新识别文件后再保存。")
            preview_path = _materialize_preview_pdf(window)
            if not preview_path:
                show_blocking_alert_modal(window, "提示", "请先生成全部勾选文件的 PDF，或取消勾选失败项。", primary_text="关闭", secondary_text="关闭")
                return
            destination, _ = QFileDialog.getSaveFileName(
                window, "另存预览 PDF", str(Path(_preview_source_details(window)[1]) / Path(preview_path).name), "PDF 文件 (*.pdf)",
            )
            if not destination:
                return
            if not destination.lower().endswith(".pdf"):
                destination += ".pdf"
            if Path(destination).resolve() != Path(preview_path).resolve():
                shutil.copyfile(preview_path, destination)
            message = f"预览 PDF 已保存到：{destination}"
            _set_preview_action_summary(window, message)
        except (OSError, RuntimeError, ValueError) as exc:
            show_blocking_alert_modal(window, "保存失败", str(exc), primary_text="关闭", secondary_text="关闭")
        return
    pdf_map = dict(getattr(window, "_preview_pdf_map", {}) or {})
    document_ids = _selected_document_ids_in_display_order(window, require_pdf=True)
    if not document_ids:
        show_blocking_alert_modal(window, "提示", "请至少勾选一份已渲染的 PDF。", primary_text="关闭", secondary_text="关闭")
        return
    zip_path = str(getattr(window, "_preview_last_zip_path", "") or "")
    base_name = sanitize_filename(Path(zip_path).stem) or "preview"
    initial_dir = str(Path(zip_path).parent) if zip_path else os.getcwd()
    destination, _ = QFileDialog.getSaveFileName(window, "保存合并 PDF", os.path.join(initial_dir, f"{base_name}_预览合并.pdf"), "PDF 文件 (*.pdf)")
    if not destination:
        return

    try:
        QApplication.setOverrideCursor(Qt.WaitCursor)
        if not _write_merged_pdf(destination, document_ids, pdf_map):
            raise RuntimeError("未能合并出有效内容。")
        exported_paths, errors = _export_selected_preview_pdfs(
            dest_path=destination,
            base_name=base_name,
            selected_document_ids=document_ids,
            pdf_map=pdf_map,
            labels_by_document_id=_document_labels(window),
        )
    except Exception as exc:
        show_blocking_alert_modal(window, "导出失败", f"合并 PDF 失败：{exc}", primary_text="关闭", secondary_text="关闭")
        return
    finally:
        QApplication.restoreOverrideCursor()

    message = f"合并 PDF 已保存到：\n{destination}\n\n已同时导出 {len(exported_paths)} 个单 PDF。"
    if errors:
        message += "\n\n以下单 PDF 导出失败：\n" + "\n".join(errors)
    show_blocking_alert_modal(window, "完成" if not errors else "部分完成", message, primary_text="关闭", secondary_text="关闭")


__all__ = [
    "_export_selected_preview_pdfs",
    "_open_preview_with_system_viewer",
    "apply_preview_mode_ui",
    "apply_preview_export_state",
    "on_preview_doc_check_toggled",
    "on_preview_documents_reordered",
    "on_preview_export_merged_pdf",
    "on_preview_manifest_completed",
    "on_preview_legacy_completed",
    "on_preview_render_completed",
    "on_preview_start_selected_case",
    "prepare_legacy_preview_case",
    "reset_preview_export_ui",
]
