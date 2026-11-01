from __future__ import annotations

import re
from pathlib import Path

from lxml import etree

OPINION_BODY_DOCTYPE = '<!DOCTYPE cn-other-file SYSTEM "/dtdandxsl/cn-other-file-20080416.dtd">'


def write_xml_with_optional_doctype(root, path: str | Path, *, doctype: str | None = None) -> str:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    etree.ElementTree(root).write(
        str(target),
        encoding="UTF-8",
        xml_declaration=True,
        pretty_print=False,
        doctype=doctype,
    )
    return str(target)


def normalize_opinion_body_xml(path: str | Path) -> str:
    target = Path(path)
    parsed = etree.parse(str(target))
    root = parsed.getroot()
    if root.tag == "cn-other-file":
        other = root
    else:
        other = root.find(".//cn-other-file")
    if other is None:
        raise RuntimeError(f"意见陈述正文转换结果缺少 cn-other-file 根节点：{target}")

    for index, paragraph in enumerate(other.iter("p"), start=1):
        raw_num = str(paragraph.attrib.get("num", "") or "").strip()
        if raw_num.isdigit() or not raw_num:
            paragraph.attrib["num"] = str(index)

    return write_xml_with_optional_doctype(other, target, doctype=OPINION_BODY_DOCTYPE)


def normalize_claims_for_response_correction(path: str | Path) -> str:
    target = Path(path)
    parsed = etree.parse(str(target))
    claims = list(parsed.iterfind(".//claim"))
    if claims:
        first = claims[0]
        first_text = "".join(first.itertext())
        if re.sub(r"\s+", "", first_text) == "权利要求书":
            parent = first.getparent()
            if parent is not None:
                parent.remove(first)

    for index, claim in enumerate(parsed.iterfind(".//claim"), start=1):
        claim.attrib["num"] = str(index)
        claim.attrib["id"] = f"c1_cl{index:03d}"

    doctype = parsed.docinfo.doctype or None
    return write_xml_with_optional_doctype(parsed.getroot(), target, doctype=doctype)


__all__ = [
    "OPINION_BODY_DOCTYPE",
    "normalize_claims_for_response_correction",
    "normalize_opinion_body_xml",
    "write_xml_with_optional_doctype",
]
