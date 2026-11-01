from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any

from PySide6.QtWidgets import QDialog

from core.description_heading_probe import probe_description_patent_type_heading
from core.logging_utils import logger
from core.request_form import parse_request_info
from core.word_engine import WordComHijackedError
from gui.dialog_utils import ask_continue_cancel, show_blocking_alert_modal
from gui.office_process_guard import ensure_office_processes_ready
from gui.patent_type_dialogs import prompt_single_patent_type_choice
from gui.section_resolution import (
    compute_effective_enabled_sections,
    compute_request_form_prefill_available,
    needs_patent_type,
    normalize_enabled_sections,
)
from gui.widgets import RequestFormDialog


@dataclass(frozen=True)
class SingleRunContext:
    request_info: Any
    confirmed_request_info: Any
    base_patent_type: Any
    patent_type: Any
    effective_patent_type: Any
    effective_patent_type_source: Any
    requested_enabled_sections: dict
    effective_enabled_sections: dict
    request_form_prefill_available: Any
    enabled_sections: dict
    desc_split_mode: Any


def _ensure_office_closed_for_request_form(window) -> bool:
    return ensure_office_processes_ready(window, context="request_form_preflight")


def prevalidate_single(
    window,
    input_path: str,
    enabled_sections: dict,
    request_info,
) -> bool:
    requested_enabled_sections = normalize_enabled_sections(enabled_sections)
    if not any(bool(v) for v in requested_enabled_sections.values()):
        show_blocking_alert_modal(
            window,
            "提示",
            "请至少勾选一项需要生成的文书（五书/请求书）。",
            primary_text="关闭",
            secondary_text="关闭",
        )
        return False

    try:
        probe = getattr(window, "_last_header_probe_single", None)
    except Exception:
        probe = None

    try:
        meta = getattr(window, "_last_header_probe_single_meta", None)
    except Exception:
        meta = None

    effective_enabled_sections = compute_effective_enabled_sections(requested_enabled_sections, probe)

    warnings: list[str] = []
    if isinstance(probe, dict):
        if requested_enabled_sections.get("request_form") and not bool(probe.get("request_meta")):
            warnings.append("已勾选“请求书”，但未检测到“申请信息确认页”页眉；本次不会忽略请求书，稍后将打开请求书弹窗供您手工补填。")

        for key, label in (
            ("claims", "权利要求书"),
            ("description", "说明书"),
            ("abstract", "说明书摘要"),
            ("drawings", "说明书附图"),
        ):
            if requested_enabled_sections.get(key) and not bool(probe.get(key)):
                warnings.append(f"已勾选“{label}”，但页眉检测未识别到该章节，本次将忽略该章节，不参与转换。")

    if isinstance(meta, dict):
        try:
            if meta.get("source_writable") is False:
                warnings.append("源文件可能为只读或当前目录无写权限，建议复制到可写目录后再转换，避免后续操作受限。")
        except Exception:
            pass

        try:
            if meta.get("protected") is True:
                ptype = meta.get("protection_type")
                warnings.append(
                    f"文档处于保护/限制编辑状态（ProtectionType={ptype}），可能导致部分解析或处理失败，建议先取消保护后再转换。"
                )
        except Exception:
            pass

        try:
            protection_check_error = meta.get("protection_check_error")
            if protection_check_error:
                warnings.append(
                    f"未能检测文档保护状态：{protection_check_error}，建议先在 Word 中确认文档是否处于受保护状态。"
                )
        except Exception:
            pass

    title_val = None
    try:
        if isinstance(request_info, dict):
            title_val = str(request_info.get("title") or "").strip() or None
    except Exception:
        title_val = None

    if effective_enabled_sections.get("request_form") and not title_val:
        warnings.append("未解析到可靠的“专利名称”，请在请求书弹窗中核对/填写，否则文件名与请求书内容可能不准确。")

    if warnings:
        deduped: list[str] = []
        seen: set[str] = set()
        for warning in warnings:
            if warning in seen:
                continue
            seen.add(warning)
            deduped.append(warning)
        warnings = deduped

    if not warnings:
        return True

    msg = "转换前校验：检测到以下需要您知晓的信息：\n\n" + "\n".join(f"- {w}" for w in warnings[:10])
    if len(warnings) > 10:
        msg += f"\n... 还有 {len(warnings) - 10} 条提示"
    msg += "\n\n是否继续？"
    return ask_continue_cancel(window, "转换前校验", msg)


def prepare_single_run_context(window, input_path: str, config_path=None) -> SingleRunContext | None:
    try:
        requested_enabled_sections = window.get_enabled_sections() if hasattr(window, "get_enabled_sections") else None
    except Exception:
        requested_enabled_sections = None
    requested_enabled_sections = normalize_enabled_sections(requested_enabled_sections)

    try:
        header_probe = getattr(window, "_last_header_probe_single", None)
    except Exception:
        header_probe = None
    effective_enabled_sections = compute_effective_enabled_sections(requested_enabled_sections, header_probe)
    request_form_prefill_available = compute_request_form_prefill_available(header_probe)

    request_form_enabled = bool(effective_enabled_sections.get("request_form"))
    need_patent_type = needs_patent_type(effective_enabled_sections)


    try:
        window._last_request_info = None
    except Exception:
        pass

    request_info = None
    if request_form_enabled:
        try:
            request_info = parse_request_info(input_path, config_path=config_path)
            try:
                window._last_request_info = request_info
            except Exception:
                pass
        except WordComHijackedError:
            raise
        except Exception:
            request_info = None
            try:
                window._last_request_info = None
            except Exception:
                pass

    base_patent_type = "invention"
    if request_form_enabled and isinstance(request_info, dict):
        request_form_patent_type = request_info.get("patent_type")
        if request_form_patent_type in ("invention", "utility_model"):
            base_patent_type = request_form_patent_type
    if request_form_enabled and request_form_prefill_available is False and base_patent_type not in ("invention", "utility_model"):
        base_patent_type = "invention"
    if request_form_enabled and request_form_prefill_available is False:
        try:
            type_probe = probe_description_patent_type_heading(input_path, config_path=config_path)
        except WordComHijackedError:
            raise
        except Exception:
            type_probe = {"patent_type": None, "matched_heading": None}
        if isinstance(type_probe, dict):
            probed_patent_type = type_probe.get("patent_type")
            if probed_patent_type in ("invention", "utility_model"):
                base_patent_type = probed_patent_type

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

    cached_form = request_form_cache.get(input_path)

    desc_split_mode = None
    try:
        if hasattr(window, "get_description_paragraph_split_mode"):
            desc_split_mode = window.get_description_paragraph_split_mode()
    except Exception:
        desc_split_mode = None

    if not prevalidate_single(window, input_path, requested_enabled_sections, request_info):
        logger.info("[SINGLE_PREFLIGHT] aborted reason=prevalidate_rejected file=%s", str(input_path))
        return None

    confirmed_request_info = request_info
    patent_type = base_patent_type
    effective_patent_type = None
    effective_patent_type_source = None

    if request_form_enabled:
        initial_source_info = request_info
        initial_patent_type = base_patent_type
        if isinstance(cached_form, dict):
            cached_confirmed = cached_form.get("confirmed_request_info")
            if isinstance(cached_confirmed, dict):
                initial_source_info = cached_confirmed
            cached_patent_type = cached_form.get("patent_type")
            if cached_patent_type in ("invention", "utility_model"):
                initial_patent_type = cached_patent_type
                base_patent_type = cached_patent_type

        initial_request_info = window._build_request_form_initial_info(initial_source_info, initial_patent_type)
        exec_embedded = getattr(window, "_exec_request_form_embedded", None)
        exec_path = "embedded" if callable(exec_embedded) else "dialog-fallback"
        logger.info(
            "[SINGLE_PREFLIGHT] request_form_executor path=%s file=%s",
            exec_path,
            str(input_path),
        )

        if callable(exec_embedded):
            dlg_result, confirmed_request_info, patent_type = exec_embedded(
                initial_request_info=initial_request_info,
                cache=request_form_cache,
                cache_key=input_path,
                source_file_path=input_path,
                target_file_name=os.path.basename(input_path),
            )
            if int(dlg_result) != int(QDialog.Accepted):
                logger.info("[SINGLE_PREFLIGHT] aborted reason=embedded_executor_rejected file=%s", str(input_path))
                return None
        else:
            dlg = RequestFormDialog(window)
            try:
                ctx_fn = getattr(dlg, "set_cache_context", None)
                if callable(ctx_fn):
                    ctx_fn(request_form_cache, input_path, source_file_path=input_path)
            except Exception:
                pass
            dlg.set_initial_data(initial_request_info)
            try:
                dlg._id_validation_cn_enabled = bool(getattr(window, "_id_validation_cn_enabled", True))
                dlg._id_validation_uscc_enabled = bool(getattr(window, "_id_validation_uscc_enabled", True))
            except Exception:
                pass
            if dlg.exec() != QDialog.Accepted:
                logger.info("[SINGLE_PREFLIGHT] aborted reason=request_form_dialog_rejected file=%s", str(input_path))
                return None
            confirmed_request_info, patent_type = dlg.get_request_data()

        if not _ensure_office_closed_for_request_form(window):
            logger.info("[SINGLE_PREFLIGHT] aborted reason=office_not_closed_after_prompt file=%s", str(input_path))
            return None

        try:
            request_form_cache[input_path] = {
                "confirmed_request_info": confirmed_request_info,
                "patent_type": patent_type or base_patent_type,
                "request_info": request_info,
            }
        except Exception:
            pass

        effective_patent_type = patent_type or base_patent_type
        effective_patent_type_source = "request_form"
        patent_type = effective_patent_type
    else:
        confirmed_request_info = None
        if need_patent_type:
            probe = {"patent_type": None, "matched_heading": None}
            try:
                probe = probe_description_patent_type_heading(input_path, config_path=config_path)
            except WordComHijackedError:
                raise
            except Exception:
                probe = {"patent_type": None, "matched_heading": None}

            probed_patent_type = None
            if isinstance(probe, dict):
                ptype = probe.get("patent_type")
                if ptype in ("invention", "utility_model"):
                    probed_patent_type = ptype

            if probed_patent_type in ("invention", "utility_model"):
                effective_patent_type = probed_patent_type
                effective_patent_type_source = "description_heading"
            else:
                selected_patent_type = prompt_single_patent_type_choice(window, file_path=input_path)
                if selected_patent_type not in ("invention", "utility_model"):
                    logger.info("[SINGLE_PREFLIGHT] aborted reason=manual_patent_type_cancelled file=%s", str(input_path))
                    return None
                effective_patent_type = selected_patent_type
                effective_patent_type_source = "manual_prompt"
            patent_type = effective_patent_type
        else:
            patent_type = None
            effective_patent_type = None
            effective_patent_type_source = None

    return SingleRunContext(
        request_info=request_info,
        confirmed_request_info=confirmed_request_info,
        base_patent_type=base_patent_type,
        patent_type=patent_type,
        effective_patent_type=effective_patent_type,
        effective_patent_type_source=effective_patent_type_source,
        requested_enabled_sections=requested_enabled_sections,
        effective_enabled_sections=effective_enabled_sections,
        request_form_prefill_available=request_form_prefill_available,
        enabled_sections=effective_enabled_sections,
        desc_split_mode=desc_split_mode,
    )
