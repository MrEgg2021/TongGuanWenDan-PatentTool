from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

PackageMode = Literal["response", "correction"]
PatentType = Literal["invention", "utility_model", ""]
DocumentSlot = Literal["100001", "100002", "100003", "100004", "100012_body"]
SubmissionScene = Literal["notice_response", "notice_correction", "active_response", "active_correction"]

_DOMESTIC_APP_NO_RE = re.compile(r"^[0-9./_-]+$")


def normalize_application_no(value: str) -> str:
    raw = str(value or "").strip().replace(" ", "")
    if not raw:
        return ""
    upper = raw.upper()
    if upper.startswith("PCT/"):
        return upper
    digits = "".join(ch for ch in raw if ch.isdigit())
    if raw.isdigit():
        return raw
    if _DOMESTIC_APP_NO_RE.fullmatch(raw) and 12 <= len(digits) <= 13:
        return digits
    return raw


@dataclass(frozen=True)
class NoticeMeta:
    application_no: str = ""
    invention_title: str = ""
    applicant: str = ""
    notice_name: str = ""
    notice_code: str = ""
    issue_date: str = ""
    doc_serial: str = ""
    patent_type: PatentType = ""
    limit_days: str = ""
    due_date: str = ""
    internal_no: str = ""
    dossier_no: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "application_no", normalize_application_no(self.application_no))


@dataclass(frozen=True)
class ParsedNotice:
    source_path: str
    meta: NoticeMeta = field(default_factory=NoticeMeta)
    meta_source: Literal["unknown", "list_xml", "pdf_fallback"] = "unknown"
    flat_fields: dict[str, str] = field(default_factory=dict)
    errors: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not bool(self.errors)


@dataclass(frozen=True)
class SlotInput:
    path: str
    preconverted: bool = False


@dataclass(frozen=True)
class CorrectionItem:
    file_name: str = ""
    location: str = ""
    before: str = ""
    after: str = ""


@dataclass(frozen=True)
class ResponsePackageRequest:
    notice: NoticeMeta
    output_dir: str
    opinion_body: SlotInput
    submission_scene: SubmissionScene = "notice_response"
    slots: dict[str, SlotInput] = field(default_factory=dict)
    signature: str = ""
    signature_year: str = ""
    signature_month: str = ""
    signature_day: str = ""


@dataclass(frozen=True)
class CorrectionPackageRequest:
    notice: NoticeMeta
    output_dir: str
    submission_scene: SubmissionScene = "notice_correction"
    correction_items: tuple[CorrectionItem, ...] = ()
    slots: dict[str, SlotInput] = field(default_factory=dict)
    signature: str = ""
    signature_year: str = ""
    signature_month: str = ""
    signature_day: str = ""


@dataclass(frozen=True)
class SlotResult:
    slot_code: str
    xml_path: str
    pages: int = 1
    counts: int = 0
    media_files: tuple[str, ...] = ()


@dataclass(frozen=True)
class PackageResult:
    outer_zip_path: str
    inner_zip_path: str
    case_root: str
    generated_files: tuple[str, ...] = ()
