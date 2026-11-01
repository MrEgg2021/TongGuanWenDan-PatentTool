from __future__ import annotations

import re
from typing import Any, Dict, Optional

from core.config import load_config
from core.logging_utils import logger
from core.word_engine import WordEngine

from .region_infer import _attach_region_codes
from .text_utils import _strip_cell_text


def parse_request_info(input_file, config_path=None):
    """解析文档中的“申请信息确认页”表格，提取请求书相关信息。

    仅用于单文件模式的请求书表单预填：
    - 若找不到对应分节 / 表格结构不符合预期，返回 None
    - 若能部分解析，则返回包含 patent_type/inventors/applicants/contact/title 的字典

    附加行为（向后兼容）：
    - 同时尝试从“说明书”分节中提取专利名称（首段文本），用于 request_info['title']，
      便于在 UI 中预填“专利名称”；即使没有“申请信息确认页”，只要说明书存在首段标题，
      也会返回仅包含 title 的 request_info，而不再直接返回 None。
    """
    if config_path is None:
        config = load_config()
    else:
        config = load_config(config_path)

    word_engine = WordEngine(config['word_engine'])
    try:
        word_engine.start_app()
        word_engine.open_doc(input_file)
        doc = word_engine.doc

        sections = doc.Sections
        section_count = sections.Count
        req_section = None
        desc_section = None

        # 1. 查找页眉包含“申请信息确认页”的分节，同时顺带记录“说明书”分节
        for i in range(1, section_count + 1):
            sec = sections(i)
            for h_idx in [1, 2, 3]:
                try:
                    header = sec.Headers(h_idx)
                    raw = header.Range.Text or ""
                except Exception:
                    continue
                norm = re.sub(r"\s+", "", str(raw))
                if not norm:
                    continue

                if req_section is None and "申请信息确认页" in norm:
                    req_section = sec

                # 说明书分节：包含“说明书”但不包含“附图”/“摘要”等关键字
                if desc_section is None and ("说明书" in norm or "说明书" in norm):
                    if "附图" in norm or "摘要" in norm:
                        continue
                    desc_section = sec

        # 2. 从“说明书”分节中尝试提取标题（首段正文文本）
        title_text: Optional[str] = None
        if desc_section is not None:
            try:
                paras = desc_section.Range.Paragraphs
                count = getattr(paras, "Count", 0) or 0
                for idx in range(1, count + 1):
                    try:
                        para = paras(idx)
                    except Exception:
                        continue
                    text = _strip_cell_text(para.Range)
                    if text:
                        title_text = text
                        break
            except Exception:
                title_text = None

        # 若完全没有“申请信息确认页”分节，但成功解析出说明书标题，则仅返回 title 供 UI 预填
        if req_section is None:
            if title_text:
                logger.info(
                    "[REQ_FORM] 未找到‘申请信息确认页’分节，仅从说明书解析到专利名称: %s",
                    title_text,
                )
                return {
                    "patent_type_raw": None,
                    "patent_type": None,
                    "title": title_text,
                    "inventors": [],
                    "applicants": [],
                    "contact": {},
                }

            logger.info("[REQ_FORM] 未找到‘申请信息确认页’对应的分节，跳过解析。")
            return None

        tables = req_section.Range.Tables
        if tables.Count < 1:
            logger.info("[REQ_FORM] ‘申请信息确认页’分节中未找到表格，跳过解析。")
            return None

        table = tables(1)
        rows = table.Rows.Count

        request_info: Dict[str, Any] = {
            "patent_type_raw": None,
            "patent_type": None,
            "title": title_text,
            "inventors": [],
            "applicants": [],
            "contact": {},
        }

        inventors = request_info["inventors"]
        applicants = request_info["applicants"]
        contact = request_info["contact"]
        inv_names: list[str] = []
        inv_ids: list[str] = []
        current_applicant_idx: Optional[int] = None
        applicant_multi_mode = False
        skip_extra_applicant = False

        def _new_applicant() -> Dict[str, Any]:
            return {
                "name": "",
                "type": "",
                "id_type": "",
                "id_no": "",
                "province": "",
                "city": "",
                "district": "",
                "address": "",
                "zip": "",
                "email": "",
                "phone": "",
            }

        def _split_multi_values(text: Any) -> list[str]:
            if text is None:
                return []
            try:
                s = str(text)
            except Exception:
                return []
            s = s.strip()
            if not s:
                return []
            parts = [p.strip() for p in re.split(r"[;；]+", s)]
            return [p for p in parts if p]

        def _ensure_applicants(n: int) -> None:
            nonlocal current_applicant_idx
            n = max(0, min(int(n), 5))
            while len(applicants) < n:
                applicants.append(_new_applicant())
            if current_applicant_idx is None and applicants:
                current_applicant_idx = 0

        for r in range(1, rows + 1):
            try:
                row = table.Rows(r)
            except Exception:
                continue

            try:
                label = _strip_cell_text(row.Cells(1))
                value = _strip_cell_text(row.Cells(2))
            except Exception:
                continue

            if not label:
                continue

            # 0) 专利名称（若表格中显式给出，则优先使用该值覆盖说明书首段推断）
            if label == "专利名称":
                if value:
                    request_info["title"] = value
                continue

            # 1) 专利类型
            if label == "专利类型":
                request_info["patent_type_raw"] = value or ""
                if value:
                    norm = re.sub(r"\s+", "", value)
                    if "实用" in norm:
                        request_info["patent_type"] = "utility_model"
                    elif "发明" in norm:
                        request_info["patent_type"] = "invention"
                continue

            # 2) 发明人信息（支持单元格内多值拆分）
            if label == "发明人姓名":
                parts = [p.strip() for p in re.split(r"[;,，；、]+", value or "") if p.strip()]
                inv_names.extend(parts)
                continue
            if label == "发明人身份证号码":
                parts = [p.strip() for p in re.split(r"[;,，；、]+", value or "") if p.strip()]
                inv_ids.extend(parts)
                continue

            # 3) 申请人信息（支持多申请人）
            if label == "申请人名称":
                parts = _split_multi_values(value)
                if len(parts) > 1:
                    applicant_multi_mode = True
                    skip_extra_applicant = False
                    n = min(len(parts), 5)
                    _ensure_applicants(n)
                    for i in range(n):
                        applicants[i]["name"] = parts[i]
                    current_applicant_idx = 0
                    if len(parts) > 5:
                        logger.info("[REQ_FORM] 申请人名称超过 5 个，仅取前 5 个。")
                else:
                    if applicant_multi_mode:
                        _ensure_applicants(1)
                        applicants[0]["name"] = value or ""
                        current_applicant_idx = 0
                    else:
                        if len(applicants) >= 5:
                            skip_extra_applicant = True
                            logger.info("[REQ_FORM] 申请人数量超过 5 个，后续申请人信息将被忽略。")
                            continue
                        skip_extra_applicant = False
                        applicants.append(_new_applicant())
                        current_applicant_idx = len(applicants) - 1
                        applicants[current_applicant_idx]["name"] = value or ""
                continue

            applicant_label_to_key: Dict[str, str] = {
                "申请人类型": "type",
                "申请人证件类型": "id_type",
                "申请人证件号码": "id_no",
                "申请人详细地址": "address",
                "申请人邮编": "zip",
                "申请人电子邮箱": "email",
                "申请人联系电话": "phone",
                "申请人电话": "phone",
                "申请人省": "province",
                "申请人市/区": "city",
                "申请人市县名称": "city",
                "申请人区": "district",
                "申请人区县": "district",
            }

            if label in applicant_label_to_key:
                key = applicant_label_to_key[label]
                parts = _split_multi_values(value)
                if len(parts) > 1:
                    applicant_multi_mode = True
                    skip_extra_applicant = False
                    n = min(len(parts), 5)
                    _ensure_applicants(n)
                    for i in range(n):
                        applicants[i][key] = parts[i]
                    if len(parts) > 5:
                        logger.info("[REQ_FORM] %s 超过 5 个值，仅取前 5 个。", label)
                else:
                    if skip_extra_applicant and (not applicant_multi_mode):
                        continue
                    if not applicants:
                        if (value or "").strip():
                            _ensure_applicants(1)
                            current_applicant_idx = 0
                        else:
                            continue
                    target_idx = 0
                    if not applicant_multi_mode:
                        if current_applicant_idx is not None:
                            target_idx = current_applicant_idx
                    if 0 <= target_idx < len(applicants):
                        applicants[target_idx][key] = value or ""
                continue

            # 4) 联系人信息（单个联系人）
            if label == "联系人姓名":
                contact["name"] = value or ""
                continue
            if label == "联系人电话":
                contact["phone"] = value or ""
                continue
            if label == "联系人电子邮箱":
                contact["email"] = value or ""
                continue
            if label == "联系人城区乡街道门牌号":
                contact["street"] = value or ""
                continue
            if label == "联系人邮编":
                contact["zip"] = value or ""
                continue

            if label == "费减备案":
                v = (value or "").strip()
                if v:
                    norm = re.sub(r"\s+", "", v).lower()
                    pos = any(tok in norm for tok in ("是", "享受", "有", "y", "1", "true"))
                    neg = any(tok in norm for tok in ("否", "不", "无", "n", "0", "false"))
                    if pos and not neg:
                        request_info["fee_reduction_enabled"] = True
                    elif neg and not pos:
                        request_info["fee_reduction_enabled"] = False
                continue

            if label == "摘要附图图号":
                v = (value or "").strip()
                if v:
                    request_info["abstract_figure_no"] = v
                continue

        # 发明人数量与证件号配对（不在此处做校验，统一交由弹窗确认时校验）
        if inv_names or inv_ids:
            max_len = max(len(inv_names), len(inv_ids))
            for idx in range(max_len):
                name_val = inv_names[idx] if idx < len(inv_names) else ""
                id_val = inv_ids[idx] if idx < len(inv_ids) else ""
                # 若两者均为空则忽略
                if not name_val and not id_val:
                    continue
                inventors.append({"name": name_val, "id_no": id_val})

        # 判断是否解析出了有效信息
        has_any = False
        if request_info.get("patent_type"):
            has_any = True
        if not has_any:
            for inv in inventors:
                if inv.get("name") or inv.get("id_no"):
                    has_any = True
                    break
        if not has_any:
            for app in applicants:
                if any(v for v in app.values()):
                    has_any = True
                    break
        if not has_any and any(contact.get(k) for k in contact):
            has_any = True

        if not has_any:
            logger.info("[REQ_FORM] ‘申请信息确认页’表格存在，但所有已识别字段均为空，视为无效。")
            return None

        # 尝试根据中文省/市名称补全行政区划代码，供请求书弹窗与 XML 使用
        _attach_region_codes(request_info)

        try:
            request_info["_source_file"] = input_file
        except Exception:
            pass
        logger.info(f"[REQ_FORM] 解析结果: {request_info}")
        return request_info
    finally:
        try:
            word_engine.quit_app()
        except Exception:
            pass


__all__ = ["parse_request_info"]
