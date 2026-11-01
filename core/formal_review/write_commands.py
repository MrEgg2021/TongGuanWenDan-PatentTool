from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

ActionKind = Literal["insert_after_name", "replace_marker_after_name", "replace_span_text"]


@dataclass(slots=True, frozen=True)
class WriteCommand:
    cmd_id: str
    action_kind: ActionKind
    section: str
    claim_num: int | None
    name: str
    marker: str
    local_start: int
    local_end: int
    word_start: int
    word_end: int
    expected_old_fragment: str
    replacement_text: str


@dataclass(slots=True)
class MarkerNormalizationWritePlan:
    commands: list[WriteCommand] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    candidate_claims: int = 0
    candidate_description: int = 0
    inserted_count: int = 0
    replaced_count: int = 0
    skipped_correct_count: int = 0
    skipped_unsupported_count: int = 0
    claim_resolve_strict_failed_count: int = 0
    claim_resolve_loose_rescued_count: int = 0
    claim_resolve_projection_count: int = 0
    claim_resolve_word_find_com_count: int = 0
    claim_resolve_word_find_legacy_count: int = 0
    claim_name_exact_check_failed_count: int = 0
    claim_name_nearby_rescued_count: int = 0
    claim_name_unsafe_continue_count: int = 0
    description_scope_found: bool = True

    @property
    def command_count(self) -> int:
        return len(self.commands)


@dataclass(slots=True, frozen=True)
class PreflightFailure:
    cmd_id: str
    reason: str
    expected: str
    actual: str


@dataclass(slots=True)
class MarkerNormalizationPreflightResult:
    passed: bool
    failures: list[PreflightFailure] = field(default_factory=list)
    checked_count: int = 0


@dataclass(slots=True)
class MarkerNormalizationApplyReport:
    committed: bool
    planned_count: int
    applied_count: int
    inserted_count: int
    replaced_count: int
    failed_count: int = 0
    failed_cmd_ids: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
