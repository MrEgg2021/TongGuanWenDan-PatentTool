from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import core.official_docs.field_registry as field_registry
from core.official_docs.resource_mirror import ResourceMirrorPaths


def _write_catalog(path: Path, *, extra_key: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "version": 1,
        "types": [
            {"key": "exam_opinion", "display_name": "审查意见通知书", "processable": True},
            {"key": "rectification", "display_name": "补正通知书", "processable": True},
            {"key": extra_key, "display_name": "测试扩展通知书", "processable": True},
        ],
    }
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


class OfficialDocsCatalogResourceHealthTests(unittest.TestCase):
    def setUp(self) -> None:
        field_registry.clear_supported_type_catalog_cache()

    def tearDown(self) -> None:
        field_registry.clear_supported_type_catalog_cache()

    def test_prefers_embedded_catalog_and_syncs_mirror(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            embedded = base / "embedded" / "official_doc_supported_types.json"
            mirror = base / "mirror" / "official_doc_supported_types.json"
            _write_catalog(embedded, extra_key="299999|测试扩展通知书")

            paths = ResourceMirrorPaths(
                resource_name="official_doc_supported_types.json",
                embedded_path=str(embedded),
                mirror_path=str(mirror),
            )
            with patch("core.official_docs.field_registry.get_resource_mirror_paths", return_value=paths):
                catalog = field_registry.get_supported_type_catalog()
                health = field_registry.get_supported_type_catalog_health()

            self.assertTrue(health.healthy)
            self.assertEqual(health.source, "embedded")
            self.assertTrue(mirror.exists())
            self.assertIn("299999|测试扩展通知书", {str(item.get("key", "")) for item in catalog})

    def test_falls_back_to_mirror_when_embedded_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            embedded = base / "embedded" / "official_doc_supported_types.json"
            mirror = base / "mirror" / "official_doc_supported_types.json"
            _write_catalog(mirror, extra_key="288888|镜像通知书")

            paths = ResourceMirrorPaths(
                resource_name="official_doc_supported_types.json",
                embedded_path=str(embedded),
                mirror_path=str(mirror),
            )
            with patch("core.official_docs.field_registry.get_resource_mirror_paths", return_value=paths):
                catalog = field_registry.get_supported_type_catalog()
                health = field_registry.get_supported_type_catalog_health()

            self.assertTrue(health.healthy)
            self.assertEqual(health.source, "mirror")
            self.assertIn("288888|镜像通知书", {str(item.get("key", "")) for item in catalog})

    def test_marks_unhealthy_when_embedded_and_mirror_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            paths = ResourceMirrorPaths(
                resource_name="official_doc_supported_types.json",
                embedded_path=str(base / "embedded" / "official_doc_supported_types.json"),
                mirror_path=str(base / "mirror" / "official_doc_supported_types.json"),
            )
            with patch("core.official_docs.field_registry.get_resource_mirror_paths", return_value=paths):
                catalog = field_registry.get_supported_type_catalog()
                health = field_registry.get_supported_type_catalog_health()

            self.assertFalse(health.healthy)
            self.assertIn("unavailable", health.error)
            keys = {str(item.get("key", "")) for item in catalog}
            self.assertEqual(keys, {"exam_opinion", "rectification"})

    def test_default_catalog_contains_non_default_extension_types(self) -> None:
        catalog = field_registry.get_supported_type_catalog()
        keys = {str(item.get("key", "")) for item in catalog}
        non_default = keys.difference({"exam_opinion", "rectification"})
        self.assertTrue(non_default, "catalog must contain extension types beyond built-in defaults")


if __name__ == "__main__":
    unittest.main()

