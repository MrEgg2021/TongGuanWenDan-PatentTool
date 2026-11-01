from __future__ import annotations

import re
from dataclasses import dataclass

_MARKER_TOKEN_RE = re.compile(r"^\d{1,6}[A-Za-z]?(?:/\d{1,6}[A-Za-z]?)*$")
_MARKER_IN_TEXT_RE = re.compile(
    r"[（(\[【]\s*([0-9]{1,6}[A-Za-z]?(?:\s*/\s*[0-9]{1,6}[A-Za-z]?)*)\s*[）)\]】]"
)
_MARKER_NOTE_SPLIT_RE = re.compile(r"[;\n；]+")
_MARKER_NOTE_PAIR_RE = re.compile(
    r"^\s*([0-9]{1,6}[A-Za-z]?(?:\s*/\s*[0-9]{1,6}[A-Za-z]?)*)"
    r"(?:\s*[、,:：，)\]）】]\s*|\s+)"
    r"(.+?)\s*$"
)


@dataclass(slots=True)
class MarkerNoteParsePayload:
    marker_to_name: dict[str, str]
    name_to_marker: dict[str, str]
    warnings: list[str]
    errors: list[str]


def normalize_marker_token(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    parts = [part.strip() for part in text.split("/") if part and part.strip()]
    normalized_parts: list[str] = []
    for part in parts:
        matched = re.match(r"^(\d{1,6})([A-Za-z]?)$", part)
        if not matched:
            return ""
        number = str(matched.group(1))
        suffix = str(matched.group(2) or "").upper()
        normalized_parts.append(f"{number}{suffix}")
    result = "/".join(normalized_parts)
    return result if _MARKER_TOKEN_RE.match(result) else ""


def _marker_sort_key(value: str) -> tuple:
    rows: list[tuple[int, str]] = []
    for part in str(value or "").split("/"):
        matched = re.match(r"^(\d{1,6})([A-Za-z]?)$", str(part or ""))
        if not matched:
            rows.append((10**9, str(part or "")))
            continue
        rows.append((int(matched.group(1)), str(matched.group(2) or "").upper()))
    return tuple(rows)


def count_effective_chars(text: str) -> int:
    count = 0
    for ch in text or "":
        if ch.isspace():
            continue
        count += 1
    return count


def extract_figure_markers(text: str) -> list[str]:
    seen: set[str] = set()
    markers: list[str] = []
    for match in _MARKER_IN_TEXT_RE.finditer(text or ""):
        marker = normalize_marker_token(match.group(1))
        if not marker or marker in seen:
            continue
        seen.add(marker)
        markers.append(marker)
    return sorted(markers, key=_marker_sort_key)


def parse_marker_note_payload(text: str) -> MarkerNoteParsePayload:
    marker_to_name: dict[str, str] = {}
    name_to_marker: dict[str, str] = {}
    warnings: list[str] = []
    errors: list[str] = []

    for idx, raw_part in enumerate(_MARKER_NOTE_SPLIT_RE.split(text or ""), start=1):
        part = str(raw_part or "").strip().strip("。")
        if not part:
            continue

        matched = _MARKER_NOTE_PAIR_RE.match(part)
        if not matched:
            warnings.append(f"第{idx}项格式无法识别，已忽略：{part}")
            continue

        marker = normalize_marker_token(str(matched.group(1) or "").strip())
        name = str(matched.group(2) or "").strip().strip("。；;")
        if not marker:
            warnings.append(f"第{idx}项标号不合法，已忽略：{part}")
            continue
        if not name:
            warnings.append(f"第{idx}项名称为空，已忽略：{part}")
            continue

        prev_marker = name_to_marker.get(name)
        if prev_marker and prev_marker != marker:
            errors.append(f"名称“{name}”同时映射到“{prev_marker}”和“{marker}”")
            continue

        prev_name = marker_to_name.get(marker)
        if prev_name and prev_name != name:
            warnings.append(f"标号“{marker}”映射多个名称：保留“{prev_name}”，忽略“{name}”")
        else:
            marker_to_name[marker] = name

        name_to_marker[name] = marker

    return MarkerNoteParsePayload(
        marker_to_name=marker_to_name,
        name_to_marker=name_to_marker,
        warnings=warnings,
        errors=errors,
    )


def parse_marker_note_map(text: str) -> dict[str, str]:
    return dict(parse_marker_note_payload(text).marker_to_name)
