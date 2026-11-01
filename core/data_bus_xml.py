from __future__ import annotations

import os

from lxml import etree

from core.logging_utils import logger


def create_data_bus(case_root, generated_files, invention_title, config, case_id=None, patent_type=None):
    """生成官方格式的 list.xml (data-bus)"""
    bus_cfg = config.get('bus', {}) or {}
    # 优先使用传入的case_id
    if case_id is None:
        case_id = str(bus_cfg.get('case_id', "") or "").strip() or "00000000"
    submission_code = str(bus_cfg.get('submission_code', "") or "")
    internal_no = ""
    default_title = str(bus_cfg.get('invention_title', "") or "")

    if patent_type == "utility_model":
        yewulx = "1"
        main_form_code = "120101"
    else:
        yewulx = "0"
        main_form_code = "110101"

    root = etree.Element("data-bus")

    qingqiu = etree.SubElement(root, "QINGQIUXX")
    etree.SubElement(qingqiu, "DIANZISQAJID").text = case_id
    etree.SubElement(qingqiu, "SHENQINGFS").text = "2"
    etree.SubElement(qingqiu, "YEWULX").text = yewulx
    etree.SubElement(qingqiu, "WENJIANLX").text = "0"
    etree.SubElement(qingqiu, "TIJIAORDM").text = submission_code
    # 发明名称以说明书 XML 中解析到的为准，若没有则退回默认配置
    title_text = invention_title or default_title
    etree.SubElement(qingqiu, "FAMINGMC").text = title_text
    etree.SubElement(qingqiu, "SHENQINGH")
    etree.SubElement(qingqiu, "WEINEIBH")
    etree.SubElement(qingqiu, "GUOJISQH")
    etree.SubElement(qingqiu, "NEIBUBH").text = internal_no
    etree.SubElement(qingqiu, "BAOID")

    wenjianb = etree.SubElement(root, "WENJIANBYSXX")
    baotou = etree.SubElement(wenjianb, "BAOTOUXX")
    etree.SubElement(baotou, "WENJIANBBZ")
    etree.SubElement(baotou, "WENJIANGS").text = str(len(generated_files))

    name_map = {
        "100001": "权利要求书",
        "100002": "说明书",
        "100003": "说明书附图",
        "100004": "说明书摘要",
        "110101": "发明专利请求书",
        "120101": "实用新型专利请求书",
    }

    for folder, xml_name, pages in generated_files:
        display_name = name_map.get(folder, folder)
        # COUNTS：对于 100001（权利要求书），使用 claim 条数，其它文种保持 0
        counts_value = "0"
        if folder == "100001":
            try:
                xml_path = os.path.join(case_root, folder, xml_name)
                tree = etree.parse(xml_path)
                claims = list(tree.iterfind(".//claim"))
                counts_value = str(len(claims))
            except Exception as e:
                logger.warning(f"⚠️ 统计权利要求数量失败，将 COUNTS 置为 0: {e}")

        node = etree.SubElement(wenjianb, "BAONEIWJXX", GUANLIANYWDM=f"YW{main_form_code}")
        etree.SubElement(node, "WENJIANBZ").text = xml_name
        etree.SubElement(node, "GESHILX").text = ".XML"
        etree.SubElement(node, "BIAOGEDM").text = folder
        etree.SubElement(node, "XIANGDUILJ").text = f"{folder}\\{xml_name}"
        etree.SubElement(node, "DTDVersion").text = "1.0"
        etree.SubElement(node, "PAGES").text = str(pages)
        etree.SubElement(node, "COUNTS").text = counts_value
        etree.SubElement(node, "SHIFOUBZ").text = "0"
        etree.SubElement(node, "WENJIANMC").text = display_name
        zmyt = etree.SubElement(node, "ZHENGMINGYT", FILETYPE="")
        zmyt.text = display_name

    tree = etree.ElementTree(root)
    list_path = os.path.join(case_root, "list.xml")
    tree.write(
        list_path,
        encoding="UTF-8",
        xml_declaration=True,
        pretty_print=True
    )
    logger.info(f"💾 list.xml 已生成: {list_path}")

    return list_path
