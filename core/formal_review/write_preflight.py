from __future__ import annotations

import re
import time

from .write_commands import MarkerNormalizationPreflightResult, PreflightFailure


def _range_text_with_retry(doc, start: int, end: int, retries: int = 2, retry_delay: float = 0.4) -> str:
    last_exc: Exception | None = None
    for attempt in range(0, retries + 1):
        try:
            rng = doc.Range(int(start), int(end))
            return str(getattr(rng, "Text", "") or "")
        except Exception as exc:
            last_exc = exc
            if attempt >= retries:
                break
            time.sleep(max(0.0, float(retry_delay)))
    raise RuntimeError(str(last_exc or "Range 读取失败"))


def _sanitize_visible_text(text: str) -> str:
    source = str(text or "").replace("\r", "")
    return "".join(ch for ch in source if (ch in ("\t", "\n") or ord(ch) >= 0x20))


def _compact_text(text: str) -> str:
    return re.sub(r"\s+", "", _sanitize_visible_text(text))


def _validate_name_anchor(doc, cmd) -> tuple[bool, str]:
    action_kind = str(getattr(cmd, "action_kind", "") or "")
    if action_kind not in {"insert_after_name", "replace_marker_after_name"}:
        return True, ""
    name = str(getattr(cmd, "name", "") or "").strip()
    compact_name = _compact_text(name)
    if not compact_name:
        return True, ""

    word_start = int(getattr(cmd, "word_start", 0) or 0)
    if word_start <= 0:
        return False, "name_anchor_invalid_start"

    window = max(int(len(compact_name) + 8), 24)
    left_start = max(0, int(word_start - window))
    try:
        left_raw = _range_text_with_retry(doc, int(left_start), int(word_start))
    except Exception as exc:
        return False, f"name_anchor_read_failed: {exc}"
    left_compact = _compact_text(left_raw)
    if left_compact.endswith(compact_name):
        return True, ""
    tail = left_compact[-max(24, len(compact_name) + 6) :]
    return False, f"name_anchor_mismatch name={compact_name!r} tail={tail!r}"


def run_write_preflight(doc, commands) -> MarkerNormalizationPreflightResult:
    failures: list[PreflightFailure] = []
    checked = 0
    for cmd in list(commands or []):
        checked += 1
        try:
            actual = _range_text_with_retry(doc, int(cmd.word_start), int(cmd.word_end))
        except Exception as exc:
            failures.append(
                PreflightFailure(
                    cmd_id=str(getattr(cmd, "cmd_id", "")),
                    reason=f"Range 读取失败: {exc}",
                    expected=str(getattr(cmd, "expected_old_fragment", "") or ""),
                    actual="",
                )
            )
            continue
        expected = str(getattr(cmd, "expected_old_fragment", "") or "")
        if actual != expected:
            failures.append(
                PreflightFailure(
                    cmd_id=str(getattr(cmd, "cmd_id", "")),
                    reason="expected_old_fragment mismatch",
                    expected=expected,
                    actual=actual,
                )
            )
            continue
        anchor_ok, anchor_reason = _validate_name_anchor(doc, cmd)
        if not anchor_ok:
            failures.append(
                PreflightFailure(
                    cmd_id=str(getattr(cmd, "cmd_id", "")),
                    reason=str(anchor_reason or "name_anchor_mismatch"),
                    expected=str(getattr(cmd, "name", "") or ""),
                    actual=actual,
                )
            )
    return MarkerNormalizationPreflightResult(
        passed=(len(failures) == 0),
        failures=failures,
        checked_count=checked,
    )
