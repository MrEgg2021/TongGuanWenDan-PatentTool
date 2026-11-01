from __future__ import annotations

import secrets
from dataclasses import dataclass
from pathlib import Path

from lxml import etree

from .models import NoticeMeta, SubmissionScene


@dataclass(frozen=True)
class ManifestEntry:
    code: str
    filename: str
    display_name: str
    fmt: str = ".XML"
    pages: int = 1
    counts: int = 0


_DISPLAY_NAMES = {
    "100001": "权利要求书",
    "100002": "说明书",
    "100003": "说明书附图",
    "100004": "说明书摘要",
    "100006": "补正书",
    "100012": "意见陈述书",
}


def _patent_yewulx(notice: NoticeMeta) -> str:
    return "1" if notice.patent_type == "utility_model" else "0"


def _related_code(submission_scene: SubmissionScene) -> str:
    return {
        "notice_response": "YW10001201",
        "notice_correction": "YW10000601",
        "active_response": "YW10001203",
        "active_correction": "YW10000602",
    }.get(str(submission_scene or "notice_response"), "YW10001201")


def generate_case_id() -> str:
    return f"100{secrets.randbelow(100000):05d}"


def count_claims(xml_path: str) -> int:
    try:
        tree = etree.parse(str(xml_path))
        return len(list(tree.iterfind(".//claim")))
    except Exception:
        return 0


def write_manifest(
    case_root: str | Path,
    *,
    case_id: str,
    submission_scene: SubmissionScene,
    notice: NoticeMeta,
    entries: list[ManifestEntry],
) -> str:
    case_root_path = Path(case_root)
    root = etree.Element("data-bus")
    qingqiu = etree.SubElement(root, "QINGQIUXX")
    etree.SubElement(qingqiu, "DIANZISQAJID").text = str(case_id)
    etree.SubElement(qingqiu, "SHENQINGFS").text = "2"
    etree.SubElement(qingqiu, "YEWULX").text = _patent_yewulx(notice)
    etree.SubElement(qingqiu, "WENJIANLX").text = "1"
    etree.SubElement(qingqiu, "TIJIAORDM").text = ""
    etree.SubElement(qingqiu, "FAMINGMC").text = notice.invention_title
    etree.SubElement(qingqiu, "SHENQINGH").text = notice.application_no
    etree.SubElement(qingqiu, "WEINEIBH").text = ""
    etree.SubElement(qingqiu, "GUOJISQH").text = ""
    etree.SubElement(qingqiu, "NEIBUBH").text = notice.internal_no
    etree.SubElement(qingqiu, "BAOID").text = ""

    wenjianb = etree.SubElement(root, "WENJIANBYSXX")
    baotou = etree.SubElement(wenjianb, "BAOTOUXX")
    etree.SubElement(baotou, "WENJIANBBZ").text = ""
    etree.SubElement(baotou, "WENJIANGS").text = str(len(entries))

    for entry in entries:
        node = etree.SubElement(wenjianb, "BAONEIWJXX", GUANLIANYWDM=_related_code(submission_scene))
        etree.SubElement(node, "WENJIANBZ").text = entry.filename
        etree.SubElement(node, "GESHILX").text = entry.fmt
        etree.SubElement(node, "BIAOGEDM").text = entry.code
        etree.SubElement(node, "XIANGDUILJ").text = f"{entry.code}\\{entry.filename}"
        etree.SubElement(node, "DTDVersion").text = "1.0"
        etree.SubElement(node, "PAGES").text = str(entry.pages)
        etree.SubElement(node, "COUNTS").text = str(entry.counts)
        etree.SubElement(node, "SHIFOUBZ").text = "0"
        etree.SubElement(node, "WENJIANMC").text = entry.display_name
        zmyt = etree.SubElement(node, "ZHENGMINGYT", FILETYPE="")
        zmyt.text = entry.display_name

    list_path = case_root_path / "list.xml"
    etree.ElementTree(root).write(str(list_path), encoding="UTF-8", xml_declaration=True, pretty_print=True)
    return str(list_path)


def make_entry(code: str, *, filename: str | None = None, fmt: str = ".XML", pages: int = 1, counts: int = 0) -> ManifestEntry:
    return ManifestEntry(
        code=code,
        filename=filename or f"{code}.xml",
        display_name=_DISPLAY_NAMES.get(code, code),
        fmt=fmt,
        pages=pages,
        counts=counts,
    )

__all__ = ["ManifestEntry", "count_claims", "generate_case_id", "make_entry", "write_manifest"]
