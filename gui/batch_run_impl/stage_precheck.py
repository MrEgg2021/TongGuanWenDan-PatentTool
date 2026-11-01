
from gui.dialog_utils import ask_continue_cancel, show_blocking_alert_modal
from core.word_engine import WordComHijackedError


def precheck_headers(window, target_files: list[str], config_path=None, *, _in_fallback: bool = False) -> str:
    total_files = len(target_files)
    for idx, file_path in enumerate(target_files):
        window._set_current_file_label(file_path)
        try:
            window._header_precheck_stage = f"步骤 1/2：检查环境 ({idx + 1}/{total_files})"
            window._header_precheck_summary = ""
        except Exception:
            pass
        # 步骤 1/2：检查环境 + 清理残留 Word 进程（批量第 i/N 个文件）
        window.update_progress(
            0,
            "正在预检查页眉...",
            f"步骤 1/2：正在后台检查运行环境并清理残留 Word 进程 ({idx + 1}/{total_files})，请稍候...",
        )
        try:
            try:
                window._header_precheck_stage = f"步骤 2/2：页眉扫描 ({idx + 1}/{total_files})"
            except Exception:
                pass
            if not window._check_required_headers_batch(file_path, config_path=config_path):
                return "cancel"
        except WordComHijackedError as e:
            if _in_fallback:
                lbl_status = getattr(window, "status_label", None)
                if lbl_status is not None:
                    try:
                        lbl_status.setText("状态：批量处理失败")
                    except Exception:
                        pass
                show_blocking_alert_modal(window, "错误", str(e) or "无法正常连接或操作 Microsoft Word。", primary_text="关闭", secondary_text="关闭")
                return "cancel"

            msg = str(e).strip() or "无法正常连接或操作 Microsoft Word。"

            if not ask_continue_cancel(
                window,
                "Word 环境异常",
                msg,
                continue_text="我已修改/重试",
                cancel_text="取消",
                default_continue=True,
            ):
                lbl_status = getattr(window, "status_label", None)
                if lbl_status is not None:
                    try:
                        lbl_status.setText("状态：已取消")
                    except Exception:
                        pass
                return "cancel"

            lbl_status = getattr(window, "status_label", None)
            if lbl_status is not None:
                try:
                    lbl_status.setText("状态：正在重试")
                except Exception:
                    pass
            return "retry"

        try:
            probe_map = getattr(window, "_batch_header_probe_map", None)
            probe = probe_map.get(file_path) if isinstance(probe_map, dict) else None
            if isinstance(probe, dict):
                mapping = [
                    ("申请信息确认页", bool(probe.get("request_meta"))),
                    ("权利要求书", bool(probe.get("claims"))),
                    ("说明书", bool(probe.get("description"))),
                    ("说明书摘要", bool(probe.get("abstract"))),
                    ("说明书附图", bool(probe.get("drawings"))),
                ]
                window._header_precheck_summary = "页眉检测：" + "  ".join(
                    f"{name}{'✅' if ok else '❌'}" for name, ok in mapping
                )
        except Exception:
            pass
        try:
            window._header_precheck_stage = f"步骤 2/2：结果分析 ({idx + 1}/{total_files})"
        except Exception:
            pass
        # 步骤 2/2：页眉扫描已完成，正在分析结果
        window.update_progress(
            0,
            "正在预检查页眉...",
            f"步骤 2/2：已在后台完成页眉扫描，正在分析章节结构和必需页眉结果 ({idx + 1}/{total_files})...",
        )

    try:
        window._header_precheck_stage = "预检查完成"
    except Exception:
        pass
    return "ok"


__all__ = ["precheck_headers"]
