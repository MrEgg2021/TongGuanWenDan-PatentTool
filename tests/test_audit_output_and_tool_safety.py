from __future__ import annotations

import tempfile
import unittest
import os
import zipfile
import json

from lxml import etree
from pathlib import Path
from unittest.mock import patch

from core.document_parser.output_mixin_impl import OutputGenerationMixin
from core.document_parser.document_parser import DocumentParser
from core.cnipa_preview.package import prepare_preview_package
from core.release_notes import evidence_status
from core.runtime import cleanup_runtime_artifacts, register_output_workspace
from core.xml_generator import XMLBuilder
from tools.build_nuitka_pyd import _prepare_output
from tools import build_nuitka_pyd
from tools.quality.table_conversion_audit import _discover_target_xml


class AuditOutputAndToolSafetyTests(unittest.TestCase):
    def test_conversion_failure_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            marker = root / "original.txt"
            marker.write_text("keep", encoding="utf-8")
            parser = OutputGenerationMixin()
            parser.config = {"paths": {"output_dir": tmp}}
            with patch.object(parser, "_normalize_description_structure", side_effect=RuntimeError("injected"), create=True):
                with self.assertRaisesRegex(RuntimeError, "injected"):
                    parser.generate_output_files("123")
            self.assertEqual("keep", marker.read_text(encoding="utf-8"))
            self.assertEqual([marker], list(root.iterdir()))
            for invalid in ("../escape", ".. ", "CON", "C:/escape"):
                with self.subTest(case_id=invalid), self.assertRaises(ValueError):
                    parser.generate_output_files(invalid)

    def test_frozen_cleanup_only_removes_current_owned_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            foreign = root / "foreign"
            foreign.mkdir()
            owned = root / ".conversion-owned"
            owned.mkdir()
            register_output_workspace(str(owned))
            with patch("core.runtime.sys.frozen", True, create=True):
                cleanup_runtime_artifacts({"case_root": str(foreign / "123")})
                self.assertTrue(foreign.exists())
                cleanup_runtime_artifacts({"case_root": str(owned / "123")})
            self.assertFalse(owned.exists())
            self.assertTrue(foreign.exists())

    def test_table_audit_finds_latest_independent_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = root / "123" / "100002" / "100002.xml"
            new = root / ".conversion-new" / "123" / "100002" / "100002.xml"
            for path in (old, new):
                path.parent.mkdir(parents=True)
                path.write_text("<description/>", encoding="utf-8")
            os.utime(old, (1, 1))
            self.assertEqual(new.resolve(), _discover_target_xml(output_root=root, case_id="123", doc_code="100002"))

    def test_repeat_output_keeps_zip_content_and_remains_previewable(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = {"paths": {"output_dir": tmp, "temp_dir": tmp}, "bus": {"case_id": "123"}}
            results = []
            for _ in range(2):
                parser = DocumentParser(None, None, XMLBuilder(config), config)
                parser.enabled_sections = {"request_form": False}
                etree.SubElement(parser.sections["abstract"], "p").text = "示例摘要。"
                results.append(parser.generate_output_files())
            self.assertNotEqual(results[0]["case_root"], results[1]["case_root"])
            contents = []
            for result in results:
                with zipfile.ZipFile(result["inner_zip_path"]) as archive:
                    contents.append({name: archive.read(name) for name in archive.namelist()})
                with prepare_preview_package(result["inner_zip_path"]) as package:
                    self.assertEqual(1, len(package.documents))
                    self.assertEqual("100004", package.documents[0].code)
            self.assertEqual(contents[0], contents[1])

    def test_evidence_status_does_not_treat_skipped_as_passed(self):
        self.assertEqual("not_executed", evidence_status({"ok": True, "not_executed": True}))
        self.assertEqual("not_applicable", evidence_status({"status": "not_applicable"}))
        self.assertEqual("failed", evidence_status({"ok": False}))
        with self.assertRaises(ValueError):
            evidence_status({"status": "unknown"})

    def test_build_clean_requires_confined_owned_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp).resolve()
            source = repo / "core"
            source.mkdir()
            marker = source / "original.py"
            marker.write_text("keep", encoding="utf-8")
            for unsafe in (repo, source, repo / "build", repo.parent):
                with self.assertRaises(SystemExit):
                    _prepare_output(repo, unsafe, clean=True)
            self.assertTrue(marker.exists())
            output = repo / "build" / "owned"
            _prepare_output(repo, output, clean=False)
            stale = output / "stale.pyd"
            stale.write_bytes(b"old")
            _prepare_output(repo, output, clean=True)
            self.assertFalse(stale.exists())
            foreign = repo / "build" / "foreign"
            foreign.mkdir()
            (foreign / "keep.txt").write_text("keep", encoding="utf-8")
            with self.assertRaises(SystemExit):
                _prepare_output(repo, foreign, clean=True)
            self.assertTrue((foreign / "keep.txt").exists())

    def test_build_validates_modules_before_cleaning(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp).resolve()
            output = repo / "build" / "owned"
            _prepare_output(repo, output, clean=False)
            source = output / "original.py"
            source.write_text("keep", encoding="utf-8")
            config = repo / "config.json"
            for include in ("missing/*.py", "build/owned/*.py"):
                config.write_text(json.dumps({"test": {"include": [include]}}), encoding="utf-8")
                args = ["build_nuitka_pyd.py", "--profile", "test", "--config", "config.json", "--output-root", "build/owned", "--clean"]
                with patch.object(build_nuitka_pyd, "__file__", str(repo / "tools" / "build_nuitka_pyd.py")), patch.object(build_nuitka_pyd.sys, "argv", args):
                    with self.assertRaises(SystemExit):
                        build_nuitka_pyd.main()
                self.assertEqual("keep", source.read_text(encoding="utf-8"))
