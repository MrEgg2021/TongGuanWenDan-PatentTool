import os
import subprocess

from gui.dialog_utils import show_blocking_alert_modal


def collect_docx_from_items(paths, include_directories=True):
    valid_files = []
    ignored = []
    for raw in paths or []:
        if not isinstance(raw, str):
            continue
        path = os.path.normpath(raw.strip())
        if not path:
            continue
        if os.path.isdir(path):
            if not include_directories:
                ignored.append(f"{path}（不是文件）")
                continue
            collected = []
            try:
                for entry in os.listdir(path):
                    full = os.path.join(path, entry)
                    if (
                        os.path.isfile(full)
                        and entry.lower().endswith((".doc", ".docx"))
                        and not entry.startswith("~")
                    ):
                        collected.append(os.path.normpath(full))
            except Exception:
                ignored.append(f"{path}（无法读取）")
                continue
            if not collected:
                ignored.append(f"{path}（未找到 DOC/DOCX）")
            else:
                valid_files.extend(collected)
            continue
        if not os.path.isfile(path):
            ignored.append(f"{path}（不存在）")
            continue
        name = os.path.basename(path)
        if not name.lower().endswith((".doc", ".docx")):
            ignored.append(f"{name}（非 DOC/DOCX）")
            continue
        if name.startswith("~"):
            ignored.append(f"{name}（临时文件）")
            continue
        valid_files.append(path)
    return valid_files, ignored


def show_drop_ignored_message(window, title, ignored_items):
    if not ignored_items:
        return
    lines = "\n".join(f"- {text}" for text in ignored_items[:10])
    extra = "" if len(ignored_items) <= 10 else f"\n… 以及 {len(ignored_items) - 10} 个"
    show_blocking_alert_modal(window, str(title or "提示"), f"以下条目未添加：\n{lines}{extra}", primary_text="关闭", secondary_text="关闭")


def reveal_path_in_explorer(path: str) -> bool:
    target = os.path.normpath(str(path or "").strip())
    if not target or not os.path.exists(target):
        return False
    try:
        if os.name == "nt":
            if os.path.isdir(target):
                subprocess.Popen(["explorer", target])
            else:
                subprocess.Popen(["explorer", "/select,", target])
            return True
        os.startfile(target)
        return True
    except Exception:
        return False
