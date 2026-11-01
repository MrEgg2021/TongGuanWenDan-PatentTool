from __future__ import annotations
 
import argparse
import json
import os
import zipfile
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional
 
 
def local_tag(tag: str) -> str:
    """Return the local name of an XML tag.
 
    Args:
        tag: Qualified XML tag.
 
    Returns:
        Local tag name without namespace.
    """
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag
 
 
def build_parent_map(root: ET.Element) -> Dict[ET.Element, ET.Element]:
    """Build a parent map for quick ancestor lookup.
 
    Args:
        root: XML root element.
 
    Returns:
        Mapping of element to its parent element.
    """
    return {child: parent for parent in root.iter() for child in parent}
 
 
def find_src_rect(node: ET.Element, parent_map: Dict[ET.Element, ET.Element]) -> Optional[Dict[str, str]]:
    """Find the nearest a:srcRect attributes around the node subtree.
 
    Args:
        node: Target node containing the image reference.
        parent_map: Parent mapping for the XML tree.
 
    Returns:
        Attribute dict for a:srcRect if found, else None.
    """
    current = node
    while current is not None:
        for elem in current.iter():
            if local_tag(elem.tag) == "srcRect":
                return dict(elem.attrib)
        current = parent_map.get(current)
    return None
 
 
def node_path(node: ET.Element, parent_map: Dict[ET.Element, ET.Element], max_depth: int = 8) -> str:
    """Build a readable ancestor path for a node.
 
    Args:
        node: Target XML node.
        parent_map: Parent mapping for the XML tree.
        max_depth: Maximum depth to include.
 
    Returns:
        Slash-delimited tag path.
    """
    parts: List[str] = []
    current = node
    while current is not None and len(parts) < max_depth:
        parts.append(local_tag(current.tag))
        current = parent_map.get(current)
    return "/".join(reversed(parts))
 
 
def collect_rel_hits(zf: zipfile.ZipFile, target: str) -> List[Dict[str, Optional[str]]]:
    """Collect relationship entries that reference the target media file.
 
    Args:
        zf: Open zipfile handle.
        target: Target filename fragment to match.
 
    Returns:
        List of relationship hit dictionaries.
    """
    hits: List[Dict[str, Optional[str]]] = []
    rel_ns = "{http://schemas.openxmlformats.org/package/2006/relationships}"
    for name in zf.namelist():
        if not name.endswith(".rels"):
            continue
        try:
            root = ET.fromstring(zf.read(name))
        except Exception:
            continue
        for rel in root.findall(rel_ns + "Relationship"):
            target_name = rel.get("Target", "") or ""
            if target in target_name:
                hits.append(
                    {
                        "rels": name,
                        "rid": rel.get("Id"),
                        "target": target_name,
                        "type": rel.get("Type"),
                    }
                )
    return hits
 
 
def collect_matches(
    zf: zipfile.ZipFile, names: List[str], rel_hits: List[Dict[str, Optional[str]]]
) -> List[Dict[str, object]]:
    """Collect element matches referencing each relationship ID.
 
    Args:
        zf: Open zipfile handle.
        names: List of zip entry names.
        rel_hits: Relationship hit dictionaries.
 
    Returns:
        List of match dictionaries with srcRect/crop attributes.
    """
    matches: List[Dict[str, object]] = []
    for hit in rel_hits:
        rel_name = hit.get("rels") or ""
        rid = hit.get("rid") or ""
        base = rel_name.replace("_rels/", "").replace(".rels", "")
        if base not in names:
            matches.append(
                {
                    "rels": rel_name,
                    "base": base,
                    "rid": rid,
                    "error": "base_not_found",
                }
            )
            continue
        try:
            root = ET.fromstring(zf.read(base))
        except Exception as exc:
            matches.append(
                {
                    "rels": rel_name,
                    "base": base,
                    "rid": rid,
                    "error": "parse_fail",
                    "error_detail": str(exc),
                }
            )
            continue
        parent_map = build_parent_map(root)
        for elem in root.iter():
            for attr_key, attr_val in elem.attrib.items():
                if attr_val == rid and (
                    attr_key.endswith("}embed")
                    or attr_key.endswith("}id")
                    or attr_key.endswith("}link")
                ):
                    tag = local_tag(elem.tag)
                    src_rect = find_src_rect(elem, parent_map)
                    crop_attrs: Dict[str, str] = {}
                    if tag == "imagedata":
                        for key, value in elem.attrib.items():
                            if "crop" in key.lower():
                                crop_attrs[key] = value
                    matches.append(
                        {
                            "rels": rel_name,
                            "base": base,
                            "rid": rid,
                            "tag": tag,
                            "path": node_path(elem, parent_map),
                            "srcRect": src_rect,
                            "cropAttrs": crop_attrs,
                        }
                    )
                    break
    return matches
 
 
def parse_args() -> argparse.Namespace:
    """Parse command line arguments.
 
    Returns:
        Parsed argparse namespace.
    """
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    default_docx = os.path.join(repo_root, "test_pic", "test.docx")
    default_out = os.path.join(repo_root, "test_pic", "crop_debug_image83.json")
 
    parser = argparse.ArgumentParser(
        description="Diagnose docx image cropping metadata (srcRect/crop*)."
    )
    parser.add_argument("--docx", default=default_docx, help="Path to docx file")
    parser.add_argument("--target", default="image83.emf", help="Target media file")
    parser.add_argument("--out", default=default_out, help="Output json path")
    return parser.parse_args()
 
 
def main() -> int:
    """Entry point for the diagnostic script.
 
    Returns:
        Exit code 0 on success, non-zero on failure.
    """
    args = parse_args()
    docx_path = os.path.abspath(args.docx)
    output_path = os.path.abspath(args.out)
 
    if not os.path.exists(docx_path):
        print(f"DOCX_NOT_FOUND {docx_path}")
        return 2
 
    try:
        with zipfile.ZipFile(docx_path, "r") as zf:
            names = zf.namelist()
            rel_hits = collect_rel_hits(zf, args.target)
            matches = collect_matches(zf, names, rel_hits)
    except Exception as exc:
        print(f"DOCX_READ_ERROR {exc}")
        return 3
 
    output = {
        "target": args.target,
        "docx_path": docx_path,
        "rel_hits": rel_hits,
        "matches": matches,
    }
 
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(output, handle, ensure_ascii=False, indent=2)
 
    print(f"WROTE {output_path} rel_hits={len(rel_hits)} matches={len(matches)}")
    return 0
 
 
if __name__ == "__main__":
    raise SystemExit(main())
 
