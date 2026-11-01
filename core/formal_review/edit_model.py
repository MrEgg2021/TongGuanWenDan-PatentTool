from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class TokenSpan:
    token: str
    kind: str = "non_text"
    local_start: int = 0
    local_end: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class EditableSegment:
    segment_id: str
    section: str
    claim_num: int | None
    paragraph_index: int
    word_start: int
    word_end: int
    original_display_text: str
    original_word_text: str
    token_spans: list[TokenSpan] = field(default_factory=list)
    has_non_text: bool = False
    prefix_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["token_spans"] = [item.to_dict() for item in self.token_spans]
        return payload
