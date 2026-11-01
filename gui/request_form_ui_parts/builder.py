from __future__ import annotations

def build_request_form_payload(parsed_info, current_patent_type):
    """构建请求书表单预填 payload。"""

    inv_name = ""
    inv_id_no = ""
    app_name = ""
    app_type = ""
    app_id_no = ""
    app_province = ""
    app_city = ""
    app_address = ""
    app_zip = ""
    app_phone = ""
    app_email = ""
    contact_name = ""
    contact_phone = ""
    contact_email = ""
    contact_province = ""
    contact_city = ""
    contact_street = ""
    contact_zip = ""
    abstract_figure_no = None

    app_province_code = ""
    app_city_code = ""
    contact_province_code = ""
    contact_city_code = ""

    app_type_code = ""
    app_id_type = ""
    app_id_type_code = ""

    title = None
    if isinstance(parsed_info, dict):
        # 兼容 parse_request_info 新增的 title 字段（专利名称）
        tval = parsed_info.get("title")
        if isinstance(tval, str) and tval.strip():
            title = tval.strip()

    if isinstance(parsed_info, dict):
        inv_list = parsed_info.get("inventors") or []
        if isinstance(inv_list, list) and inv_list:
            inv0 = inv_list[0] or {}
            if isinstance(inv0, dict):
                name_val = inv0.get("name")
                if name_val:
                    inv_name = str(name_val)
                id_val = inv0.get("id_no")
                if id_val:
                    inv_id_no = str(id_val)

        app_list = parsed_info.get("applicants") or []
        if isinstance(app_list, list) and app_list:
            app0 = app_list[0] or {}
            if isinstance(app0, dict):
                name_val = app0.get("name")
                if name_val:
                    app_name = str(name_val)
                type_val = app0.get("type")
                if type_val:
                    t = str(type_val).strip()
                    app_type = t
                    code = ""
                    if "工矿" in t:
                        code = "3"
                    elif "个人" in t:
                        code = "1"
                    elif ("事业" in t and "单位" in t) or ("科研" in t and "机构" in t):
                        code = "2"
                    if not code:
                        for ch in t:
                            if ch.isdigit():
                                code = ch
                                break
                    if code:
                        app_type_code = code
                id_type_val = app0.get("id_type")
                if id_type_val:
                    t = str(id_type_val).strip()
                    app_id_type = t
                    code2 = ""
                    t_upper = t.upper()
                    if "统一社会信用代码" in t or "社会信用代码" in t or "统一社会信用" in t:
                        code2 = "F"
                    elif t_upper.startswith("F-") or t_upper.startswith("F ") or t_upper == "F":
                        code2 = "F"
                    elif "身份证" in t or "居民" in t:
                        code2 = "I"
                    elif t_upper.startswith("I-") or t_upper == "I":
                        code2 = "I"
                    elif "其他" in t:
                        code2 = "O"
                    elif t_upper.startswith("O-") or t_upper == "O":
                        code2 = "O"
                    if code2:
                        app_id_type_code = code2
                id_val = app0.get("id_no")
                if id_val:
                    app_id_no = str(id_val)
                prov_val = app0.get("province")
                if prov_val:
                    app_province = str(prov_val)
                city_val = app0.get("city") or ""
                district_val = app0.get("district") or ""
                if district_val and not city_val:
                    city_val = district_val
                if city_val:
                    app_city = str(city_val)
                # 尽量使用解析出的行政区划代码
                prov_code_val = app0.get("province_code")
                if prov_code_val:
                    app_province_code = str(prov_code_val)
                city_code_val = app0.get("city_code") or app0.get("district_code")
                if city_code_val:
                    app_city_code = str(city_code_val)
                addr_val = app0.get("address")
                if addr_val:
                    app_address = str(addr_val)
                zip_val = app0.get("zip")
                if zip_val:
                    app_zip = str(zip_val)
                phone_val = app0.get("phone")
                if phone_val:
                    app_phone = str(phone_val)
                email_val = app0.get("email")
                if email_val:
                    app_email = str(email_val)

        contact = parsed_info.get("contact") or {}
        if isinstance(contact, dict):
            val = contact.get("name")
            if val:
                contact_name = str(val)
            val = contact.get("phone")
            if val:
                contact_phone = str(val)
            val = contact.get("email")
            if val:
                contact_email = str(val)
            val = contact.get("province")
            if val:
                contact_province = str(val)
            val = contact.get("city")
            if val:
                contact_city = str(val)
            c_prov_code = contact.get("province_code")
            if c_prov_code:
                contact_province_code = str(c_prov_code)
            c_city_code = contact.get("city_code")
            if c_city_code:
                contact_city_code = str(c_city_code)
            val = contact.get("street")
            if val:
                contact_street = str(val)
            val = contact.get("zip")
            if val:
                contact_zip = str(val)
        # 支持多发明人/多申请人，供各 Tab 渲染
        inventors_list = []
        applicants_list = []

        raw_inv_list = parsed_info.get("inventors") or []
        if isinstance(raw_inv_list, list) and raw_inv_list:
            for idx, inv in enumerate(raw_inv_list):
                if not isinstance(inv, dict):
                    inv = {}
                name_val = inv.get("name")
                id_val = inv.get("id_no")
                nat_val = inv.get("nationality_code", "CN") or "CN"
                publish_flag = bool(inv.get("publish_not_public"))
                if idx == 0:
                    name = str(name_val) if name_val else inv_name
                    id_no = str(id_val) if id_val else inv_id_no
                else:
                    name = str(name_val) if name_val else ""
                    id_no = str(id_val) if id_val else ""
                inventors_list.append(
                    {
                        "name": name,
                        "id_no": id_no,
                        "nationality_code": str(nat_val) if nat_val else "CN",
                        "publish_not_public": publish_flag,
                    }
                )

        raw_app_list = parsed_info.get("applicants") or []
        if isinstance(raw_app_list, list) and raw_app_list:
            for idx, app in enumerate(raw_app_list):
                if not isinstance(app, dict):
                    app = {}
                poa_no = ""
                try:
                    poa_no = str(app.get("power_of_attorney_no") or "").strip()
                except Exception:
                    poa_no = ""
                if idx == 0:
                    # 第一申请人优先使用已归一化后的字段
                    item = {
                        "name": app_name,
                        "type": app_type,
                        "type_code": app_type_code,
                        "id_type": app_id_type,
                        "id_type_code": app_id_type_code,
                        "id_no": app_id_no,
                        "province": app_province,
                        "city": app_city,
                        "district": "",
                        "address": app_address,
                        "zip": app_zip,
                        "email": app_email,
                        "phone": app_phone,
                        "province_code": app_province_code,
                        "city_code": app_city_code,
                        "power_of_attorney_no": poa_no,
                    }
                else:
                    name_val = app.get("name")
                    type_val = app.get("type")
                    id_type_val = app.get("id_type")
                    id_val = app.get("id_no")
                    prov_val = app.get("province")
                    city_val = app.get("city") or app.get("district")
                    prov_code_val = app.get("province_code")
                    city_code_val = app.get("city_code") or app.get("district_code")
                    addr_val = app.get("address")
                    zip_val = app.get("zip")
                    email_val = app.get("email")
                    phone_val = app.get("phone")
                    item = {
                        "name": str(name_val) if name_val else "",
                        "type": str(type_val) if type_val else "",
                        "type_code": "",
                        "id_type": str(id_type_val) if id_type_val else "",
                        "id_type_code": "",
                        "id_no": str(id_val) if id_val else "",
                        "province": str(prov_val) if prov_val else "",
                        "city": str(city_val) if city_val else "",
                        "district": "",
                        "address": str(addr_val) if addr_val else "",
                        "zip": str(zip_val) if zip_val else "",
                        "email": str(email_val) if email_val else "",
                        "phone": str(phone_val) if phone_val else "",
                        "province_code": str(prov_code_val) if prov_code_val else "",
                        "city_code": str(city_code_val) if city_code_val else "",
                        "power_of_attorney_no": poa_no,
                    }
                applicants_list.append(item)

    if not locals().get("inventors_list"):
        inventors_list = [
            {
                "name": "",
                "id_no": "",
                "nationality_code": "CN",
                "publish_not_public": False,
            }
        ]

    if not locals().get("applicants_list"):
        applicants_list = [
            {
                "name": "",
                "type": "",
                "type_code": "",
                "id_type": "",
                "id_type_code": "",
                "id_no": "",
                "province": "",
                "city": "",
                "district": "",
                "address": "",
                "zip": "",
                "email": "",
                "phone": "",
                "province_code": "",
                "city_code": "",
            }
        ]

    val = parsed_info.get("abstract_figure_no") if isinstance(parsed_info, dict) else None
    if val:
        abstract_figure_no = str(val)

    agency_enabled = False
    early_publication_enabled = True
    substantive_exam_enabled = True
    power_of_attorney_no = None
    if isinstance(parsed_info, dict):
        if "agency_enabled" in parsed_info:
            try:
                agency_enabled = bool(parsed_info.get("agency_enabled"))
            except Exception:
                agency_enabled = False
        if "early_publication_enabled" in parsed_info:
            try:
                early_publication_enabled = bool(parsed_info.get("early_publication_enabled"))
            except Exception:
                early_publication_enabled = False
        if "substantive_exam_enabled" in parsed_info:
            try:
                substantive_exam_enabled = bool(parsed_info.get("substantive_exam_enabled"))
            except Exception:
                substantive_exam_enabled = True
        if "power_of_attorney_no" in parsed_info:
            val2 = parsed_info.get("power_of_attorney_no")
            if val2 is not None:
                txt = str(val2).strip()
                power_of_attorney_no = txt or None

    if current_patent_type == "utility_model":
        early_publication_enabled = False
        substantive_exam_enabled = False

    agency_info = None
    if isinstance(parsed_info, dict):
        a0 = parsed_info.get("agency_info")
        if isinstance(a0, dict) and a0:
            agency_info = a0

    request_info = {
        "patent_type": current_patent_type,
        # title 作为 request_info 顶层字段，供后续流程复用
        "title": title,
        "inventors": inventors_list,
        "applicants": applicants_list,
        "contact": {
            "name": contact_name,
            "phone": contact_phone,
            "email": contact_email,
            "province": contact_province,
            "city": contact_city,
            "street": contact_street,
            "zip": contact_zip,
            "province_code": contact_province_code,
            "city_code": contact_city_code,
        },
        "agency_enabled": agency_enabled,
        "early_publication_enabled": early_publication_enabled,
        "substantive_exam_enabled": substantive_exam_enabled,
    }
    if agency_info is not None:
        request_info["agency_info"] = agency_info
    if abstract_figure_no is not None:
        request_info["abstract_figure_no"] = abstract_figure_no
    if power_of_attorney_no is not None:
        request_info["power_of_attorney_no"] = power_of_attorney_no
    return request_info
