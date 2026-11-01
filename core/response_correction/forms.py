from __future__ import annotations

import os
from pathlib import Path

from lxml import etree

from .models import CorrectionItem, NoticeMeta, SubmissionScene


def _sub(parent, tag: str, text: str | None = None, **attrs):
    node = etree.SubElement(parent, tag, **{k: str(v) for k, v in attrs.items()})
    if text is not None:
        node.text = str(text)
    return node


def _split_yyyymmdd(value: str) -> tuple[str, str, str]:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    if len(digits) >= 8:
        return digits[:4], digits[4:6], digits[6:8]
    return "", "", ""


def _write_xml(root, output_path: str | os.PathLike[str]) -> str:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tree = etree.ElementTree(root)
    tree.write(str(path), encoding="UTF-8", xml_declaration=True, pretty_print=False)
    return str(path)


def write_response_form_xml(
    output_path: str | os.PathLike[str],
    *,
    notice: NoticeMeta,
    attachment_names: list[tuple[str, str]],
    submission_scene: SubmissionScene = "notice_response",
    signature: str = "",
    signature_year: str = "",
    signature_month: str = "",
    signature_day: str = "",
) -> str:
    is_active = submission_scene == "active_response"
    root = etree.Element("意见陈述书")
    patent = _sub(root, "专利申请或专利")
    _sub(patent, "申请号或专利号", notice.application_no)
    _sub(patent, "发明创造名称", notice.invention_title)
    _sub(patent, "申请人或专利权人姓名或名称", notice.applicant)

    statement = _sub(root, "陈述事项")
    target = _sub(statement, "针对通知书陈述")
    _sub(target, "附加", "0" if is_active else "1")
    date = _sub(target, "专利局就上述专利申请或专利发出通知的日期")
    y, m, d = _split_yyyymmdd("" if is_active else notice.issue_date)
    _sub(date, "年", y)
    _sub(date, "月", m)
    _sub(date, "日", d)
    _sub(target, "专利局就上述专利申请或专利发出通知的名称", "" if is_active else notice.notice_name)
    _sub(target, "发文序号", "" if is_active else notice.doc_serial)

    supplement = _sub(statement, "针对通知书补充陈述")
    _sub(supplement, "附加", "0")
    supplement_date = _sub(supplement, "专利局就上述专利申请或专利发出通知的日期")
    _sub(supplement_date, "年", "")
    _sub(supplement_date, "月", "")
    _sub(supplement_date, "日", "")
    _sub(supplement, "专利局就上述专利申请或专利发出通知的名称", "")
    _sub(supplement, "发文序号", "")

    rule57 = _sub(statement, "根据专利法实施细则第57条第1款第2款的规定主动提出修改")
    _sub(rule57, "附加", "1" if is_active else "0")

    gonggao = _sub(statement, "公布公告事项")
    _sub(gonggao, "附加", "")

    compensation = _sub(statement, "针对专利权期限补偿审批决定陈述")
    _sub(compensation, "附加", "")
    compensation_date = _sub(compensation, "专利局就上述专利申请或专利发出通知的日期")
    _sub(compensation_date, "年", "")
    _sub(compensation_date, "月", "")
    _sub(compensation_date, "日", "")
    _sub(compensation, "发文序号", "")

    drug = _sub(statement, "针对药品专利期限补偿审查意见通知书陈述")
    _sub(drug, "附加", "")
    drug_date = _sub(drug, "专利局就上述专利申请或专利发出通知的日期")
    _sub(drug_date, "年", "")
    _sub(drug_date, "月", "")
    _sub(drug_date, "日", "")
    _sub(drug, "发文序号", "")

    other = _sub(statement, "其他陈述")
    _sub(other, "附加", "0")
    _sub(other, "陈述内容", "")

    experiment = _sub(root, "关于补交实验数据的情况")
    experiment_item = _sub(experiment, "补交了实验数据")
    _sub(experiment_item, "附加", "")

    _sub(root, "陈述的意见", "")

    attachments = _sub(root, "附件清单")
    for index, (name, attachment_type) in enumerate(attachment_names, start=1):
        item = _sub(attachments, "分类附件", 顺序=str(index))
        _sub(item, "附件名称", name)
        _sub(item, "附件类型", attachment_type)
        _sub(item, "属性", "电子件")
    record = _sub(attachments, "备案证明文件")
    _sub(record, "备案证明文件编号", "")

    sign = _sub(root, "当事人或代理机构签章")
    _sub(sign, "签章", signature)
    sign_date = _sub(sign, "签章日期")
    _sub(sign_date, "年", signature_year)
    _sub(sign_date, "月", signature_month)
    _sub(sign_date, "日", signature_day)

    office = _sub(root, "专利局处理意见")
    _sub(office, "意见内容", "")
    office_date = _sub(office, "提出日期")
    _sub(office_date, "年", "")
    _sub(office_date, "月", "")
    _sub(office_date, "日", "")
    return _write_xml(root, output_path)


def write_correction_form_xml(
    output_path: str | os.PathLike[str],
    *,
    notice: NoticeMeta,
    correction_items: tuple[CorrectionItem, ...] = (),
    attachment_names: list[tuple[str, str]],
    submission_scene: SubmissionScene = "notice_correction",
    signature: str = "",
    signature_year: str = "",
    signature_month: str = "",
    signature_day: str = "",
) -> str:
    is_active = submission_scene == "active_correction"
    root = etree.Element("补正书")
    patent = _sub(root, "专利申请")
    _sub(patent, "申请号", notice.application_no)
    _sub(patent, "发明创造名称", notice.invention_title)
    _sub(patent, "申请人或专利权人姓名或名称", notice.applicant)

    reason = _sub(root, "补正原因")
    rule57 = _sub(reason, "根据专利法实施细则第57条的规定")
    _sub(rule57, "附加", "1" if is_active else "0")
    rule50 = _sub(reason, "根据专利法实施细则第50条的规定针对通知书")
    _sub(rule50, "附加", "0" if is_active else "1")
    date = _sub(rule50, "日期")
    y, m, d = _split_yyyymmdd("" if is_active else notice.issue_date)
    _sub(date, "年", y)
    _sub(date, "月", m)
    _sub(date, "日", d)
    _sub(rule50, "通知书序号", "" if is_active else notice.notice_name)
    _sub(rule50, "发文序号", "" if is_active else notice.doc_serial)

    content = _sub(root, "补正内容")
    for index, item_data in enumerate(correction_items or (), start=1):
        item = _sub(content, "补正项", 顺序=str(index))
        _sub(item, "文件名称", item_data.file_name)
        _sub(item, "文件中的位置", item_data.location)
        _sub(item, "补正前", item_data.before)
        _sub(item, "补正后", item_data.after)

    attachments = _sub(root, "附件清单")
    for index, (name, attachment_type) in enumerate(attachment_names, start=1):
        item = _sub(attachments, "分类附件", 顺序=str(index))
        _sub(item, "附件名称", name)
        _sub(item, "附件类型", attachment_type)
        _sub(item, "属性", "电子件")
    record = _sub(attachments, "备案证明文件")
    _sub(record, "备案证明文件编号", "")

    sign = _sub(root, "专利代理机构签章")
    _sub(sign, "签章", signature)
    sign_date = _sub(sign, "签章日期")
    _sub(sign_date, "年", signature_year)
    _sub(sign_date, "月", signature_month)
    _sub(sign_date, "日", signature_day)

    office = _sub(root, "专利局处理意见")
    _sub(office, "意见内容", "")
    office_date = _sub(office, "提出日期")
    _sub(office_date, "年", "")
    _sub(office_date, "月", "")
    _sub(office_date, "日", "")
    return _write_xml(root, output_path)


__all__ = ["write_correction_form_xml", "write_response_form_xml"]
