from __future__ import annotations

import os

from lxml import etree

from core.logging_utils import logger

from .normalize import _normalize_applicant_type_code, _normalize_id_type_code


def create_120101_xml(case_root, invention_title, config, request_info, has_drawings: bool = False):
    """生成 120101.xml（实用新型专利请求书）"""
    bus_cfg = config.get("bus", {}) or {}

    ri = request_info
    inv_list = []
    app_list = []
    inv_ri = {}
    app_ri = {}
    contact_ri = {}
    fee_flag = None
    title_override = None
    agency_enabled = False
    agency_info = None
    if isinstance(ri, dict):
        inv_list = ri.get("inventors") or []
        app_list = ri.get("applicants") or []
        contact_ri = ri.get("contact") or {}
        if inv_list:
            inv_ri = inv_list[0] or {}
        if app_list:
            app_ri = app_list[0] or {}
        if "fee_reduction_enabled" in ri:
            fee_flag = bool(ri.get("fee_reduction_enabled"))
        title_override = ri.get("title")

        if "agency_enabled" in ri:
            try:
                agency_enabled = bool(ri.get("agency_enabled"))
            except Exception:
                agency_enabled = False

        try:
            agency_info = ri.get("agency_info")
        except Exception:
            agency_info = None

    if not invention_title:
        try:
            if request_info and isinstance(request_info, dict):
                src_path = request_info.get("_source_file")
                if src_path:
                    invention_title = os.path.splitext(os.path.basename(str(src_path)))[0]
        except Exception:
            invention_title = None
    if not invention_title:
        try:
            invention_title = str(bus_cfg.get("invention_title") or "").strip() or ""
        except Exception:
            invention_title = ""
    if isinstance(title_override, str) and title_override.strip():
        invention_title = title_override.strip()

    root = etree.Element("实用新型专利请求书")

    etree.SubElement(root, "收到日期")
    etree.SubElement(root, "申请号")
    etree.SubElement(root, "分案提交日")
    etree.SubElement(root, "申请日")
    etree.SubElement(root, "费减审批")
    etree.SubElement(root, "向外申请审批")
    etree.SubElement(root, "挂号号码")

    title_node = etree.SubElement(root, "发明名称")
    title_node.text = invention_title
    etree.SubElement(root, "发明英文名称").text = ""

    internal_no = ""
    etree.SubElement(root, "内部编号").text = internal_no

    inventors = etree.SubElement(root, "发明人")
    first_inv = etree.SubElement(inventors, "第一发明人")
    inv_name = ""
    inv_idno = ""
    nationality = "CN"
    if isinstance(inv_ri, dict):
        inv_name = inv_ri.get("name", inv_name)
        inv_idno = inv_ri.get("id_no", inv_idno)
        nat_code = inv_ri.get("nationality_code")
        if nat_code:
            nationality = str(nat_code)
    if inv_name is None:
        inv_name = ""
    if inv_idno is None:
        inv_idno = ""
    etree.SubElement(first_inv, "姓名").text = str(inv_name)
    req_pub = etree.SubElement(first_inv, "请求不公开")
    etree.SubElement(req_pub, "附加").text = "0"
    etree.SubElement(first_inv, "国籍").text = nationality
    etree.SubElement(first_inv, "身份证件号码").text = str(inv_idno)
    etree.SubElement(first_inv, "英文姓名").text = ""

    # 若上游提供了多个发明人，则按顺序生成 "其他发明人"
    if isinstance(inv_list, list) and len(inv_list) > 1:
        order = 1
        for extra in inv_list[1:]:
            if not isinstance(extra, dict):
                continue
            other_inv = etree.SubElement(inventors, "其他发明人", 顺序=str(order))
            extra_name = extra.get("name") or ""
            etree.SubElement(other_inv, "姓名").text = str(extra_name)
            other_req_pub = etree.SubElement(other_inv, "请求不公开")
            etree.SubElement(other_req_pub, "附加").text = "0"
            etree.SubElement(other_inv, "英文姓名").text = ""
            etree.SubElement(other_inv, "国籍").text = str(extra.get("nationality_code") or "CN")
            etree.SubElement(other_inv, "身份证件号码").text = str(extra.get("id_no") or "")
            order += 1

    applicants = etree.SubElement(root, "申请人")
    first_app = etree.SubElement(applicants, "第一申请人")
    app_name = ""
    app_type = ""
    app_id_no = ""
    app_email = ""
    app_province = ""
    app_city = ""
    app_address = ""
    app_zip = ""
    app_phone = ""
    app_id_type = ""
    raw_type_code = None
    raw_type_text = None
    raw_id_type_code = None
    raw_id_type_text = None
    if isinstance(app_ri, dict):
        app_name = app_ri.get("name", app_name)
        raw_type_code = app_ri.get("type_code")
        raw_type_text = app_ri.get("type")
        app_id_no = app_ri.get("id_no", app_id_no)
        app_email = app_ri.get("email", app_email)
        app_province = app_ri.get("province_code", app_ri.get("province", app_province))
        city_val = app_ri.get("city_code", app_ri.get("city", app_city))
        district_val = app_ri.get("district_code", app_ri.get("district"))
        if district_val and not city_val:
            city_val = district_val
        app_city = city_val
        app_address = app_ri.get("address", app_address)
        app_zip = app_ri.get("zip", app_zip)
        app_phone = app_ri.get("phone", app_phone)
        raw_id_type_code = app_ri.get("id_type_code")
        raw_id_type_text = app_ri.get("id_type")
    app_type = _normalize_applicant_type_code(raw_type_code, raw_type_text, app_type)
    app_id_type = _normalize_id_type_code(raw_id_type_code, raw_id_type_text, app_id_type)
    if app_name is None:
        app_name = ""
    if app_type is None:
        app_type = ""
    if app_id_no is None:
        app_id_no = ""
    if app_email is None:
        app_email = ""
    if app_province is None:
        app_province = ""
    if app_city is None:
        app_city = ""
    if app_address is None:
        app_address = ""
    if app_zip is None:
        app_zip = ""
    if app_phone is None:
        app_phone = ""
    etree.SubElement(first_app, "姓名或名称").text = str(app_name)
    etree.SubElement(first_app, "申请人类型").text = str(app_type)
    etree.SubElement(first_app, "用户代码").text = ""
    etree.SubElement(first_app, "身份证件号码或统一社会信用代码").text = str(app_id_no)
    etree.SubElement(first_app, "电子邮箱").text = str(app_email)
    etree.SubElement(first_app, "国籍或总部所在地").text = "CN"
    etree.SubElement(first_app, "经营所在地或营业所在地").text = "CN"
    etree.SubElement(first_app, "省自治区直辖市名称").text = str(app_province)
    etree.SubElement(first_app, "市县名称").text = str(app_city)
    etree.SubElement(first_app, "城区乡街道门牌号").text = str(app_address)
    etree.SubElement(first_app, "邮政编码").text = str(app_zip)
    etree.SubElement(first_app, "电话").text = str(app_phone)
    etree.SubElement(first_app, "英文名称").text = ""
    etree.SubElement(first_app, "英文地址").text = ""
    etree.SubElement(first_app, "证件类型").text = str(app_id_type)
    fee_node = etree.SubElement(first_app, "费减备案")
    fee_val = "1"
    if fee_flag is not None:
        fee_val = "1" if fee_flag else "0"
    etree.SubElement(fee_node, "附加").text = fee_val

    # 其他申请人：若上游提供了多个申请人，则从第二个开始依次生成，顺序从 1 计数。
    if isinstance(app_list, list) and len(app_list) > 1:
        order = 1
        for extra in app_list[1:]:
            if not isinstance(extra, dict):
                continue
            other_app = etree.SubElement(applicants, "其他申请人", 顺序=str(order))
            e_name = ""
            e_type = ""
            e_id_no = ""
            e_email = ""
            e_province = ""
            e_city = ""
            e_address = ""
            e_zip = ""
            e_phone = ""
            e_id_type = ""
            raw_e_type_code = None
            raw_e_type_text = None
            raw_e_id_type_code = None
            raw_e_id_type_text = None
            e_name = extra.get("name", e_name)
            raw_e_type_code = extra.get("type_code")
            raw_e_type_text = extra.get("type")
            e_id_no = extra.get("id_no", e_id_no)
            e_email = extra.get("email", e_email)
            e_province = extra.get("province_code", extra.get("province", e_province))
            city_val2 = extra.get("city_code", extra.get("city", e_city))
            district_val2 = extra.get("district_code", extra.get("district"))
            if district_val2 and not city_val2:
                city_val2 = district_val2
            e_city = city_val2
            e_address = extra.get("address", e_address)
            e_zip = extra.get("zip", e_zip)
            e_phone = extra.get("phone", e_phone)
            raw_e_id_type_code = extra.get("id_type_code")
            raw_e_id_type_text = extra.get("id_type")
            e_type = _normalize_applicant_type_code(raw_e_type_code, raw_e_type_text, e_type)
            e_id_type = _normalize_id_type_code(raw_e_id_type_code, raw_e_id_type_text, e_id_type)
            if e_name is None:
                e_name = ""
            if e_type is None:
                e_type = ""
            if e_id_no is None:
                e_id_no = ""
            if e_email is None:
                e_email = ""
            if e_province is None:
                e_province = ""
            if e_city is None:
                e_city = ""
            if e_address is None:
                e_address = ""
            if e_zip is None:
                e_zip = ""
            if e_phone is None:
                e_phone = ""
            etree.SubElement(other_app, "姓名或名称").text = str(e_name)
            etree.SubElement(other_app, "申请人类型").text = str(e_type)
            etree.SubElement(other_app, "用户代码").text = ""
            etree.SubElement(other_app, "身份证件号码或统一社会信用代码").text = str(e_id_no)
            etree.SubElement(other_app, "电子邮箱").text = str(e_email)
            etree.SubElement(other_app, "国籍或总部所在地").text = "CN"
            etree.SubElement(other_app, "经营所在地或营业所在地").text = "CN"
            etree.SubElement(other_app, "省自治区直辖市名称").text = str(e_province)
            etree.SubElement(other_app, "市县名称").text = str(e_city)
            etree.SubElement(other_app, "城区乡街道门牌号").text = str(e_address)
            etree.SubElement(other_app, "邮政编码").text = str(e_zip)
            etree.SubElement(other_app, "电话").text = str(e_phone)
            etree.SubElement(other_app, "英文名称").text = ""
            etree.SubElement(other_app, "英文地址").text = ""
            etree.SubElement(other_app, "证件类型").text = str(e_id_type)
            order += 1

    etree.SubElement(root, "代表人").text = "1"

    contact = etree.SubElement(root, "联系人")
    c_name = ""
    c_phone = ""
    c_email = ""
    c_zip = ""
    c_province = ""
    c_city = ""
    c_street = ""
    if agency_enabled:
        contact_ri = {}
        c_name = ""
        c_phone = ""
        c_email = ""
        c_zip = ""
        c_province = ""
        c_city = ""
        c_street = ""
    if isinstance(contact_ri, dict):
        c_name = contact_ri.get("name", c_name)
        c_phone = contact_ri.get("phone", c_phone)
        c_email = contact_ri.get("email", c_email)
        c_zip = contact_ri.get("zip", c_zip)
        # 兼容旧字段 "province"/"city" 与新版 "province_code"/"city_code"
        c_province = contact_ri.get("province_code", contact_ri.get("province", c_province))
        c_city = contact_ri.get("city_code", contact_ri.get("city", c_city))
        c_street = contact_ri.get("street", c_street)
    if c_name is None:
        c_name = ""
    if c_phone is None:
        c_phone = ""
    if c_email is None:
        c_email = ""
    if c_zip is None:
        c_zip = ""
    if c_province is None:
        c_province = ""
    if c_city is None:
        c_city = ""
    if c_street is None:
        c_street = ""
    etree.SubElement(contact, "姓名").text = str(c_name)
    etree.SubElement(contact, "电话").text = str(c_phone)
    etree.SubElement(contact, "电子邮箱").text = str(c_email)
    etree.SubElement(contact, "邮政编码").text = str(c_zip)
    etree.SubElement(contact, "省自治区直辖市名称").text = str(c_province)
    etree.SubElement(contact, "市县名称").text = str(c_city)
    etree.SubElement(contact, "城区乡街道门牌号").text = str(c_street)

    agency = etree.SubElement(root, "专利代理机构")
    agency_name = ""
    agency_code = ""
    agent1_name = ""
    agent1_cert = ""
    agent1_phone = ""
    agent2_name = ""
    agent2_cert = ""
    agent2_phone = ""
    if agency_enabled and isinstance(agency_info, dict):
        agency_name = str(agency_info.get("name") or "")
        agency_code = str(agency_info.get("code") or "")
        a1 = agency_info.get("agent1") if isinstance(agency_info.get("agent1"), dict) else {}
        a2 = agency_info.get("agent2") if isinstance(agency_info.get("agent2"), dict) else {}
        agent1_name = str(a1.get("name") or "")
        agent1_cert = str(a1.get("cert_no") or "")
        agent1_phone = str(a1.get("phone") or "")
        agent2_name = str(a2.get("name") or "")
        agent2_cert = str(a2.get("cert_no") or "")
        agent2_phone = str(a2.get("phone") or "")

    etree.SubElement(agency, "名称").text = agency_name
    etree.SubElement(agency, "代码").text = agency_code
    stmt = etree.SubElement(agency, "声明已经与申请人签订了专利代理委托书且本表中的信息与委托书中相应信息一致")
    etree.SubElement(stmt, "附加").text = "1" if agency_enabled else "0"
    agent1 = etree.SubElement(agency, "代理师", 顺序="1")
    etree.SubElement(agent1, "姓名").text = agent1_name
    etree.SubElement(agent1, "资格证号").text = agent1_cert
    etree.SubElement(agent1, "电话").text = agent1_phone
    agent2 = etree.SubElement(agency, "代理师", 顺序="2")
    etree.SubElement(agent2, "姓名").text = agent2_name
    etree.SubElement(agent2, "资格证号").text = agent2_cert
    etree.SubElement(agent2, "电话").text = agent2_phone

    div_app = etree.SubElement(root, "分案申请")
    etree.SubElement(div_app, "原申请号")
    etree.SubElement(div_app, "针对的分案申请号")
    orig_date = etree.SubElement(div_app, "原申请日")
    etree.SubElement(orig_date, "年")
    etree.SubElement(orig_date, "月")
    etree.SubElement(orig_date, "日")

    etree.SubElement(root, "要求优先权声明")

    ref_stmt = etree.SubElement(root, "援引加入声明")
    etree.SubElement(ref_stmt, "附加").text = "0"

    novelty = etree.SubElement(root, "不丧失新颖性申明颖性申明")
    sec1 = etree.SubElement(novelty, "已在国家出现紧急状态或者非常情况时为公共利益目的首次公开")
    etree.SubElement(sec1, "附加").text = "0"
    sec2 = etree.SubElement(novelty, "已在中国政府主办或承认的国际展览会上首次展出")
    etree.SubElement(sec2, "附加").text = "0"
    sec3 = etree.SubElement(novelty, "已在规定的学术会议或技术会议上首次发表")
    etree.SubElement(sec3, "附加").text = "0"
    sec4 = etree.SubElement(novelty, "他人未经申请人同意而泄露其内容")
    etree.SubElement(sec4, "附加").text = "0"

    same_day = etree.SubElement(root, "同日申请")
    same_stmt = etree.SubElement(same_day, "声明本实用新型在同日申请发明专利")
    etree.SubElement(same_stmt, "附加").text = "0"

    # 摘要附图：缺失则留空；若本案无说明书附图，则图号置空。
    abs_figure_no_text = None
    has_new_abstract = False
    if isinstance(ri, dict) and "abstract_figure_no" in ri:
        has_new_abstract = True
        val = ri.get("abstract_figure_no")
        if val is not None:
            val_str = str(val).strip()
            if val_str:
                abs_figure_no_text = val_str

    abs_fig = etree.SubElement(root, "摘要附图")
    abs_no_val = ""
    if has_new_abstract and abs_figure_no_text and has_drawings:
        abs_no_val = abs_figure_no_text
    if not has_drawings:
        abs_no_val = ""
    etree.SubElement(abs_fig, "图号").text = abs_no_val

    active_mod = etree.SubElement(root, "主动修改")
    give_up = etree.SubElement(active_mod, "声明本申请人放弃专利主动修改权利")
    etree.SubElement(give_up, "附加").text = ""

    delay = etree.SubElement(root, "延迟审查")
    delay_one = etree.SubElement(delay, "延迟审查一年")
    etree.SubElement(delay_one, "附加").text = "0"

    file_list = etree.SubElement(root, "申请文件清单")
    file_info = etree.SubElement(file_list, "申请文件信息")

    files = [
        ("1", "实用新型专利请求书", "120101", ""),
        ("2", "说明书摘要", "100004", ""),
        ("3", "权利要求书", "100001", ""),
        ("4", "说明书", "100002", ""),
    ]
    if has_drawings:
        files.append(("5", "说明书附图", "100003", ""))
    for order, name, code, pages in files:
        item = etree.SubElement(file_info, "申请文件", 顺序=order)
        etree.SubElement(item, "文件名称").text = name
        etree.SubElement(item, "表格代码").text = code
        etree.SubElement(item, "页数").text = pages

    etree.SubElement(file_list, "项数").text = ""

    extra_list = etree.SubElement(root, "附加文件清单")
    poa_values = []
    try:
        if agency_enabled and isinstance(app_list, list):
            seen = set()
            dup = set()
            for a in app_list:
                if not isinstance(a, dict):
                    continue
                v = str(a.get("power_of_attorney_no") or "").strip()
                if not v:
                    continue
                if v in seen:
                    dup.add(v)
                    continue
                seen.add(v)
                poa_values.append(v)
            if dup:
                raise ValueError(
                    "发现重复的总委托书编号(POA)，同一申请内不可重复，已阻止生成请求书 XML：\n"
                    + "\n".join([f"- {d}" for d in sorted(dup)])
                )
    except Exception:
        poa_values = []

    if not agency_enabled or not poa_values:
        etree.SubElement(extra_list, "总委托书编号", 顺序="1").text = ""
    else:
        order = 1
        for v in poa_values:
            etree.SubElement(extra_list, "总委托书编号", 顺序=str(order)).text = str(v)
            order += 1
    etree.SubElement(extra_list, "备案编号").text = ""

    sign = etree.SubElement(root, "申请人或代理机构签章")
    etree.SubElement(sign, "签章").text = ""
    sign_date = etree.SubElement(sign, "签章日期")
    etree.SubElement(sign_date, "年").text = ""
    etree.SubElement(sign_date, "月").text = ""
    etree.SubElement(sign_date, "日").text = ""

    approval = etree.SubElement(root, "专利局审批")
    etree.SubElement(approval, "意见内容")
    submit_date = etree.SubElement(approval, "提出日期")
    etree.SubElement(submit_date, "年").text = ""
    etree.SubElement(submit_date, "月").text = ""
    etree.SubElement(submit_date, "日").text = ""

    tree = etree.ElementTree(root)
    out_dir = os.path.join(case_root, "120101")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "120101.xml")
    tree.write(out_path, encoding="UTF-8", xml_declaration=True, pretty_print=True)
    logger.info(f"💾 120101.xml 已生成: {out_path}")
    return out_path


__all__ = ["create_120101_xml"]
