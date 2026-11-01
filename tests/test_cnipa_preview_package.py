from __future__ import annotations

import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from core.archive_safety import ArchiveBudget
from core.cnipa_preview.package import PreviewPackageError, inspect_preview_package, prepare_preview_package


_DOCUMENTS = (
    ("100001", "权利要求书"),
    ("100002", "说明书"),
    ("100003", "说明书附图"),
    ("100004", "说明书摘要"),
    ("110101", "发明专利请求书"),
    ("110401", "实质审查请求书"),
)

_DEFAULT_PREVIEW_CODES = ("110101", "110401", "100004", "100001", "100002", "100003")
_DEFAULT_PREVIEW_NAMES = ("发明专利请求书", "实质审查请求书", "说明书摘要", "权利要求书", "说明书", "说明书附图")


def _manifest(entries: tuple[tuple[str, str], ...] = _DOCUMENTS) -> str:
    blocks = []
    for code, name in entries:
        blocks.append(
            "<BAONEIWJXX>"
            f"<WENJIANBZ>{code}.xml</WENJIANBZ>"
            "<GESHILX>.XML</GESHILX>"
            f"<BIAOGEDM>{code}</BIAOGEDM>"
            f"<XIANGDUILJ>{code}\\{code}.xml</XIANGDUILJ>"
            f"<WENJIANMC>{name}</WENJIANMC>"
            "</BAONEIWJXX>"
        )
    return "<?xml version='1.0' encoding='UTF-8'?><data-bus><WENJIANBYSXX>" + "".join(blocks) + "</WENJIANBYSXX></data-bus>"


def _case_zip_bytes(*, manifest: str | None = None, extra_members: dict[str, bytes] | None = None) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("10000021/list.xml", manifest or _manifest())
        for code, _name in _DOCUMENTS:
            archive.writestr(f"10000021/{code}/{code}.xml", f"<root code='{code}'/>")
        for name, content in (extra_members or {}).items():
            archive.writestr(name, content)
    return buffer.getvalue()


def _attachment_manifest(*blocks: str) -> str:
    """Build a manifest from raw BAONEIWJXX bodies so attachments can omit BIAOGEDM."""
    entries = "".join(f"<BAONEIWJXX>{block}</BAONEIWJXX>" for block in blocks)
    return "<?xml version='1.0' encoding='UTF-8'?><data-bus><WENJIANBYSXX>" + entries + "</WENJIANBYSXX></data-bus>"


def _png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (24, 32), "white").save(buffer, format="PNG")
    return buffer.getvalue()


class CnipaPreviewPackageTests(unittest.TestCase):
    def test_discovers_four_books_without_manifest_and_preserves_images(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "case.zip"
            with zipfile.ZipFile(path, "w") as archive:
                for code in ("100001", "100002", "100003", "100004"):
                    archive.writestr(f"case/{code}/{code}.xml", "<cn-application-body/>")
                archive.writestr("case/100003/figure.jpg", b"image")
                archive.writestr("case/110101/110101.xml", "<request/>")
            with prepare_preview_package(path) as package:
                self.assertEqual([doc.code for doc in package.documents], ["100004", "100001", "100002", "100003"])
                self.assertEqual(package.errors_by_document_id, {})
                drawings = next(doc for doc in package.documents if doc.code == "100003")
                xml_path = package.xml_paths_by_document_id[drawings.id]
                self.assertEqual((xml_path.parent / "figure.jpg").read_bytes(), b"image")
                self.assertEqual(package.case_root / drawings.relative_path, xml_path)

    def test_discovers_four_book_subset_in_nested_zip_without_manifest(self) -> None:
        inner = io.BytesIO()
        with zipfile.ZipFile(inner, "w") as archive:
            archive.writestr("100001.XML", "<cn-application-body/>")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "outer.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("inner.zip", inner.getvalue())
            result = inspect_preview_package(path)
        self.assertEqual([doc.code for doc in result.documents], ["100001"])

    def test_no_manifest_does_not_guess_other_xml_names(self) -> None:
        for name in ("110101.xml", "claims.xml", "100001-backup.xml", "100001.txt"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmpdir:
                path = Path(tmpdir) / "case.zip"
                with zipfile.ZipFile(path, "w") as archive:
                    archive.writestr(name, "<cn-application-body><cn-claims/></cn-application-body>")
                with self.assertRaisesRegex(PreviewPackageError, "四书 XML"):
                    inspect_preview_package(path)

    def test_manifest_remains_authoritative_over_unlisted_four_books(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "case.zip"
            path.write_bytes(_case_zip_bytes(manifest=_manifest((("110101", "发明专利请求书"),))))
            result = inspect_preview_package(path)
        self.assertEqual([doc.code for doc in result.documents], ["110101"])

    def test_multiple_manifests_are_not_bypassed_by_four_book_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "case.zip"
            path.write_bytes(_case_zip_bytes(extra_members={"other/list.xml": b"<root/>"}))
            with self.assertRaisesRegex(PreviewPackageError, "多个 list.xml"):
                inspect_preview_package(path)

    def test_no_manifest_still_rejects_archive_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "case.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("100001.xml", "<cn-application-body/>")
                archive.writestr("../outside.xml", "<root/>")
            with self.assertRaisesRegex(PreviewPackageError, "unsafe member path"):
                inspect_preview_package(path)

    def test_pdf_attachment_passes_through_without_a_form_code(self) -> None:
        manifest = _attachment_manifest(
            "<WENJIANBZ>100022.pdf</WENJIANBZ><GESHILX>.PDF</GESHILX>"
            "<XIANGDUILJ>100022\\100022.pdf</XIANGDUILJ><WENJIANMC>总委托书</WENJIANMC>",
            "<BIAOGEDM>100001</BIAOGEDM><XIANGDUILJ>100001\\100001.xml</XIANGDUILJ><WENJIANMC>权利要求书</WENJIANMC>",
        )
        attachment_bytes = b"%PDF-1.7\nsigned power of attorney"
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "case.zip"
            path.write_bytes(
                _case_zip_bytes(
                    manifest=manifest,
                    extra_members={"10000021/100022/100022.pdf": attachment_bytes},
                )
            )

            with prepare_preview_package(path) as package:
                by_name = {document.display_name: document for document in package.documents}
                self.assertEqual(package.errors_by_document_id, {})
                self.assertEqual(set(package.xml_paths_by_document_id), {by_name["权利要求书"].id})
                self.assertEqual(set(package.pdf_paths_by_document_id), {by_name["总委托书"].id})
                self.assertEqual(
                    package.pdf_paths_by_document_id[by_name["总委托书"].id].read_bytes(),
                    attachment_bytes,
                )

            result = inspect_preview_package(path)
        self.assertEqual(result.passthrough_document_ids, frozenset({by_name["总委托书"].id}))

    def test_attachment_content_defeats_the_declared_xml_suffix(self) -> None:
        manifest = _attachment_manifest(
            "<WENJIANBZ>100022.xml</WENJIANBZ><GESHILX>.XML</GESHILX><BIAOGEDM>100022</BIAOGEDM>"
            "<XIANGDUILJ>100022\\100022.xml</XIANGDUILJ><WENJIANMC>总委托书</WENJIANMC>",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "case.zip"
            path.write_bytes(
                _case_zip_bytes(
                    manifest=manifest,
                    extra_members={"10000021/100022/100022.xml": b"%PDF-1.7\nscanned"},
                )
            )

            with prepare_preview_package(path) as package:
                document = package.documents[0]
                self.assertEqual(document.display_name, "总委托书")
                self.assertEqual(set(package.pdf_paths_by_document_id), {document.id})
                self.assertEqual(package.xml_paths_by_document_id, {})
                self.assertEqual(package.errors_by_document_id, {})

    def test_image_attachment_is_passed_through_without_a_form_code(self) -> None:
        manifest = _attachment_manifest(
            "<WENJIANBZ>100023.png</WENJIANBZ><GESHILX>.PNG</GESHILX>"
            "<XIANGDUILJ>100023\\100023.png</XIANGDUILJ><WENJIANMC>扫描件</WENJIANMC>",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "case.zip"
            path.write_bytes(
                _case_zip_bytes(
                    manifest=manifest,
                    extra_members={"10000021/100023/100023.png": _png_bytes()},
                )
            )

            with prepare_preview_package(path) as package:
                self.assertEqual(set(package.pdf_paths_by_document_id), {package.documents[0].id})
                self.assertEqual(package.errors_by_document_id, {})

    def test_unrecognised_attachment_fails_alone(self) -> None:
        manifest = _attachment_manifest(
            "<BIAOGEDM>100001</BIAOGEDM><XIANGDUILJ>100001\\100001.xml</XIANGDUILJ><WENJIANMC>权利要求书</WENJIANMC>",
            "<WENJIANBZ>100099.doc</WENJIANBZ><XIANGDUILJ>100099\\100099.doc</XIANGDUILJ><WENJIANMC>中间文件</WENJIANMC>",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "case.zip"
            path.write_bytes(
                _case_zip_bytes(
                    manifest=manifest,
                    extra_members={"10000021/100099/100099.doc": b"\x00\x01\x02binary"},
                )
            )

            with prepare_preview_package(path) as package:
                by_name = {document.display_name: document for document in package.documents}
                self.assertEqual(set(package.xml_paths_by_document_id), {by_name["权利要求书"].id})
                self.assertEqual(package.pdf_paths_by_document_id, {})
                self.assertEqual(
                    package.errors_by_document_id,
                    {by_name["中间文件"].id: "附件无法并入预览：100099.doc 不是 PDF 也不是可识别的图片。"},
                )

    def test_xml_entry_without_a_form_code_still_fails(self) -> None:
        manifest = _attachment_manifest(
            "<WENJIANBZ>100001.xml</WENJIANBZ><XIANGDUILJ>100001\\100001.xml</XIANGDUILJ><WENJIANMC>权利要求书</WENJIANMC>",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "case.zip"
            path.write_bytes(_case_zip_bytes(manifest=manifest))

            with prepare_preview_package(path) as package:
                document = package.documents[0]
                self.assertIn("缺少文书类型", package.errors_by_document_id[document.id])
                self.assertEqual(package.pdf_paths_by_document_id, {})

    def test_inspects_manifest_without_starting_the_renderer(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "case.zip"
            path.write_bytes(_case_zip_bytes())

            result = inspect_preview_package(path)

        self.assertEqual([document.code for document in result.documents], list(_DEFAULT_PREVIEW_CODES))
        self.assertEqual(result.errors_by_document_id, {})

    def test_discovers_all_manifest_xml_entries_from_single_nested_zip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "bundle.zip"
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as outer:
                outer.writestr("10000021.zip", _case_zip_bytes())

            with prepare_preview_package(path) as package:
                self.assertEqual([document.code for document in package.documents], list(_DEFAULT_PREVIEW_CODES))
                self.assertEqual([document.display_name for document in package.documents], list(_DEFAULT_PREVIEW_NAMES))
                self.assertEqual(set(package.xml_paths_by_document_id), {document.id for document in package.documents})
                self.assertEqual(package.errors_by_document_id, {})

    def test_keeps_duplicate_codes_as_distinct_document_ids(self) -> None:
        entries = (("110401", "实质审查请求书一"), ("110401", "实质审查请求书二"))
        manifest = _manifest(entries)
        manifest = manifest.replace("110401\\110401.xml</XIANGDUILJ>", "110401\\first.xml</XIANGDUILJ>", 1)
        manifest = manifest.replace("110401\\110401.xml</XIANGDUILJ>", "110401\\second.xml</XIANGDUILJ>", 1)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "case.zip"
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("list.xml", manifest)
                archive.writestr("110401/first.xml", "<first/>")
                archive.writestr("110401/second.xml", "<second/>")

            with prepare_preview_package(path) as package:
                self.assertEqual(len(package.documents), 2)
                self.assertNotEqual(package.documents[0].id, package.documents[1].id)
                self.assertEqual(len(package.xml_paths_by_document_id), 2)

    def test_manifest_traversal_is_reported_per_document(self) -> None:
        manifest = _manifest((("100001", "权利要求书"),)).replace(
            "100001\\100001.xml", "..\\outside.xml"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "case.zip"
            path.write_bytes(_case_zip_bytes(manifest=manifest))

            with prepare_preview_package(path) as package:
                document = package.documents[0]
                self.assertNotIn(document.id, package.xml_paths_by_document_id)
                self.assertIn("文件路径不安全", package.errors_by_document_id[document.id])

    def test_unsafe_zip_member_is_rejected_before_manifest_parsing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "unsafe.zip"
            path.write_bytes(_case_zip_bytes(extra_members={"../outside.xml": b"<outside/>"}))

            with self.assertRaisesRegex(PreviewPackageError, "unsafe member path"):
                with prepare_preview_package(path):
                    pass

    def test_archive_over_budget_cleans_preview_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            path = root / "large.zip"
            workspace = root / "owned-workspace"
            workspace.mkdir()
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("100001.xml", b"<document/>" * 10)
            with patch("core.cnipa_preview.package.ArchiveBudget", return_value=ArchiveBudget(max_member_bytes=32)):
                with patch("core.cnipa_preview.package.tempfile.mkdtemp", return_value=str(workspace)):
                    with self.assertRaisesRegex(PreviewPackageError, "解压大小超出限制"):
                        with prepare_preview_package(path):
                            pass
            self.assertFalse(workspace.exists())


if __name__ == "__main__":
    unittest.main()
