from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from xml.etree import ElementTree as ET

from .models import AttachmentMeta


def _decode_xml_bytes(data: bytes) -> str:
    raw = data or b""
    for enc in ("utf-8-sig", "utf-8", "gb18030", "gbk"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("utf-8", errors="replace")


def _text(el: Optional[ET.Element]) -> str:
    if el is None:
        return ""
    try:
        t = el.text
    except Exception:
        t = None
    return str(t or "").strip()


def _flatten_children(parent: ET.Element, prefix: str, out: dict[str, str]) -> None:
    try:
        children = list(parent)
    except Exception:
        children = []
    if not children:
        return

    counts: dict[str, int] = {}
    for ch in children:
        tag = str(getattr(ch, "tag", "") or "")
        if not tag:
            continue
        counts[tag] = counts.get(tag, 0) + 1

    seen: dict[str, int] = {}
    for ch in children:
        tag = str(getattr(ch, "tag", "") or "")
        if not tag:
            continue
        seen[tag] = seen.get(tag, 0) + 1
        if counts.get(tag, 0) > 1:
            seg = f"{tag}[{seen[tag]}]"
        else:
            seg = tag

        path = f"{prefix}/{seg}" if prefix else seg

        try:
            attrib = dict(getattr(ch, "attrib", {}) or {})
        except Exception:
            attrib = {}
        for k, v in attrib.items():
            ak = str(k or "").strip()
            if not ak:
                continue
            out[f"{path}@{ak}"] = str(v or "").strip()

        tv = _text(ch)
        if tv:
            out[path] = tv

        _flatten_children(ch, path, out)


@dataclass(frozen=True)
class ListXmlParseResult:
    meta: dict[str, str]
    flat_fields: dict[str, str]
    attachments: list[AttachmentMeta]


def parse_list_xml(xml_bytes: bytes) -> ListXmlParseResult:
    text = _decode_xml_bytes(xml_bytes)
    root = ET.fromstring(text)

    # Extract meta fields (best-effort; empty when missing)
    meta: dict[str, str] = {}
    try:
        meta["FAWENXLH"] = _text(root.find("./FAWENXLH"))
    except Exception:
        meta["FAWENXLH"] = ""

    sx = None
    try:
        sx = root.find(".//SHUXINGXX")
    except Exception:
        sx = None

    def _sx(tag: str) -> str:
        if sx is None:
            return ""
        try:
            return _text(sx.find(f"./{tag}"))
        except Exception:
            return ""

    meta.update(
        {
            "ANJUANH": _sx("ANJUANH"),
            "NEIBUBH": _sx("NEIBUBH"),
            "SHENQINGH": _sx("SHENQINGH"),
            "SHENQINGR": _sx("SHENQINGR"),
            "FAMINGMC": _sx("FAMINGMC"),
            "TONGZHISBM": _sx("TONGZHISBM"),
            "TONGZHISMC": _sx("TONGZHISMC"),
            "FAWENR": _sx("FAWENR"),
            "YUQIRQ": _sx("YUQIRQ"),
            "QIXIAN": _sx("QIXIAN"),
            "FAMINGLX": _sx("FAMINGLX"),
            "DMHFLAG": _sx("DMHFLAG"),
        }
    )

    # Extract attachments in declared order (if present)
    attachments: list[AttachmentMeta] = []
    try:
        for fu in root.findall(".//FUJIANLB/FUJIAN"):
            attachments.append(
                AttachmentMeta(
                    name=_text(fu.find("./WENJIANMC")),
                    desc=_text(fu.find("./WENJIANMS")),
                )
            )
    except Exception:
        attachments = []

    # Flatten: root-level fields (excluding TONGZHISXJ) + TONGZHISXJ subtree (without TONGZHISXJ prefix)
    flat: dict[str, str] = {}
    try:
        root_children = list(root)
    except Exception:
        root_children = []

    tong_nodes = [c for c in root_children if str(getattr(c, "tag", "") or "") == "TONGZHISXJ"]
    other_nodes = [c for c in root_children if str(getattr(c, "tag", "") or "") != "TONGZHISXJ"]

    for ch in other_nodes:
        tag = str(getattr(ch, "tag", "") or "")
        if not tag:
            continue
        # include attributes and own text
        try:
            attrib = dict(getattr(ch, "attrib", {}) or {})
        except Exception:
            attrib = {}
        for k, v in attrib.items():
            ak = str(k or "").strip()
            if not ak:
                continue
            flat[f"{tag}@{ak}"] = str(v or "").strip()
        tv = _text(ch)
        if tv:
            flat[tag] = tv
        _flatten_children(ch, tag, flat)

    if len(tong_nodes) == 1:
        _flatten_children(tong_nodes[0], "", flat)
    else:
        for idx, tn in enumerate(tong_nodes, start=1):
            _flatten_children(tn, f"TONGZHISXJ[{idx}]", flat)

    return ListXmlParseResult(meta=meta, flat_fields=flat, attachments=attachments)


__all__ = ["ListXmlParseResult", "parse_list_xml"]
