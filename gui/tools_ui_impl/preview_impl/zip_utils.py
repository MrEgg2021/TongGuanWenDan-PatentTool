import os
import re
import tempfile
import zipfile

from .constants import FILENAME_SANITIZE_PATTERN


def sanitize_filename(name: str, fallback: str = "preview") -> str:
    cleaned = re.sub(FILENAME_SANITIZE_PATTERN, "_", name or "")
    cleaned = cleaned.strip(" .") or fallback
    return cleaned


def build_preview_zip_without_case_root(zip_path: str, temp_paths: list[str] | None = None, depth: int = 3) -> str:
    if temp_paths is None:
        temp_paths = []
    if depth <= 0:
        return zip_path
    try:
        with zipfile.ZipFile(zip_path, "r") as src:
            file_infos = [info for info in src.infolist() if info.filename and not info.is_dir()]
            if not file_infos:
                return zip_path

            # 先处理“单一内层 ZIP”的情况，支持多层嵌套（限制 depth）
            zip_entries = [info for info in file_infos if info.filename.lower().endswith(".zip")]
            if len(zip_entries) == 1 and len(file_infos) == 1:
                fd, inner_tmp = tempfile.mkstemp(suffix=".zip")
                os.close(fd)
                try:
                    data = src.read(zip_entries[0].filename)
                    with open(inner_tmp, "wb") as f:
                        f.write(data)
                    temp_paths.append(inner_tmp)
                    return build_preview_zip_without_case_root(inner_tmp, temp_paths, depth=depth - 1)
                except Exception:
                    try:
                        os.remove(inner_tmp)
                    except Exception:
                        pass
                    return zip_path

            names = []
            for info in file_infos:
                name = info.filename or ""
                if not name or name.endswith("/") or name.endswith("\\"):
                    continue
                names.append(name)
            if not names:
                return zip_path

            first_segments = set()
            second_segments = set()
            for name in names:
                parts = name.replace("\\", "/").lstrip("/").split("/")
                if not parts:
                    continue
                first_segments.add(parts[0])
                if len(parts) >= 2:
                    second_segments.add(parts[1])
            if len(first_segments) != 1:
                return zip_path
            root = list(first_segments)[0]
            markers = {"100001", "100002", "100003", "100004", "110101", "120101"}
            has_inner_markers = any(seg in markers or seg.lower() == "list.xml" for seg in second_segments)
            if not has_inner_markers:
                return zip_path
            fd, tmp_path = tempfile.mkstemp(suffix=".zip")
            os.close(fd)
            try:
                with zipfile.ZipFile(zip_path, "r") as src2, zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as dst:
                    for info in src2.infolist():
                        name = info.filename or ""
                        if not name or name.endswith("/") or name.endswith("\\"):
                            continue
                        rel = name.replace("\\", "/").lstrip("/")
                        if not rel:
                            continue
                        parts = rel.split("/", 1)
                        if parts[0] == root:
                            new_name = parts[1] if len(parts) > 1 else ""
                        else:
                            new_name = rel
                        new_name = new_name.strip("/")
                        if not new_name:
                            continue
                        data = src2.read(info.filename)
                        dst.writestr(new_name, data)
                temp_paths.append(tmp_path)
                return tmp_path
            except Exception:
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
                return zip_path
    except Exception:
        return zip_path


__all__ = ["sanitize_filename", "build_preview_zip_without_case_root"]
