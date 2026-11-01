from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import core.official_docs.pdf_entity_extract_v3 as matrix_mod
from core.official_docs.resource_mirror import ResourceMirrorPaths


def _write_matrix(path: Path, *, default_fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "default_fields": default_fields,
        "by_notice_key": {},
        "by_notice_code": {},
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


class OfficialDocsPdfMatrixResourceHealthTests(unittest.TestCase):
    def setUp(self) -> None:
        matrix_mod.clear_pdf_field_matrix_cache()

    def tearDown(self) -> None:
        matrix_mod.clear_pdf_field_matrix_cache()

    def test_prefers_embedded_matrix_and_syncs_mirror(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            embedded = base / "embedded" / "official_doc_pdf_field_matrix.json"
            mirror = base / "mirror" / "official_doc_pdf_field_matrix.json"
            _write_matrix(embedded, default_fields=["department", "applicant"])

            paths = ResourceMirrorPaths(
                resource_name="official_doc_pdf_field_matrix.json",
                embedded_path=str(embedded),
                mirror_path=str(mirror),
            )
            with patch("core.official_docs.pdf_entity_extract_v3.get_resource_mirror_paths", return_value=paths):
                fields = matrix_mod.resolve_pdf_applicable_fields(notice_key="unknown")
                health = matrix_mod.get_pdf_field_matrix_health()

            self.assertTrue(health.healthy)
            self.assertEqual(health.source, "embedded")
            self.assertTrue(mirror.exists())
            self.assertEqual(fields, ("department", "applicant"))

    def test_falls_back_to_mirror_when_embedded_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            embedded = base / "embedded" / "official_doc_pdf_field_matrix.json"
            mirror = base / "mirror" / "official_doc_pdf_field_matrix.json"
            _write_matrix(mirror, default_fields=["reject_reason"])

            paths = ResourceMirrorPaths(
                resource_name="official_doc_pdf_field_matrix.json",
                embedded_path=str(embedded),
                mirror_path=str(mirror),
            )
            with patch("core.official_docs.pdf_entity_extract_v3.get_resource_mirror_paths", return_value=paths):
                fields = matrix_mod.resolve_pdf_applicable_fields(notice_key="unknown")
                health = matrix_mod.get_pdf_field_matrix_health()

            self.assertTrue(health.healthy)
            self.assertEqual(health.source, "mirror")
            self.assertEqual(fields, ("reject_reason",))

    def test_marks_unhealthy_when_embedded_and_mirror_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            paths = ResourceMirrorPaths(
                resource_name="official_doc_pdf_field_matrix.json",
                embedded_path=str(base / "embedded" / "official_doc_pdf_field_matrix.json"),
                mirror_path=str(base / "mirror" / "official_doc_pdf_field_matrix.json"),
            )
            with patch("core.official_docs.pdf_entity_extract_v3.get_resource_mirror_paths", return_value=paths):
                fields = matrix_mod.resolve_pdf_applicable_fields(notice_key="unknown")
                health = matrix_mod.get_pdf_field_matrix_health()

            self.assertFalse(health.healthy)
            self.assertEqual(fields, tuple())


if __name__ == "__main__":
    unittest.main()

