import os
import zipfile

from core.config import sanitize_filename

from gui.main_window.mixins.preview_temp import ensure_preview_temp_root


def iter_preview_leaf_cases(window):
    """遍历所有可预览的叶子案件（bundle 的子 ZIP + 单案件 ZIP）。"""
    for top in getattr(window, "_preview_cases", []) or []:
        if not isinstance(top, dict):
            continue
        if str(top.get("kind") or "") == "bundle":
            for ch in top.get("children") or []:
                if isinstance(ch, dict) and ch.get("zip_path"):
                    yield top, ch
        else:
            if top.get("zip_path"):
                yield None, top


def get_preview_leaf_by_zip_path(window, zip_path: str | None) -> tuple[dict | None, dict | None]:
    """根据 zip_path 查找对应的 (parent_bundle, leaf_case) 结构。"""
    if not zip_path:
        return None, None
    zp = str(zip_path or "")
    if not zp:
        return None, None
    for parent, leaf in iter_preview_leaf_cases(window):
        try:
            if str((leaf or {}).get("zip_path") or "") == zp:
                return parent, leaf
        except Exception:
            continue
    return None, None


def get_selected_preview_leaf(window) -> tuple[dict | None, dict | None]:
    """返回当前选中的案件叶子节点。"""
    try:
        zp = getattr(window, "_preview_selected_zip_path", None)
    except Exception:
        zp = None
    return get_preview_leaf_by_zip_path(window, zp)


def normalize_preview_zip_candidates(paths) -> list[str]:
    """将输入的路径集合规范为可导入的 zip 文件路径列表。"""
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


def build_preview_case_nodes_from_zip(window, zip_path: str) -> dict | None:
    """将一个 ZIP 解析成预览案件节点（bundle 或单案件）。"""
    if not zip_path or not os.path.isfile(zip_path):
        return None

    base = "preview"
    try:
        base = os.path.splitext(os.path.basename(zip_path))[0] or "preview"
    except Exception:
        base = "preview"

    inner_zip_infos = []
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for info in zf.infolist():
                try:
                    name = str(info.filename or "")
                except Exception:
                    name = ""
                if not name:
                    continue
                if getattr(info, "is_dir", lambda: False)():
                    continue
                if name.lower().endswith(".zip"):
                    inner_zip_infos.append(info)
    except Exception:
        inner_zip_infos = []

    if len(inner_zip_infos) >= 2:
        bundle = {
            "kind": "bundle",
            "name": base,
            "source_path": zip_path,
            "children": [],
        }

        root = ensure_preview_temp_root(window)
        for idx, info in enumerate(inner_zip_infos, start=1):
            entry_name = ""
            try:
                entry_name = str(info.filename or "")
            except Exception:
                entry_name = ""

            child_base = "case"
            try:
                entry_base = os.path.basename(entry_name.replace("\\", "/"))
                child_base = os.path.splitext(entry_base)[0] or "case"
            except Exception:
                child_base = "case"

            out_base = "preview"
            try:
                out_base = sanitize_filename(f"{base}_{child_base}_{idx}") or "preview"
            except Exception:
                out_base = "preview"
            out_name = f"{out_base}.zip"
            out_path = os.path.join(root, out_name)

            if os.path.exists(out_path):
                n = 2
                while True:
                    cand = os.path.join(root, f"{out_base}_{n}.zip")
                    if not os.path.exists(cand):
                        out_path = cand
                        break
                    n += 1

            data = None
            try:
                with zipfile.ZipFile(zip_path, "r") as zf2:
                    data = zf2.read(entry_name)
            except Exception:
                data = None

            if not data:
                continue

            try:
                with open(out_path, "wb") as f:
                    f.write(data)
            except Exception:
                continue

            try:
                window._preview_temp_files.append(out_path)
            except Exception:
                pass

            try:
                bundle["children"].append(
                    {
                        "name": child_base,
                        "zip_path": out_path,
                    }
                )
            except Exception:
                pass

        return bundle

    return {
        "kind": "case",
        "name": base,
        "zip_path": zip_path,
    }


def add_preview_zip_cases(window, zip_paths: list[str]) -> int:
    """导入 ZIP 列表并追加到预览案件列表中，返回成功追加的数量。"""
    if not zip_paths:
        return 0

    existing_sources: set[str] = set()
    try:
        for top in getattr(window, "_preview_cases", []) or []:
            if not isinstance(top, dict):
                continue
            if str(top.get("kind") or "") == "bundle":
                sp = str(top.get("source_path") or "")
                if sp:
                    existing_sources.add(sp)
            else:
                zp = str(top.get("zip_path") or "")
                if zp:
                    existing_sources.add(zp)
    except Exception:
        existing_sources = set()

    added = 0
    for zp in zip_paths:
        try:
            zp_abs = os.path.abspath(zp)
        except Exception:
            zp_abs = str(zp)

        if not zp_abs or not os.path.isfile(zp_abs):
            continue
        if zp_abs in existing_sources:
            continue

        node = build_preview_case_nodes_from_zip(window, zp_abs)
        if not node:
            continue

        try:
            window._preview_cases.append(node)
        except Exception:
            continue

        existing_sources.add(zp_abs)
        added += 1

    return added
