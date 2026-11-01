from __future__ import annotations

from core.office_process_safety import (
    OfficeProcessInfo,
    blocking_office_processes,
    hidden_background_document_hosts,
    terminate_office_processes,
)
from core.logging_utils import logger
from core.word_engine import terminate_owned_office_processes
from gui.dialog_utils import ask_continue_cancel, show_blocking_alert_modal


def _format_process_lines(items: list[OfficeProcessInfo]) -> str:
    lines = [item.display_line() for item in list(items or [])]
    return "\n".join(lines)


def _set_killed_flag(window, killed: bool) -> None:
    if not killed:
        return
    try:
        setattr(window, "_office_process_guard_killed", True)
    except Exception:
        pass


def _cleanup_hidden_office_processes(
    window,
    *,
    context: str,
) -> bool:
    hidden = hidden_background_document_hosts()
    if not hidden:
        try:
            logger.info("[OFFICE_CLEANUP] skipped context=%r hidden=0", context)
        except Exception:
            pass
        return True

    try:
        logger.info(
            "[OFFICE_CLEANUP] advanced_confirm_prompt context=%r hidden=%d items=%r",
            context,
            len(hidden),
            _format_process_lines(hidden),
        )
    except Exception:
        pass
    if not ask_continue_cancel(
        window,
        "高级清理后台进程",
        "工具将尝试关闭看不见的 Word/WPS 后台程序，然后重新检测。\n\n"
        "继续前请确认：重要文档已经保存，Word/WPS 中没有正在编辑的内容。"
        "清理后，Word/WPS 下次打开时可能会提示恢复文档。",
        continue_text="已保存，开始清理",
        cancel_text="取消",
        default_continue=False,
        icon=None,
    ):
        try:
            logger.info("[OFFICE_CLEANUP] advanced_cleanup_rejected context=%r hidden=%d", context, len(hidden))
        except Exception:
            pass
        return False

    try:
        logger.info(
            "[OFFICE_CLEANUP] start context=%r hidden=%d items=%r",
            context,
            len(hidden),
            _format_process_lines(hidden),
        )
    except Exception:
        pass
    first_result = terminate_office_processes(hidden, allow_kill=False)
    try:
        logger.info(
            "[OFFICE_CLEANUP] normal_terminate context=%r terminated=%r killed=%r remaining=%d errors=%r",
            context,
            first_result.terminated,
            first_result.killed,
            len(first_result.remaining),
            first_result.errors,
        )
    except Exception:
        pass
    remaining = hidden_background_document_hosts()
    if not remaining:
        try:
            logger.info("[OFFICE_CLEANUP] normal_terminate_cleared context=%r", context)
        except Exception:
            pass
        return True

    try:
        logger.info(
            "[OFFICE_CLEANUP] hard_kill_prompt context=%r remaining=%d items=%r",
            context,
            len(remaining),
            _format_process_lines(remaining),
        )
    except Exception:
        pass
    if not ask_continue_cancel(
        window,
        "后台进程清理",
        "部分 Word/WPS 后台程序没有正常关闭。\n\n"
        "如果你已确认没有重要文档正在编辑，可以继续结束这些后台程序；"
        "否则请取消，然后手动关闭 Word/WPS 或重启 Windows。",
        continue_text="继续结束后台程序",
        cancel_text="取消",
        default_continue=False,
        icon=None,
    ):
        show_blocking_alert_modal(
            window,
            "Word 启动检查未通过",
            "已取消强制结束。请重启 Windows，或手动关闭后台 Office/WPS 进程后重新检测或转换。",
            primary_text="关闭",
            secondary_text="关闭",
        )
        try:
            logger.info("[OFFICE_CLEANUP] hard_kill_rejected context=%r remaining=%d", context, len(remaining))
        except Exception:
            pass
        return False

    kill_result = terminate_office_processes(remaining, allow_kill=True)
    _set_killed_flag(window, bool(kill_result.killed))
    try:
        logger.info(
            "[OFFICE_CLEANUP] hard_kill_result context=%r terminated=%r killed=%r remaining=%d errors=%r",
            context,
            kill_result.terminated,
            kill_result.killed,
            len(kill_result.remaining),
            kill_result.errors,
        )
    except Exception:
        pass
    remaining_after_kill = hidden_background_document_hosts()
    if not remaining_after_kill:
        return True

    show_blocking_alert_modal(
        window,
        "后台进程仍未结束",
        "强制结束后仍检测到后台 Office/WPS 进程。请重启 Windows 后重新检测或转换。",
        primary_text="关闭",
        secondary_text="关闭",
    )
    return False


def advanced_cleanup_hidden_office_processes(window, *, context: str = "advanced_cleanup") -> bool:
    return _cleanup_hidden_office_processes(window, context=context)


def _prompt_hidden_background_hosts(window, hidden: list[OfficeProcessInfo], *, context: str) -> str:
    try:
        logger.info(
            "[OFFICE_GUARD] hidden_hosts context=%r hidden=%d items=%r",
            context,
            len(hidden),
            _format_process_lines(hidden),
        )
    except Exception:
        pass
    detail = _format_process_lines(hidden)
    message = (
        "检测到 Word/WPS 还有后台程序在运行，可能会影响后续检测或转换。"
        "请先保存并关闭 Word/WPS 文档，然后点击重新检测；如果仍然提示，可以重启 Windows 后再试。\n\n"
        "如果你已经确认没有正在编辑的重要文档，也可以让工具尝试清理这些后台程序。"
        "这个功能一般只在反复检测不过时使用。"
    )
    if detail.strip():
        message = message + "\n\n检测到的进程：\n" + detail
    choice = show_blocking_alert_modal(
        window,
        "后台 Office/WPS 进程",
        message,
        primary_text="重新检测",
        secondary_text="取消",
        tertiary_text="尝试清理后台程序...",
        close_result="secondary",
    )
    if choice == "primary":
        try:
            logger.info("[OFFICE_GUARD] hidden_retry context=%r hidden=%d", context, len(hidden))
        except Exception:
            pass
        return "retry"
    if choice == "tertiary":
        try:
            logger.info("[OFFICE_GUARD] hidden_advanced_cleanup_selected context=%r hidden=%d", context, len(hidden))
        except Exception:
            pass
        return "advanced_cleanup"
    else:
        try:
            logger.info("[OFFICE_GUARD] hidden_block_cancelled context=%r hidden=%d", context, len(hidden))
        except Exception:
            pass
        return "cancel"


def ensure_office_processes_ready(window, *, context: str = "conversion_start") -> bool:
    try:
        terminate_owned_office_processes(allow_kill=False)
    except Exception:
        pass

    while True:
        found = blocking_office_processes()
        if found:
            try:
                logger.info(
                    "[OFFICE_GUARD] visible_hosts context=%r visible=%d items=%r",
                    context,
                    len(found),
                    _format_process_lines(found),
                )
            except Exception:
                pass
            text = "检测到仍有 Word/WPS 文档窗口打开。请先保存并关闭相关文档，然后重新检测。"
            if not ask_continue_cancel(
                window,
                "Word/WPS 文档仍在打开",
                text,
                continue_text="重新检测",
                cancel_text="取消",
                icon=None,
            ):
                return False
            continue

        hidden = hidden_background_document_hosts()
        if not hidden:
            return True

        action = _prompt_hidden_background_hosts(window, hidden, context=context)
        if action == "retry":
            continue
        if action == "advanced_cleanup":
            if advanced_cleanup_hidden_office_processes(window, context=context):
                continue
            return False
        return False


__all__ = [
    "advanced_cleanup_hidden_office_processes",
    "ensure_office_processes_ready",
]
