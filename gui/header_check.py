import os

from core.headers import probe_required_headers_with_meta
from core.word_engine import WordComHijackedError
from gui.dialog_utils import show_blocking_alert_modal
from gui.section_resolution import compute_effective_enabled_sections


def _offer_header_precheck_hint(window, input_path: str, detail: str) -> None:
    show_blocking_alert_modal(window, "提示", detail + "\n\n如需定位环境差异，可查看程序日志了解详情。")


def check_required_headers_single(window, input_path: str, config_path=None) -> bool:
    try:
        result, meta = probe_required_headers_with_meta(input_path, config_path=config_path)
    except WordComHijackedError:
        raise
    except Exception as e:
        msg = str(e)
        if "Document contains comments or tracked changes" in msg:
            detail = (
                "检测页眉时出错：文档包含批注或未接受的修订。\n\n"
                "请在 Word 中执行以下操作后重试：\n"
                "1）在“审阅”选项卡中选择“接受所有修订”；\n"
                "2）删除所有批注；\n"
                "3）保存为新的 DOC/DOCX 文件，再使用本工具转换。"
            )
        else:
            detail = f"检测页眉时出错：{msg}"
        _offer_header_precheck_hint(window, input_path, detail)
        return False

    try:
        window._last_header_probe_single = result
    except Exception:
        pass

    try:
        requested_enabled_sections = window.get_enabled_sections() if hasattr(window, "get_enabled_sections") else None
    except Exception:
        requested_enabled_sections = None
    try:
        window._last_single_effective_enabled_sections = compute_effective_enabled_sections(
            requested_enabled_sections,
            result,
        )
    except Exception:
        pass

    try:
        window._last_header_probe_single_meta = meta
    except Exception:
        pass

    # 若全部必需页眉均未检测到，则中止处理
    if not any(result.values()):
        show_blocking_alert_modal(
            window,
            "提示",
            "未检测到有效的页眉信息，请核对文件页眉格式或使用工具导出的模版文件进行转档。",
            primary_text="关闭",
            secondary_text="关闭",
        )
        window.update_progress(
            0,
            "页眉检测失败",
            "未检测到有效的页眉信息，已停止处理。",
        )
        return False

    mapping = [
        ("申请信息确认页", bool(result.get("request_meta"))),
        ("权利要求书", bool(result.get("claims"))),
        ("说明书", bool(result.get("description"))),
        ("说明书摘要", bool(result.get("abstract"))),
        ("说明书附图", bool(result.get("drawings"))),
    ]
    status_text = "页眉检测：" + "  ".join(
        f"{name}{'✅' if ok else '❌'}" for name, ok in mapping
    )
    lbl_batch = getattr(window, "batch_status_label", None)
    if lbl_batch is not None:
        try:
            lbl_batch.setText(status_text)
        except Exception:
            pass
        try:
            lbl_batch.setToolTip(
                status_text + f"（{os.path.basename(input_path)}）"
            )
        except Exception:
            pass
        try:
            lbl_batch.setVisible(True)
        except Exception:
            pass

    return True


def check_required_headers_batch(window, file_path: str, config_path=None) -> bool:
    try:
        result, meta = probe_required_headers_with_meta(file_path, config_path=config_path)
    except WordComHijackedError:
        raise
    except Exception as e:
        msg = str(e)
        prefix = f"检测文件 {os.path.basename(file_path)} 的页眉时出错："
        if "Document contains comments or tracked changes" in msg:
            detail = (
                prefix
                + "文档包含批注或未接受的修订。\n\n"
                "请在 Word 中执行以下操作后重试：\n"
                "1）在“审阅”选项卡中选择“接受所有修订”；\n"
                "2）删除所有批注；\n"
                "3）保存为新的 DOC/DOCX 文件，再使用本工具转换。"
            )
            short = f"{os.path.basename(file_path)}：文档包含批注或未接受的修订，请在 Word 中清理后重试。"
        else:
            detail = prefix + msg
            short = f"{os.path.basename(file_path)}：{msg}"
        show_blocking_alert_modal(window, "提示", detail, primary_text="关闭", secondary_text="关闭")
        # 在底部状态区持久显示当前文件和错误原因，并重置进度
        window.update_progress(
            0,
            "批量处理已终止",
            short,
            batch_info=f"❌ 批量处理中断：{short}",
        )
        return False

    try:
        if not hasattr(window, "_batch_header_probe_map") or not isinstance(getattr(window, "_batch_header_probe_map"), dict):
            window._batch_header_probe_map = {}
        window._batch_header_probe_map[file_path] = result
    except Exception:
        pass

    try:
        requested_enabled_sections = window.get_enabled_sections() if hasattr(window, "get_enabled_sections") else None
    except Exception:
        requested_enabled_sections = None
    try:
        if not hasattr(window, "_batch_effective_enabled_sections_map") or not isinstance(
            getattr(window, "_batch_effective_enabled_sections_map"),
            dict,
        ):
            window._batch_effective_enabled_sections_map = {}
        window._batch_effective_enabled_sections_map[file_path] = compute_effective_enabled_sections(
            requested_enabled_sections,
            result,
        )
    except Exception:
        pass

    try:
        if not hasattr(window, "_batch_doc_meta_map") or not isinstance(getattr(window, "_batch_doc_meta_map"), dict):
            window._batch_doc_meta_map = {}
        window._batch_doc_meta_map[file_path] = meta
    except Exception:
        pass

    # 若全部必需页眉均未检测到，标记失败但不中止后续文件
    if not any(result.values()):
        if not hasattr(window, "_batch_header_empty_files"):
            window._batch_header_empty_files = []
        window._batch_header_empty_files.append(file_path)
        status_text = (
            "页眉检测：未检测到有效的页眉信息，已标记失败，将继续处理其他文件。"
            + f"（{os.path.basename(file_path)}）"
        )
        window.update_progress(
            0,
            "页眉检测结果：缺失必要页眉",
            status_text,
            batch_info=status_text,
        )
        return True

    mapping = [
        ("申请信息确认页", bool(result.get("request_meta"))),
        ("权利要求书", bool(result.get("claims"))),
        ("说明书", bool(result.get("description"))),
        ("说明书摘要", bool(result.get("abstract"))),
        ("说明书附图", bool(result.get("drawings"))),
    ]
    base_name = os.path.basename(file_path)
    status_core = "页眉检测：" + "  ".join(
        f"{name}{'✅' if ok else '❌'}" for name, ok in mapping
    )
    has_missing = any((not ok) for _, ok in mapping)
    status_text = status_core + (f"（{base_name}）" if has_missing else "")
    lbl_batch = getattr(window, "batch_status_label", None)
    if lbl_batch is not None:
        try:
            lbl_batch.setText(status_text)
        except Exception:
            pass
        try:
            lbl_batch.setToolTip(
                status_core + f"（{base_name}）"
            )
        except Exception:
            pass
        try:
            lbl_batch.setVisible(True)
        except Exception:
            pass

    # 页眉缺失不再导致批量中止，仅作提示，是否生成对应文书由后续五书勾选和解析结果决定
    return True
