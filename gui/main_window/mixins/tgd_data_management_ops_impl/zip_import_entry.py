import os

from PySide6.QtWidgets import QFileDialog

from gui.dialog_utils import show_blocking_alert_modal

from .output_dir import _ensure_output_dir
from .zip_import_batch import _process_request_zip_paths


def _normalize_zip_candidates(paths) -> list[str]:
    if not paths:
        return []
    out: list[str] = []
    for p in list(paths) if isinstance(paths, (list, tuple)) else [paths]:
        if not p:
            continue
        try:
            fp = str(p)
        except Exception:
            continue
        if not fp:
            continue
        if os.path.isdir(fp):
            continue
        if not fp.lower().endswith(".zip"):
            continue
        if not os.path.isfile(fp):
            continue
        out.append(fp)
    return out


def _collect_zip_files_recursively(root_dir: str) -> list[str]:
    if not root_dir:
        return []
    if not os.path.isdir(root_dir):
        return []
    out: list[str] = []
    try:
        for base, _dirs, files in os.walk(root_dir):
            for fn in files:
                if not fn:
                    continue
                if not str(fn).lower().endswith(".zip"):
                    continue
                fp = os.path.join(base, fn)
                if os.path.isfile(fp):
                    out.append(fp)
    except Exception:
        return []
    return out


def _get_confirm_each_enabled(window) -> bool:
    try:
        chk = getattr(window, "tgd_request_zip_confirm_each_checkbox", None)
        if chk is not None:
            return bool(chk.isChecked())
    except Exception:
        pass
    return True


def _get_parse_poa_enabled(window) -> bool:
    try:
        chk = getattr(window, "tgd_request_zip_parse_poa_checkbox", None)
        if chk is not None:
            return bool(chk.isChecked())
    except Exception:
        pass
    return False


def on_tgd_request_zip_import(window) -> None:
    default_dir = _ensure_output_dir()
    src_paths, _ = QFileDialog.getOpenFileNames(
        window,
        "导入案卷 ZIP（请求书）",
        default_dir,
        "ZIP 文件 (*.zip)",
    )
    if not src_paths:
        return
    on_tgd_request_zips_dropped(window, src_paths)


def on_tgd_request_zip_folder_import(window) -> None:
    default_dir = _ensure_output_dir()
    folder = ""
    try:
        folder = QFileDialog.getExistingDirectory(window, "选择包含案卷 ZIP 的文件夹", default_dir)
    except Exception:
        folder = ""
    if not folder:
        return

    zip_paths = _collect_zip_files_recursively(folder)
    if not zip_paths:
        show_blocking_alert_modal(window, "提示", "所选文件夹内未找到 ZIP 文件。", primary_text="关闭", secondary_text="关闭")
        return
    on_tgd_request_zips_dropped(window, zip_paths)


def on_tgd_request_zips_dropped(window, paths) -> None:
    zip_paths: list[str] = []
    for p in list(paths) if isinstance(paths, (list, tuple)) else [paths]:
        if not p:
            continue
        try:
            fp = str(p)
        except Exception:
            continue
        if not fp:
            continue
        if os.path.isdir(fp):
            zip_paths.extend(_collect_zip_files_recursively(fp))
            continue
        zip_paths.extend(_normalize_zip_candidates([fp]))

    uniq: list[str] = []
    seen: set[str] = set()
    for z in zip_paths:
        if z in seen:
            continue
        seen.add(z)
        uniq.append(z)

    confirm_each = _get_confirm_each_enabled(window)
    parse_poa = _get_parse_poa_enabled(window)
    _process_request_zip_paths(window, uniq, confirm_each=confirm_each, parse_poa=parse_poa)
