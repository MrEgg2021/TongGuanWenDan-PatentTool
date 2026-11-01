import os
import shutil
import tempfile


def ensure_preview_temp_root(window) -> str:
    """确保预览导入用的临时目录存在，并返回目录路径。"""
    root = None
    try:
        root = getattr(window, "_preview_temp_root", None)
    except Exception:
        root = None
    if not root or not os.path.isdir(str(root)):
        root = tempfile.mkdtemp(prefix="preview_cases_")
        try:
            window._preview_temp_root = root
        except Exception:
            pass
    return str(root)


def cleanup_preview_temp(window) -> None:
    """清理预览导入时产生的临时文件与临时目录。"""
    try:
        for p in list(getattr(window, "_preview_temp_files", []) or []):
            try:
                if p and os.path.isfile(p):
                    os.remove(p)
            except Exception:
                pass
    except Exception:
        pass

    try:
        root = getattr(window, "_preview_temp_root", None)
        if root and os.path.isdir(str(root)):
            shutil.rmtree(str(root), ignore_errors=True)
    except Exception:
        pass

    try:
        window._preview_temp_files = []
        window._preview_temp_root = None
    except Exception:
        pass
