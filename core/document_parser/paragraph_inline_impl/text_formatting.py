from __future__ import annotations

import re
from lxml import etree
from core.logging_utils import logger


def extract_text_with_formatting(self, rng):
    """
    从 Word Range 中提取文本，并保留上下标格式。
    返回的字符串中包含 <sub>...</sub> 和 <sup>...</sup> 标签。
    """
    try:
        def _fallback_text():
            try:
                return (rng.Text or "").replace("\x0b", "\n")
            except Exception:
                try:
                    return rng.Text
                except Exception:
                    return ""

        xml_content = rng.WordOpenXML
        if not xml_content:
            return _fallback_text()

        try:
            if isinstance(xml_content, bytes):
                if b"vertAlign" not in xml_content:
                    return _fallback_text()
            else:
                if "vertAlign" not in xml_content:
                    return _fallback_text()
        except Exception:
            return _fallback_text()

        if isinstance(xml_content, bytes):
            xml_bytes = xml_content
        else:
            xml_text = re.sub(r"^\s*<\?xml[^>]*\?>", "", xml_content).lstrip()
            xml_bytes = xml_text.encode("utf-8")

        root = etree.fromstring(xml_bytes)
        ns = {
            "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
            "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
        }

        text_parts = []
        runs = root.xpath(".//w:r", namespaces=ns)

        for run in runs:
            rPr = run.find("w:rPr", namespaces=ns)
            tag_start = ""
            tag_end = ""

            if rPr is not None:
                vertAlign = rPr.find("w:vertAlign", namespaces=ns)
                if vertAlign is not None:
                    val = vertAlign.get(f"{{{ns['w']}}}val")
                    if val == "superscript":
                        tag_start = "<sup>"
                        tag_end = "</sup>"
                    elif val == "subscript":
                        tag_start = "<sub>"
                        tag_end = "</sub>"

            run_text = ""
            for child in run:
                tag = child.tag
                if tag == f"{{{ns['w']}}}t":
                    if child.text:
                        run_text += child.text
                elif tag == f"{{{ns['w']}}}tab":
                    run_text += "\t"
                elif tag == f"{{{ns['w']}}}br":
                    try:
                        br_type = child.get(f"{{{ns['w']}}}type")
                    except Exception:
                        br_type = None
                    if (not br_type) or br_type == "textWrapping":
                        run_text += "\n"
                elif tag == f"{{{ns['w']}}}cr":
                    run_text += "\n"
                elif tag == f"{{{ns['w']}}}sym":
                    return _fallback_text()

            if run_text:
                text_parts.append(f"{tag_start}{run_text}{tag_end}")

        if not text_parts:
            raw_text_check = _fallback_text()
            if raw_text_check and raw_text_check.strip() and not text_parts:
                return raw_text_check
            return ""

        return "".join(text_parts)

    except Exception as e:
        try:
            logger.warning(f"Error parsing WordOpenXML: {e}, falling back to Range.Text")
        except Exception:
            pass
        return _fallback_text()


__all__ = ["extract_text_with_formatting"]
