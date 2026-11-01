from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class ClaimItem:
    num: int
    text: str
    word_count: int = 0
    markers: list[str] = field(default_factory=list)
    refs: list[int] = field(default_factory=list)
    anchor_start: int | None = None
    anchor_end: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Issue:
    rule_id: str
    severity: str
    category: str
    section: str
    message: str
    claim_num: int | None = None
    span_start: int | None = None
    span_end: int | None = None
    snippet: str | None = None
    anchor: dict[str, Any] | None = None
    issue_id: str | None = None
    ignored: bool = False
    rule_name: str = ""
    suggestion: str = ""
    location: dict[str, Any] | None = None
    evidence: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["ruleId"] = self.rule_id
        payload["ruleName"] = self.rule_name
        return payload


@dataclass(slots=True)
class FormalReviewDocument:
    claims: list[ClaimItem] = field(default_factory=list)
    description: str = ""
    abstract: str = ""
    drawings: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["claims"] = [claim.to_dict() for claim in self.claims]
        return payload
