import os
import tempfile
import zipfile
from typing import Any, Optional

from lxml import etree

from .text_utils import _norm_text


def _zip_entry_basename(name: str) -> str:
    try:
        rel = str(name or "").replace("\\", "/")
        return os.path.basename(rel)
    except Exception:
        return ""


def _find_request_form_xml_in_zip(
    zip_path: str,
    *,
    max_depth: int = 6,
    temp_files: list[str] | None = None,
) -> tuple[str | None, bytes | None]:
    if temp_files is None:
        temp_files = []
    if max_depth <= 0:
        return None, None

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            infos = [it for it in zf.infolist() if it.filename and (not it.is_dir())]
            for info in infos:
                base = _zip_entry_basename(info.filename)
                if base in ("110101.xml", "120101.xml"):
                    try:
                        return base, zf.read(info.filename)
                    except Exception:
                        return None, None

            for info in infos:
                base = _zip_entry_basename(info.filename)
                if not base.lower().endswith(".zip"):
                    continue
                try:
                    data = zf.read(info.filename)
                except Exception:
                    continue
                if not data:
                    continue
                fd, tmp_path = tempfile.mkstemp(suffix=".zip")
                os.close(fd)
                try:
                    with open(tmp_path, "wb") as f:
                        f.write(data)
                    temp_files.append(tmp_path)
                except Exception:
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
                    continue

                found_name, found_data = _find_request_form_xml_in_zip(
                    tmp_path,
                    max_depth=max_depth - 1,
                    temp_files=temp_files,
                )
                if found_name and found_data:
                    return found_name, found_data
    except Exception:
        return None, None

    return None, None


def _xml_text(node, path: str) -> str:
    if node is None:
        return ""
    try:
        val = node.findtext(path)
        return _norm_text(val)
    except Exception:
        return ""


def _applicant_type_text_from_code(code: str) -> str:
    c = _norm_text(code)
    if c == "3":
        return "工矿企业"
    if c == "1":
        return "个人"
    if c == "2":
        return "事业单位/科研机构"
    return c


def _applicant_id_type_text_from_code(code: str) -> str:
    c = _norm_text(code).upper()
    if c.startswith("F"):
        return "统一社会信用代码"
    if c.startswith("I"):
        return "身份证"
    if c.startswith("O") or c == "0":
        return "其他"
    return _norm_text(code) or ""


def _parse_xml_root(xml_bytes: bytes):
    try:
        return etree.fromstring(xml_bytes)
    except Exception:
        return None


def _collect_ordered_nodes(parent, *, first_tag: str, other_tag: str) -> list[Any]:
    nodes: list[tuple[int, Any]] = []
    first = None
    try:
        first = parent.find(first_tag)
    except Exception:
        first = None
    if first is not None:
        nodes.append((0, first))

    others = []
    try:
        others = parent.findall(other_tag)
    except Exception:
        others = []
    for it in others or []:
        try:
            order = int(_norm_text(it.get("顺序")) or "0")
        except Exception:
            order = 0
        nodes.append((order, it))

    try:
        nodes = sorted(nodes, key=lambda x: int(x[0]))
    except Exception:
        pass
    return [node for _order, node in nodes]


def _parse_inventor_id_type(node) -> str:
    raw = _xml_text(node, "证件类型")
    if not raw:
        raw = _xml_text(node, "发明人证件类型")
    return _applicant_id_type_text_from_code(raw)


def _parse_inventors(root) -> list[dict]:
    invs: list[dict] = []
    inv_root = None
    try:
        inv_root = root.find("发明人")
    except Exception:
        inv_root = None
    if inv_root is None:
        return invs

    first = None
    try:
        first = inv_root.find("第一发明人")
    except Exception:
        first = None
    if first is not None:
        invs.append(
            {
                "name": _xml_text(first, "姓名"),
                "id_type": _parse_inventor_id_type(first),
                "id_type_code": "",
                "id_no": _xml_text(first, "身份证件号码"),
                "nationality_code": _xml_text(first, "国籍") or "CN",
                "publish_not_public": _xml_text(first, "请求不公开/附加") == "1",
            }
        )

    others = []
    try:
        others = inv_root.findall("其他发明人")
    except Exception:
        others = []
    try:
        others = sorted(
            [o for o in others if o is not None],
            key=lambda x: int(_norm_text(x.get("顺序")) or "0"),
        )
    except Exception:
        pass
    for it in others or []:
        invs.append(
            {
                "name": _xml_text(it, "姓名"),
                "id_type": _parse_inventor_id_type(it),
                "id_type_code": "",
                "id_no": _xml_text(it, "身份证件号码"),
                "nationality_code": _xml_text(it, "国籍") or "CN",
                "publish_not_public": _xml_text(it, "请求不公开/附加") == "1",
            }
        )
    return invs


def _parse_applicants(root) -> tuple[list[dict], Optional[bool]]:
    apps: list[dict] = []
    fee_reduction_enabled: Optional[bool] = None
    app_root = None
    try:
        app_root = root.find("申请人")
    except Exception:
        app_root = None
    if app_root is None:
        return apps, fee_reduction_enabled

    ordered_nodes = _collect_ordered_nodes(app_root, first_tag="第一申请人", other_tag="其他申请人")
    for node in ordered_nodes:
        type_code = _xml_text(node, "申请人类型")
        id_type_code = _xml_text(node, "证件类型")
        id_type_text = _applicant_id_type_text_from_code(id_type_code)
        app = {
            "name": _xml_text(node, "姓名或名称"),
            "type": _applicant_type_text_from_code(type_code),
            "type_code": type_code,
            "id_type": id_type_text,
            "id_type_code": "",
            "id_no": _xml_text(node, "身份证件号码或统一社会信用代码"),
            "province": _xml_text(node, "省自治区直辖市名称"),
            "city": _xml_text(node, "市县名称"),
            "district": "",
            "address": _xml_text(node, "城区乡街道门牌号"),
            "zip": _xml_text(node, "邮政编码"),
            "email": _xml_text(node, "电子邮箱"),
            "phone": _xml_text(node, "电话"),
            "province_code": _xml_text(node, "省自治区直辖市名称"),
            "city_code": _xml_text(node, "市县名称"),
            "district_code": "",
        }
        apps.append(app)

        if fee_reduction_enabled is None:
            raw_fee = _xml_text(node, "费减备案/附加")
            if raw_fee in ("0", "1"):
                fee_reduction_enabled = raw_fee == "1"
    return apps, fee_reduction_enabled


def _parse_contact(root) -> dict:
    c_root = None
    try:
        c_root = root.find("联系人")
    except Exception:
        c_root = None
    if c_root is None:
        return {}
    return {
        "name": _xml_text(c_root, "姓名"),
        "phone": _xml_text(c_root, "电话"),
        "email": _xml_text(c_root, "电子邮箱"),
        "province": _xml_text(c_root, "省自治区直辖市名称"),
        "city": _xml_text(c_root, "市县名称"),
        "street": _xml_text(c_root, "城区乡街道门牌号"),
        "zip": _xml_text(c_root, "邮政编码"),
        "province_code": _xml_text(c_root, "省自治区直辖市名称"),
        "city_code": _xml_text(c_root, "市县名称"),
    }


def _parse_agency_agents(a_root) -> list[dict]:
    agent_nodes = []
    try:
        agent_nodes = a_root.findall("代理师")
    except Exception:
        agent_nodes = []

    ordered: list[tuple[int, Any]] = []
    for n in agent_nodes or []:
        try:
            order = int(_norm_text(n.get("顺序")) or "0")
        except Exception:
            order = 0
        ordered.append((order, n))
    try:
        ordered = sorted(ordered, key=lambda x: int(x[0]))
    except Exception:
        pass

    agents: list[dict] = []
    for order, n in ordered:
        agent_name = _xml_text(n, "姓名")
        cert_no = _xml_text(n, "资格证号")
        phone = _xml_text(n, "电话")
        if not any([agent_name, cert_no, phone]):
            continue
        agents.append({"name": agent_name, "cert_no": cert_no, "phone": phone, "order": int(order)})
    return agents


def _parse_agency(root) -> tuple[Optional[bool], dict | None]:
    agency_info: dict | None = None
    agency_enabled: Optional[bool] = None

    a_root = None
    try:
        a_root = root.find("专利代理机构")
    except Exception:
        a_root = None
    if a_root is None:
        return agency_enabled, agency_info

    a_name = _xml_text(a_root, "名称")
    a_code = _xml_text(a_root, "代码")
    stmt_tag = "声明已经与申请人签订了专利代理委托书且本表中的信息与委托书中相应信息一致"
    stmt_val = _xml_text(a_root, f"{stmt_tag}/附加")
    if stmt_val in ("0", "1"):
        agency_enabled = stmt_val == "1"

    agents = _parse_agency_agents(a_root)
    if a_name or a_code or agents:
        agency_info = {"name": a_name, "code": a_code}
        if agents:
            agency_info["agents"] = agents
            if len(agents) >= 1:
                agency_info["agent1"] = {
                    "name": _norm_text(agents[0].get("name")),
                    "cert_no": _norm_text(agents[0].get("cert_no")),
                    "phone": _norm_text(agents[0].get("phone")),
                    "order": int(agents[0].get("order") or 0),
                }
            if len(agents) >= 2:
                agency_info["agent2"] = {
                    "name": _norm_text(agents[1].get("name")),
                    "cert_no": _norm_text(agents[1].get("cert_no")),
                    "phone": _norm_text(agents[1].get("phone")),
                    "order": int(agents[1].get("order") or 0),
                }
    return agency_enabled, agency_info


def _parse_poa_nos(root) -> list[str]:
    poa_nos: list[str] = []
    extra_root = None
    try:
        extra_root = root.find("附加文件清单")
    except Exception:
        extra_root = None
    if extra_root is None:
        return poa_nos

    nodes = []
    try:
        nodes = extra_root.findall(".//总委托书编号")
    except Exception:
        nodes = []
    for node in nodes or []:
        try:
            poa_text = _norm_text(getattr(node, "text", None))
        except Exception:
            poa_text = ""
        if poa_text:
            poa_nos.append(poa_text)
    return poa_nos


def _parse_request_form_xml_bytes(xml_bytes: bytes, *, patent_type: str) -> dict:
    root = _parse_xml_root(xml_bytes)
    if root is None:
        return {}

    title = _xml_text(root, "发明名称")
    invs = _parse_inventors(root)
    apps, fee_reduction_enabled = _parse_applicants(root)
    contact = _parse_contact(root)
    agency_enabled, agency_info = _parse_agency(root)
    poa_nos = _parse_poa_nos(root)

    out: dict = {
        "patent_type": patent_type,
        "title": title,
        "inventors": invs,
        "applicants": apps,
        "contact": contact,
    }
    if fee_reduction_enabled is not None:
        out["fee_reduction_enabled"] = bool(fee_reduction_enabled)
    if agency_enabled is not None:
        out["agency_enabled"] = bool(agency_enabled)
    if isinstance(agency_info, dict) and agency_info:
        out["agency_info"] = agency_info
    if poa_nos:
        out["_poa_nos_from_xml"] = poa_nos
    return out
