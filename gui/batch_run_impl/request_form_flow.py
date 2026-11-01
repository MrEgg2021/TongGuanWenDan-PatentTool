from __future__ import annotations

import os

from PySide6.QtWidgets import QDialog

from core.description_heading_probe import probe_description_patent_type_heading
from core.logging_utils import logger
from core.request_form import parse_request_info
from core.word_engine import WordComHijackedError
from gui.patent_type_dialogs import prompt_batch_patent_type_choices
from gui.section_resolution import (
    compute_effective_enabled_sections,
    compute_request_form_prefill_available,
    needs_patent_type,
    normalize_enabled_sections,
)
from gui.widgets import RequestFormDialog


def _extract_patent_type(request_info) -> str:
    if isinstance(request_info, dict):
        patent_type = request_info.get("patent_type")
        if patent_type in ("invention", "utility_model"):
            return patent_type
    return "invention"


def _build_effective_enabled_sections_map(window, target_files: list[str], enabled_sections: dict | None) -> dict[str, dict]:
    requested_enabled_sections = normalize_enabled_sections(enabled_sections)
    try:
        probe_map = getattr(window, "_batch_header_probe_map", None)
    except Exception:
        probe_map = None

    effective_map: dict[str, dict] = {}
    for file_path in target_files:
        probe = probe_map.get(file_path) if isinstance(probe_map, dict) else None
        effective_map[file_path] = compute_effective_enabled_sections(requested_enabled_sections, probe)

    try:
        if not hasattr(window, "_batch_effective_enabled_sections_map") or not isinstance(
            getattr(window, "_batch_effective_enabled_sections_map"),
            dict,
        ):
            window._batch_effective_enabled_sections_map = {}
        window._batch_effective_enabled_sections_map.update(effective_map)
    except Exception:
        pass
    return effective_map


def _build_request_form_prefill_available_map(window, target_files: list[str]) -> dict[str, bool | None]:
    try:
        probe_map = getattr(window, "_batch_header_probe_map", None)
    except Exception:
        probe_map = None

    availability_map: dict[str, bool | None] = {}
    for file_path in target_files:
        probe = probe_map.get(file_path) if isinstance(probe_map, dict) else None
        availability_map[file_path] = compute_request_form_prefill_available(probe)
    return availability_map


def _set_batch_patent_type(window, file_path: str, patent_type: str | None) -> None:
    if patent_type not in ("invention", "utility_model"):
        return
    try:
        window._batch_file_types[file_path] = patent_type
    except Exception:
        pass


def _build_request_form_setting(
    *,
    effective_enabled_sections: dict,
    request_form_prefill_available: bool | None,
    request_info,
    patent_type: str | None,
    source: str | None,
) -> dict:
    return {
        "patent_type": patent_type,
        "effective_patent_type": patent_type,
        "effective_patent_type_source": source,
        "request_info": request_info,
        "effective_enabled_sections": dict(effective_enabled_sections),
        "request_form_prefill_available": request_form_prefill_available,
    }


def collect_request_form_settings(window, target_files: list[str], config_path, enabled_sections: dict) -> dict[str, dict] | None:
    per_file_settings: dict[str, dict] = {}
    effective_sections_map = _build_effective_enabled_sections_map(window, target_files, enabled_sections)
    prefill_available_map = _build_request_form_prefill_available_map(window, target_files)

    confirm_req = True
    try:
        confirm_req = bool(window.batch_chk_confirm_req.isChecked())
    except Exception:
        confirm_req = True

    request_form_files = [file_path for file_path in target_files if effective_sections_map[file_path].get("request_form")]
    pre_parsed_info: dict[str, dict | None] = {}


    if request_form_files:
        total_cfg_files = len(request_form_files)
        for idx, file_path in enumerate(request_form_files):
            try:
                window.update_progress(
                    0,
                    "正在预解析申请信息…",
                    f"正在预解析第 {idx + 1}/{total_cfg_files} 个文件的“申请信息确认页”，请稍候…",
                )
            except Exception:
                pass

            try:
                pre_parsed_info[file_path] = parse_request_info(file_path, config_path=config_path)
            except WordComHijackedError:
                raise
            except Exception:
                pre_parsed_info[file_path] = None

    popup_request_form_files = list(request_form_files) if confirm_req else [
        file_path for file_path in request_form_files if prefill_available_map.get(file_path) is False
    ]

    if request_form_files and confirm_req:
        try:
            request_form_cache = getattr(window, "_request_form_cache", None)
        except Exception:
            request_form_cache = None
        if not isinstance(request_form_cache, dict):
            request_form_cache = {}
            try:
                window._request_form_cache = request_form_cache
            except Exception:
                pass

        idx = 0
        total_cfg_files = len(popup_request_form_files)
        while 0 <= idx < total_cfg_files:
            file_path = popup_request_form_files[idx]
            effective_enabled_sections = effective_sections_map[file_path]
            existing = per_file_settings.get(file_path)

            request_info = pre_parsed_info.get(file_path)
            base_patent_type = _extract_patent_type(request_info)
            if isinstance(existing, dict):
                request_info = existing.get("request_info")
                base_patent_type = existing.get("effective_patent_type") or existing.get("patent_type") or base_patent_type

            try:
                initial_request_info = window._build_request_form_initial_info(request_info, base_patent_type)
            except Exception:
                initial_request_info = None

            exec_embedded = getattr(window, "_exec_request_form_embedded", None)
            exec_path = "embedded" if callable(exec_embedded) else "dialog-fallback"
            logger.info(
                "[BATCH_REQ_FORM] file=%s name=%s index=%d/%d executor=%s",
                str(file_path),
                str(os.path.basename(file_path)),
                int(idx + 1),
                int(total_cfg_files),
                exec_path,
            )

            if callable(exec_embedded):
                def _configure(dlg):
                    try:
                        dlg.btn_ok.setText("确定（进入下一个）")
                        dlg.btn_cancel.setText("取消（终止批量）" if idx == 0 else "取消（回到上一个）")
                    except Exception:
                        pass

                dlg_result, confirmed_request_info, patent_type = exec_embedded(
                    initial_request_info=initial_request_info,
                    cache=request_form_cache,
                    cache_key=file_path,
                    source_file_path=file_path,
                    target_file_name=os.path.basename(file_path),
                    configure_fn=_configure,
                )
            else:
                dlg = RequestFormDialog(window)
                try:
                    ctx_fn = getattr(dlg, "set_cache_context", None)
                    if callable(ctx_fn):
                        ctx_fn(request_form_cache, file_path, source_file_path=file_path)
                except Exception:
                    pass
                try:
                    dlg.set_target_file_name(os.path.basename(file_path))
                except Exception:
                    pass
                try:
                    dlg.btn_ok.setText("确定（进入下一个）")
                    dlg.btn_cancel.setText("取消（终止批量）" if idx == 0 else "取消（回到上一个）")
                except Exception:
                    pass
                if initial_request_info is not None:
                    dlg.set_initial_data(initial_request_info)
                try:
                    dlg._id_validation_cn_enabled = bool(getattr(window, "_id_validation_cn_enabled", True))
                    dlg._id_validation_uscc_enabled = bool(getattr(window, "_id_validation_uscc_enabled", True))
                except Exception:
                    pass
                dlg_result = dlg.exec()
                confirmed_request_info = None
                patent_type = None
                if dlg_result == QDialog.Accepted:
                    try:
                        confirmed_request_info, patent_type = dlg.get_request_data()
                    except Exception:
                        confirmed_request_info, patent_type = None, None

            if dlg_result == QDialog.Accepted:
                logger.info(
                    "[BATCH_REQ_FORM] file=%s name=%s index=%d/%d result=accepted",
                    str(file_path),
                    str(os.path.basename(file_path)),
                    int(idx + 1),
                    int(total_cfg_files),
                )
                if not isinstance(confirmed_request_info, dict):
                    confirmed_request_info = {}
                effective_patent_type = patent_type if patent_type in ("invention", "utility_model") else base_patent_type
                per_file_settings[file_path] = _build_request_form_setting(
                    effective_enabled_sections=effective_enabled_sections,
                    request_form_prefill_available=prefill_available_map.get(file_path),
                    request_info=confirmed_request_info,
                    patent_type=effective_patent_type,
                    source="request_form",
                )
                _set_batch_patent_type(window, file_path, effective_patent_type)
                try:
                    window._set_current_file_label(file_path)
                except Exception:
                    pass
                idx += 1
                continue

            if idx == 0:
                logger.info(
                    "[BATCH_REQ_FORM] file=%s name=%s index=%d/%d result=rejected action=abort_batch reason=first_file_cancelled",
                    str(file_path),
                    str(os.path.basename(file_path)),
                    int(idx + 1),
                    int(total_cfg_files),
                )
                try:
                    window.update_progress(0, "批量处理已取消", "您已取消第一个文件的请求书设置，批量处理未开始。")
                    window.btn_run.setEnabled(True)
                except Exception:
                    pass
                return None

            logger.info(
                "[BATCH_REQ_FORM] file=%s name=%s index=%d/%d result=rejected action=step_back_to_previous",
                str(file_path),
                str(os.path.basename(file_path)),
                int(idx + 1),
                int(total_cfg_files),
            )
            idx -= 1

    elif request_form_files:
        for file_path in request_form_files:
            if file_path in popup_request_form_files:
                continue
            request_info = pre_parsed_info.get(file_path)
            effective_patent_type = _extract_patent_type(request_info)
            per_file_settings[file_path] = _build_request_form_setting(
                effective_enabled_sections=effective_sections_map[file_path],
                request_form_prefill_available=prefill_available_map.get(file_path),
                request_info=request_info if isinstance(request_info, dict) else None,
                patent_type=effective_patent_type,
                source="request_form",
            )
            _set_batch_patent_type(window, file_path, effective_patent_type)

        if popup_request_form_files:
            try:
                request_form_cache = getattr(window, "_request_form_cache", None)
            except Exception:
                request_form_cache = None
            if not isinstance(request_form_cache, dict):
                request_form_cache = {}
                try:
                    window._request_form_cache = request_form_cache
                except Exception:
                    pass

            idx = 0
            total_cfg_files = len(popup_request_form_files)
            while 0 <= idx < total_cfg_files:
                file_path = popup_request_form_files[idx]
                effective_enabled_sections = effective_sections_map[file_path]
                request_info = pre_parsed_info.get(file_path)
                base_patent_type = _extract_patent_type(request_info)

                try:
                    initial_request_info = window._build_request_form_initial_info(request_info, base_patent_type)
                except Exception:
                    initial_request_info = None

                exec_embedded = getattr(window, "_exec_request_form_embedded", None)
                exec_path = "embedded" if callable(exec_embedded) else "dialog-fallback"
                logger.info(
                    "[BATCH_REQ_FORM] file=%s name=%s index=%d/%d executor=%s force_popup_missing_confirm=true",
                    str(file_path),
                    str(os.path.basename(file_path)),
                    int(idx + 1),
                    int(total_cfg_files),
                    exec_path,
                )

                if callable(exec_embedded):
                    def _configure(dlg):
                        try:
                            dlg.btn_ok.setText("确定（进入下一个）")
                            dlg.btn_cancel.setText("取消（终止批量）" if idx == 0 else "取消（回到上一个）")
                        except Exception:
                            pass

                    dlg_result, confirmed_request_info, patent_type = exec_embedded(
                        initial_request_info=initial_request_info,
                        cache=request_form_cache,
                        cache_key=file_path,
                        source_file_path=file_path,
                        target_file_name=os.path.basename(file_path),
                        configure_fn=_configure,
                    )
                else:
                    dlg = RequestFormDialog(window)
                    try:
                        ctx_fn = getattr(dlg, "set_cache_context", None)
                        if callable(ctx_fn):
                            ctx_fn(request_form_cache, file_path, source_file_path=file_path)
                    except Exception:
                        pass
                    try:
                        dlg.set_target_file_name(os.path.basename(file_path))
                    except Exception:
                        pass
                    try:
                        dlg.btn_ok.setText("确定（进入下一个）")
                        dlg.btn_cancel.setText("取消（终止批量）" if idx == 0 else "取消（回到上一个）")
                    except Exception:
                        pass
                    if initial_request_info is not None:
                        dlg.set_initial_data(initial_request_info)
                    try:
                        dlg._id_validation_cn_enabled = bool(getattr(window, "_id_validation_cn_enabled", True))
                        dlg._id_validation_uscc_enabled = bool(getattr(window, "_id_validation_uscc_enabled", True))
                    except Exception:
                        pass
                    dlg_result = dlg.exec()
                    confirmed_request_info = None
                    patent_type = None
                    if dlg_result == QDialog.Accepted:
                        try:
                            confirmed_request_info, patent_type = dlg.get_request_data()
                        except Exception:
                            confirmed_request_info, patent_type = None, None

                if dlg_result == QDialog.Accepted:
                    if not isinstance(confirmed_request_info, dict):
                        confirmed_request_info = {}
                    effective_patent_type = patent_type if patent_type in ("invention", "utility_model") else base_patent_type
                    per_file_settings[file_path] = _build_request_form_setting(
                        effective_enabled_sections=effective_enabled_sections,
                        request_form_prefill_available=prefill_available_map.get(file_path),
                        request_info=confirmed_request_info,
                        patent_type=effective_patent_type,
                        source="request_form",
                    )
                    _set_batch_patent_type(window, file_path, effective_patent_type)
                    try:
                        window._set_current_file_label(file_path)
                    except Exception:
                        pass
                    idx += 1
                    continue

                if idx == 0:
                    logger.info(
                        "[BATCH_REQ_FORM] file=%s name=%s index=%d/%d result=rejected action=abort_batch reason=missing_confirm_force_popup_cancelled",
                        str(file_path),
                        str(os.path.basename(file_path)),
                        int(idx + 1),
                        int(total_cfg_files),
                    )
                    try:
                        window.update_progress(0, "批量处理已取消", "您已取消缺少确认页文件的请求书补填，批量处理未开始。")
                        window.btn_run.setEnabled(True)
                    except Exception:
                        pass
                    return None

                logger.info(
                    "[BATCH_REQ_FORM] file=%s name=%s index=%d/%d result=rejected action=step_back_to_previous force_popup_missing_confirm=true",
                    str(file_path),
                    str(os.path.basename(file_path)),
                    int(idx + 1),
                    int(total_cfg_files),
                )
                idx -= 1

    unresolved_files: list[str] = []
    for file_path in target_files:
        if file_path in per_file_settings:
            continue

        effective_enabled_sections = effective_sections_map[file_path]
        if not needs_patent_type(effective_enabled_sections):
            per_file_settings[file_path] = _build_request_form_setting(
                effective_enabled_sections=effective_enabled_sections,
                request_form_prefill_available=prefill_available_map.get(file_path),
                request_info=None,
                patent_type=None,
                source=None,
            )
            continue

        try:
            probe = probe_description_patent_type_heading(file_path, config_path=config_path)
        except WordComHijackedError:
            raise
        except Exception:
            probe = {"patent_type": None, "matched_heading": None}

        effective_patent_type = None
        if isinstance(probe, dict):
            patent_type = probe.get("patent_type")
            if patent_type in ("invention", "utility_model"):
                effective_patent_type = patent_type

        if effective_patent_type in ("invention", "utility_model"):
            per_file_settings[file_path] = _build_request_form_setting(
                effective_enabled_sections=effective_enabled_sections,
                request_form_prefill_available=prefill_available_map.get(file_path),
                request_info=None,
                patent_type=effective_patent_type,
                source="description_heading",
            )
            _set_batch_patent_type(window, file_path, effective_patent_type)
        else:
            unresolved_files.append(file_path)

    if unresolved_files:
        selections = prompt_batch_patent_type_choices(window, file_paths=unresolved_files)
        if not isinstance(selections, dict):
            logger.info("[BATCH_REQ_FORM] aborted reason=manual_patent_type_cancelled")
            return None
        for file_path in unresolved_files:
            selected_patent_type = selections.get(file_path)
            if selected_patent_type not in ("invention", "utility_model"):
                logger.info(
                    "[BATCH_REQ_FORM] aborted reason=manual_patent_type_missing file=%s",
                    str(file_path),
                )
                return None
            per_file_settings[file_path] = _build_request_form_setting(
                effective_enabled_sections=effective_sections_map[file_path],
                request_form_prefill_available=prefill_available_map.get(file_path),
                request_info=None,
                patent_type=selected_patent_type,
                source="manual_prompt",
            )
            _set_batch_patent_type(window, file_path, selected_patent_type)

    return per_file_settings


__all__ = ["collect_request_form_settings"]
