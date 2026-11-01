from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


_SUPPORTED_SUFFIXES = (".doc", ".docx", ".pdf", ".zip")
_SLOT_ROLE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("权利要求书", "100001"),
    ("说明书", "100002"),
    ("说明书附图", "100003"),
    ("说明书摘要", "100004"),
)
_FLOW_ROLE_OPTIONS = {
    "response": (("意见陈述书", "opinion_body"), *_SLOT_ROLE_OPTIONS),
    "active_response": (("意见陈述书", "opinion_body"), *_SLOT_ROLE_OPTIONS),
    "correction": _SLOT_ROLE_OPTIONS,
    "active_correction": _SLOT_ROLE_OPTIONS,
}
_ROLE_LABELS = {code: label for label, code in _FLOW_ROLE_OPTIONS["response"]}
_COMPARISON_TOKENS = ("修改对照", "对照页", "comparison", "compare")


def _normalized_path(path: str) -> str:
    text = str(path or "").strip()
    if not text:
        return ""
    try:
        return os.path.normcase(str(Path(text).resolve()))
    except Exception:
        return os.path.normcase(os.path.abspath(text))


@dataclass(frozen=True)
class StagedImportItem:
    source_path: str
    source_kind: str = "file"
    suggested_role: str = ""
    selected_role: str = ""
    status: str = "待上传"
    confirmed_role: str = ""
    confirmed_time: str = ""
    confirmed_payload_path: str = ""
    result_message: str = ""
    error_message: str = ""


def source_kind_for_path(path: str) -> str:
    suffix = Path(str(path or "")).suffix.lower()
    if suffix == ".zip":
        return "xml_package"
    if suffix == ".pdf":
        return "pdf"
    if suffix in {".doc", ".docx"}:
        return "word"
    return "file"


def should_attempt_notice_parse(path: str, flow: str) -> bool:
    flow_name = str(flow or "").strip()
    if flow_name not in {"response", "correction", "active_response", "active_correction"}:
        return False
    source = Path(str(path or ""))
    suffix = source.suffix.lower()
    if suffix not in {".zip", ".pdf"}:
        return False
    name = source.name.lower()
    if any(token in name for token in _COMPARISON_TOKENS):
        return False
    return True


def should_silently_ignore_material(path: str, flow: str) -> bool:
    _ = flow
    source = Path(str(path or ""))
    name = source.name.lower()
    return any(token in name for token in _COMPARISON_TOKENS)


def unsupported_material_reason(path: str, flow: str) -> str:
    _ = flow
    source = Path(str(path or ""))
    suffix = source.suffix.lower()
    if suffix == ".pdf":
        return f"{source.name} 不是当前页面可导入材料，已跳过。"
    return ""


def role_options_for_flow(flow: str) -> tuple[tuple[str, str], ...]:
    return tuple(_FLOW_ROLE_OPTIONS.get(str(flow or "").strip(), _FLOW_ROLE_OPTIONS["response"]))


def role_label_for_code(code: str) -> str:
    if not code:
        return "暂不关联"
    return _ROLE_LABELS.get(str(code or "").strip(), str(code or "").strip())


def collect_response_correction_files(paths, include_directories: bool = True):
    valid_files: list[str] = []
    ignored: list[str] = []
    seen: set[str] = set()
    for raw in paths or []:
        if not isinstance(raw, str):
            continue
        normalized = os.path.normpath(raw.strip())
        if not normalized:
            continue
        if os.path.isdir(normalized):
            if not include_directories:
                ignored.append(f"{normalized} 是文件夹，已跳过")
                continue
            walk_errors: list[str] = []
            collected = False

            def _on_walk_error(exc: OSError) -> None:
                target = getattr(exc, "filename", None) or normalized
                walk_errors.append(f"{os.path.normpath(str(target))} 无法读取，已跳过")

            collected = False
            for current_root, _dirnames, filenames in os.walk(normalized, topdown=True, onerror=_on_walk_error, followlinks=False):
                for entry in sorted(filenames):
                    if entry.startswith("~$"):
                        ignored.append(f"{entry} 是临时文件，已跳过")
                        continue
                    full_path = os.path.join(current_root, entry)
                    normalized_full_path = _normalized_path(full_path)
                    if not entry.lower().endswith(_SUPPORTED_SUFFIXES):
                        ignored.append(f"{entry} 不是受支持的文件类型，已跳过")
                        continue
                    if normalized_full_path not in seen:
                        valid_files.append(full_path)
                        seen.add(normalized_full_path)
                        collected = True
            ignored.extend(walk_errors)
            if not collected:
                ignored.append(f"{normalized} 整个目录树中未发现可导入的 DOC/DOCX/PDF/ZIP 文件")
            continue
        if not os.path.isfile(normalized):
            ignored.append(f"{normalized} 不存在，已跳过")
            continue
        name = os.path.basename(normalized)
        if name.startswith("~$"):
            ignored.append(f"{name} 是临时文件，已跳过")
            continue
        if not name.lower().endswith(_SUPPORTED_SUFFIXES):
            ignored.append(f"{name} 不是受支持的文件类型，已跳过")
            continue
        normalized_key = _normalized_path(normalized)
        if normalized_key not in seen:
            valid_files.append(normalized)
            seen.add(normalized_key)
    return valid_files, ignored


def suggest_role_for_path(path: str, flow: str) -> str:
    allowed = {code for _label, code in role_options_for_flow(flow)}
    name = Path(str(path or "")).name.lower()
    if "opinion_body" in allowed and any(token in name for token in ("意见陈述", "意见陈述书", "opinion", "response")):
        return "opinion_body"
    if "100001" in allowed and any(token in name for token in ("权利要求", "claims", "claim")):
        return "100001"
    if "100003" in allowed and any(token in name for token in ("附图", "drawings", "drawing", "figure")):
        return "100003"
    if "100004" in allowed and any(token in name for token in ("摘要", "abstract")):
        return "100004"
    if "100002" in allowed and any(token in name for token in ("说明书", "description", "specification")):
        return "100002"
    return ""


__all__ = [
    "StagedImportItem",
    "collect_response_correction_files",
    "role_label_for_code",
    "role_options_for_flow",
    "should_silently_ignore_material",
    "source_kind_for_path",
    "suggest_role_for_path",
    "should_attempt_notice_parse",
    "unsupported_material_reason",
]
