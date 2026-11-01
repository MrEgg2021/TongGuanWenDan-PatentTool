from __future__ import annotations

import hashlib


def _normalize_text(value: str) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def build_instance_fingerprint(
    *,
    rule_id: str,
    section: str,
    claim_num: int | None,
    pre_context: str,
    snippet: str,
    post_context: str,
) -> str:
    payload = "|".join(
        [
            str(rule_id or ""),
            str(section or ""),
            str(int(claim_num) if claim_num is not None else -1),
            _normalize_text(pre_context),
            _normalize_text(snippet),
            _normalize_text(post_context),
        ]
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


class SuppressionStore:
    def __init__(self) -> None:
        self._current_file_key: str | None = None
        self._instance: dict[str, set[str]] = {}

    def switch_file(self, file_key: str) -> None:
        key = str(file_key or "").strip()
        if self._current_file_key and key and key != self._current_file_key:
            self.clear_all()
        self._current_file_key = key if key else None
        if self._current_file_key:
            self._instance.setdefault(self._current_file_key, set())

    def _require_key(self) -> str | None:
        return self._current_file_key

    def mark_instance(self, fingerprint: str, ignored: bool) -> None:
        key = self._require_key()
        if not key:
            return
        bucket = self._instance.setdefault(key, set())
        fp = str(fingerprint or "").strip()
        if not fp:
            return
        if ignored:
            bucket.add(fp)
        else:
            bucket.discard(fp)

    def is_suppressed(self, issue, fingerprint: str | None = None) -> bool:
        key = self._require_key()
        if not key:
            return False
        instances = self._instance.get(key, set())
        return bool(fingerprint and str(fingerprint or "").strip() in instances)

    def clear_current(self) -> None:
        key = self._require_key()
        if not key:
            return
        self._instance[key] = set()

    def clear_all(self) -> None:
        self._instance = {}
        self._current_file_key = None

