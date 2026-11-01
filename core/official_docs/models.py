from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Literal

NoticeKind = str
NamingMode = Literal["default", "custom"]
MetaSource = Literal["unknown", "list_xml", "pdf_fallback"]
NoListMultiPdfMode = Literal["split_each_pdf", "merge_all"]


@dataclass(frozen=True)
class ReceiptFeeLineItem:
    code: str = ""
    name: str = ""
    amount: str = ""


@dataclass(frozen=True)
class NoticeMeta:
    notice_code: str = ""
    notice_name: str = ""
    invention_name: str = ""
    notice_round: str = ""
    app_no: str = ""
    app_no_dotted: str = ""
    issue_date_raw: str = ""
    issue_date: str = ""
    issue_date8: str = ""
    internal_no: str = ""
    due_date: str = ""
    limit_days: str = ""
    doc_serial: str = ""
    dossier_no: str = ""
    patent_type: str = ""
    apply_date: str = ""
    applicant: str = ""
    receipt_payer: str = ""
    receipt_app_no: str = ""
    receipt_patent_type: str = ""
    receipt_fee_item: str = ""
    receipt_fee_items: tuple[ReceiptFeeLineItem, ...] = field(default_factory=tuple)
    receipt_fee_item_first: str = ""
    receipt_fee_item_summary: str = ""
    receipt_fee_item_detail: str = ""
    receipt_amount: str = ""
    receipt_payment_date: str = ""
    receipt_payment_method: str = ""
    receipt_order_no: str = ""
    receipt_ticket_code: str = ""
    receipt_ticket_no: str = ""
    receipt_invoice_date: str = ""
    receipt_payer_credit_code: str = ""
    receipt_check_code: str = ""
    receipt_payee_unit: str = ""
    receipt_reviewer: str = ""
    receipt_collector: str = ""


@dataclass(frozen=True)
class AttachmentMeta:
    name: str = ""
    desc: str = ""


@dataclass(frozen=True)
class PdfSource:
    raw_name: str
    display_name: str
    kind: Literal["main", "attachment", "extra"]
    source_type: Literal["pdf", "image"] = "pdf"


@dataclass(frozen=True)
class ParsedNotice:
    source_zip_path: str
    notice_kind: NoticeKind
    meta: NoticeMeta
    meta_source: MetaSource = "unknown"
    flat_fields: dict[str, str] = field(default_factory=dict)
    attachments: list[AttachmentMeta] = field(default_factory=list)
    pdf_entries: list[PdfSource] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not bool(self.errors)


@dataclass(frozen=True)
class NoticeAliasRule:
    notice_name: str
    short_name: str
    enabled: bool = False


@dataclass(frozen=True)
class NoticeTypeNamingConfig:
    naming_mode: NamingMode = "default"
    filename_fields: list[str] = field(default_factory=list)
    alias_rules: list[NoticeAliasRule] = field(default_factory=list)


@dataclass(frozen=True)
class NamingGroupConfig:
    id: str
    name: str
    member_type_keys: list[str] = field(default_factory=list)
    group_config: NoticeTypeNamingConfig = field(default_factory=NoticeTypeNamingConfig)


CollisionPolicy = Literal["overwrite", "skip", "rename"]
CollisionResolver = Callable[[str, str], CollisionPolicy]


@dataclass(frozen=True)
class ProcessOptions:
    summary_root_dir: str
    archive_root_dir: str
    write_summary: bool = True
    write_archive: bool = True
    filename_template: str = "{申请号}+{通知书名称}+{发文日}"
    archive_dir_template: str = "{申请号}"
    filename_template_by_kind: dict[str, str] = field(default_factory=dict)
    archive_dir_template_by_kind: dict[str, str] = field(default_factory=dict)
    category_mode: Literal["full_name", "short_kind", "custom"] = "full_name"
    category_template_exam_opinion: str = "{次数}审"
    category_template_rectification: str = "{次数}补正"
    filename_separator: str = "+"
    type_naming_configs: dict[str, NoticeTypeNamingConfig] = field(default_factory=dict)
    naming_groups: dict[str, NamingGroupConfig] = field(default_factory=dict)
    type_group_membership: dict[str, str] = field(default_factory=dict)
    confirm_each: bool = True
    enable_exam_pdf_parse: bool = False
    pdf_parse_field_flags: dict[str, bool] = field(default_factory=dict)
    no_list_multi_pdf_mode: NoListMultiPdfMode = "split_each_pdf"
    source_label_by_zip_path: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ProcessItemResult:
    source_zip_path: str
    status: Literal["success", "skip", "fail"]
    reason: str = ""
    notice_kind: NoticeKind = "unknown"
    notice_key: str = ""
    meta: NoticeMeta = field(default_factory=NoticeMeta)
    meta_source: MetaSource = "unknown"
    output_pdf_name: str = ""
    summary_pdf_path: str = ""
    archive_pdf_path: str = ""
    merged_sources: list[str] = field(default_factory=list)
    business_fields: dict[str, str] = field(default_factory=dict)
    uncertain_fields: dict[str, str] = field(default_factory=dict)
    raw_fields: dict[str, str] = field(default_factory=dict)
    flat_fields: dict[str, str] = field(default_factory=dict)
    pdf_parse_status: str = ""
    pdf_parse_error: str = ""
    pdf_reject_reason: str = ""
    pdf_reject_reasons: str = ""
    pdf_clauses: str = ""
    pdf_cn_pubnos: str = ""
    pdf_examiner_name: str = ""
    pdf_examiner_phone: str = ""
    pdf_department: str = ""
    pdf_center: str = ""
    pdf_applicant: str = ""
    pdf_inventor: str = ""
    pdf_agent: str = ""
    pdf_agency_raw: str = ""
    pdf_panel_head: str = ""
    pdf_panel_main: str = ""
    pdf_panel_member: str = ""
    pdf_dossier_no: str = ""
    pdf_authorization_pub_no: str = ""
    pdf_authorization_pub_date: str = ""
    pdf_certificate_no: str = ""
    pdf_qrcode_link: str = ""
    pdf_qrcode_image_bytes: bytes = b""
    pdf_evidence: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ProcessSummary:
    summary_run_dir: str = ""
    excel_path: str = ""
    total: int = 0
    success: int = 0
    skipped: int = 0
    failed: int = 0
    items: list[ProcessItemResult] = field(default_factory=list)
