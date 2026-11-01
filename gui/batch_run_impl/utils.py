import shutil
import zipfile


def _increment_case_number(case_number: str) -> str:
    """根据原有逻辑递增案件号字符串。"""
    try:
        import re

        match = re.match(r"(\D*)(\d+)", case_number)
        if match:
            prefix = match.group(1)
            num = int(match.group(2))
            return f"{prefix}{num + 1:0{len(match.group(2))}d}"
        # 如果没有数字，直接加1
        return case_number + "1"
    except Exception:
        return case_number + "1"


def _repack_case_zip_with_root(src_zip_path: str, dest_zip_path: str, new_root_name: str, old_root_name: str | None = None) -> None:
    """重打包单案 ZIP，使其解压后的顶层目录名与 new_root_name 一致。

    - src_zip_path: 核心转换逻辑生成的内层案件 ZIP（通常顶层为数字 case_id）。
    - dest_zip_path: 目标 ZIP 路径。
    - new_root_name: 希望使用的顶层目录名（已做过文件名安全处理）。
    - old_root_name: 原顶层目录名（通常为 case_id），若为空则不做前缀剥离，直接嵌套在 new_root_name 下。
    """

    try:
        normalized_new_root = (new_root_name or "").strip().strip("/\\") or "output"
        normalized_old_root = (old_root_name or "").strip().strip("/\\")

        with zipfile.ZipFile(src_zip_path, "r") as src, zipfile.ZipFile(
            dest_zip_path, "w", zipfile.ZIP_DEFLATED
        ) as dst:
            for info in src.infolist():
                name = info.filename or ""
                # 跳过纯目录占位条目，ZipFile 会根据文件路径自动创建目录
                if not name or name.endswith("/") or name.endswith("\\"):
                    continue

                rel = name.lstrip("/\\")
                if normalized_old_root and (
                    rel == normalized_old_root
                    or rel.startswith(normalized_old_root + "/")
                    or rel.startswith(normalized_old_root + "\\")
                ):
                    rel = rel[len(normalized_old_root) :].lstrip("/\\")

                new_name = normalized_new_root
                if rel:
                    new_name = normalized_new_root + "/" + rel.replace("\\", "/")

                data = src.read(info.filename)
                dst.writestr(new_name, data)
    except Exception:
        # 若重打包失败，退回为简单复制原 ZIP，避免整个批量任务失败
        try:
            shutil.copy(src_zip_path, dest_zip_path)
        except Exception:
            pass


__all__ = ["_repack_case_zip_with_root", "_increment_case_number"]
