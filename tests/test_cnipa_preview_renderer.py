from __future__ import annotations

import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

from core.cnipa_preview.package import prepare_preview_package
from core.cnipa_preview.renderer import CnipaXmlRenderer
from core.cnipa_preview.form_renderer import FormRenderCancelled


_DOCS = (
    ("100001", "权利要求书"),
    ("100002", "说明书"),
    ("100003", "说明书附图"),
    ("100004", "说明书摘要"),
    ("110101", "发明专利请求书"),
    ("110401", "实质审查请求书"),
)

_DEFAULT_PREVIEW_CODES = ("110101", "110401", "100004", "100001", "100002", "100003")
_DEFAULT_PREVIEW_NAMES = ("发明专利请求书", "实质审查请求书", "说明书摘要", "权利要求书", "说明书", "说明书附图")


def _case_zip_bytes() -> bytes:
    manifest = ["<?xml version='1.0' encoding='UTF-8'?><data-bus><WENJIANBYSXX>"]
    for code, name in _DOCS:
        manifest.append(
            "<BAONEIWJXX>"
            f"<BIAOGEDM>{code}</BIAOGEDM>"
            f"<XIANGDUILJ>{code}\\{code}.xml</XIANGDUILJ>"
            f"<WENJIANMC>{name}</WENJIANMC>"
            "</BAONEIWJXX>"
        )
    manifest.append("</WENJIANBYSXX></data-bus>")
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("list.xml", "".join(manifest))
        for code, _ in _DOCS:
            archive.writestr(f"{code}/{code}.xml", f"<document code='{code}'/>")
    return data.getvalue()


class _Service:
    def __init__(self) -> None:
        self.calls = 0

    def ensure_running(self, *, startup_wait_callback=None) -> str:
        self.calls += 1
        if startup_wait_callback is not None:
            startup_wait_callback(12.0)
        return "http://127.0.0.1:19123"


class _Response:
    def __init__(self, *, content: bytes, status_code: int = 200, text: str = "") -> None:
        self.content = content
        self.status_code = status_code
        self.text = text


def _manifest_zip_bytes(entries: tuple[str, ...], members: dict[str, bytes]) -> bytes:
    """Write one case package whose manifest holds exactly the given BAONEIWJXX bodies."""
    manifest = (
        "<?xml version='1.0' encoding='UTF-8'?><data-bus><WENJIANBYSXX>"
        + "".join(f"<BAONEIWJXX>{entry}</BAONEIWJXX>" for entry in entries)
        + "</WENJIANBYSXX></data-bus>"
    )
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("list.xml", manifest)
        for name, payload in members.items():
            archive.writestr(name, payload)
    return data.getvalue()


class CnipaPreviewRendererTests(unittest.TestCase):
    def test_opinion_statement_routes_main_and_sibling_to_private_library(self) -> None:
        service = _Service()
        service.ensure_runtime = Mock(return_value=object())
        manifest = (
            "<data-bus><WENJIANBYSXX><BAONEIWJXX><BIAOGEDM>100012</BIAOGEDM>"
            "<XIANGDUILJ>100012/100012.xml</XIANGDUILJ><WENJIANMC>意见陈述书</WENJIANMC>"
            "</BAONEIWJXX></WENJIANBYSXX></data-bus>"
        )
        def render(_layout, xml_path, **kwargs):
            self.assertEqual(xml_path.read_text(encoding="utf-8"), "<意见陈述书/>")
            self.assertEqual(xml_path.with_name("section_1.xml").read_bytes(), b"<cn-other-file/>")
            self.assertEqual(xml_path.with_name("zjwj_1.jpg").read_bytes(), b"image")
            return b"%PDF-1.7\nform-with-section"

        http = Mock(side_effect=AssertionError("Opinion must not use the entity-dependent HTTP endpoint"))
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "case.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("list.xml", manifest)
                archive.writestr("100012/100012.xml", "<意见陈述书/>")
                archive.writestr("100012/section_1.xml", "<cn-other-file/>")
                archive.writestr("100012/zjwj_1.jpg", b"image")
            renderer = CnipaXmlRenderer(service, request_get=http)
            with patch("core.cnipa_preview.renderer.render_opinion_pdf", side_effect=render) as helper:
                result = renderer.render_case(str(path))
                self.assertEqual(len(result.pdf_by_document_id), 1)
                self.assertEqual(result.errors_by_document_id, {})
                renderer.render_case(str(path), selected_document_ids=())
                self.assertEqual(helper.call_count, 1)
            with patch("core.cnipa_preview.renderer.render_opinion_pdf", side_effect=FormRenderCancelled):
                result = renderer.render_case(str(path))
                self.assertTrue(result.cancelled)
                self.assertEqual(result.pdf_by_document_id, {})
        http.assert_not_called()

    def test_passthrough_attachment_renders_without_starting_the_service(self) -> None:
        attachment_bytes = b"%PDF-1.7\nsigned attachment\n" + b"payload" * 8
        case = _manifest_zip_bytes(
            (
                "<WENJIANBZ>100022.pdf</WENJIANBZ><GESHILX>.PDF</GESHILX>"
                "<XIANGDUILJ>100022\\100022.pdf</XIANGDUILJ><WENJIANMC>总委托书</WENJIANMC>",
            ),
            {"100022/100022.pdf": attachment_bytes},
        )
        service = _Service()
        http = Mock(side_effect=AssertionError("Attachments must not be sent to the official renderer"))
        renderer = CnipaXmlRenderer(service, request_get=http)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "case.zip"
            path.write_bytes(case)
            result = renderer.render_case(str(path))

        self.assertEqual(service.calls, 0)
        self.assertEqual(result.errors_by_document_id, {})
        self.assertEqual(
            [document.display_name for document in result.documents if document.id in result.pdf_by_document_id],
            ["总委托书"],
        )
        self.assertEqual(result.passthrough_document_ids, frozenset(document.id for document in result.documents))
        self.assertEqual(next(iter(result.pdf_by_document_id.values())), attachment_bytes)
        http.assert_not_called()

    def test_xml_and_attachment_keep_the_manifest_order(self) -> None:
        received: list[str] = []

        def fake_get(_url: str, **kwargs):
            received.append(kwargs["params"]["wenjianlx"])
            return _Response(content=b"%PDF-1.7\nmock")

        attachment_bytes = b"%PDF-1.7\nattachment"
        case = _manifest_zip_bytes(
            (
                "<BIAOGEDM>100001</BIAOGEDM><XIANGDUILJ>100001\\100001.xml</XIANGDUILJ><WENJIANMC>权利要求书</WENJIANMC>",
                "<WENJIANBZ>100022.pdf</WENJIANBZ><GESHILX>.PDF</GESHILX>"
                "<XIANGDUILJ>100022\\100022.pdf</XIANGDUILJ><WENJIANMC>总委托书</WENJIANMC>",
                "<BIAOGEDM>100002</BIAOGEDM><XIANGDUILJ>100002\\100002.xml</XIANGDUILJ><WENJIANMC>说明书</WENJIANMC>",
            ),
            {
                "100001/100001.xml": b"<document code='100001'/>",
                "100002/100002.xml": b"<document code='100002'/>",
                "100022/100022.pdf": attachment_bytes,
            },
        )
        renderer = CnipaXmlRenderer(_Service(), request_get=fake_get)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "case.zip"
            path.write_bytes(case)
            result = renderer.render_case(str(path))

        self.assertEqual(received, ["100001", "100002"])
        self.assertEqual(
            [document.display_name for document in result.documents],
            ["权利要求书", "说明书", "总委托书"],
        )
        attachment_id = result.documents[2].id
        self.assertEqual(result.pdf_by_document_id[attachment_id], attachment_bytes)
        self.assertEqual(result.passthrough_document_ids, frozenset({attachment_id}))
        self.assertEqual(len(result.pdf_by_document_id), 3)
        self.assertEqual(result.errors_by_document_id, {})

    def test_renders_every_manifest_entry_in_default_preview_order(self) -> None:
        received: list[dict[str, str]] = []

        def fake_get(url: str, **kwargs):
            self.assertEqual(url, "http://127.0.0.1:19123/preview/xml2pdf")
            received.append(dict(kwargs["params"]))
            return _Response(content=b"%PDF-1.7\nmock")

        service = _Service()
        renderer = CnipaXmlRenderer(service, request_get=fake_get)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "case.zip"
            path.write_bytes(_case_zip_bytes())
            result = renderer.render_case(str(path))

        self.assertEqual(service.calls, 1)
        self.assertEqual([item["wenjianlx"] for item in received], list(_DEFAULT_PREVIEW_CODES))
        self.assertEqual(len(result.pdf_by_document_id), 6)
        self.assertEqual(result.errors_by_document_id, {})
        self.assertEqual(
            [document.display_name for document in result.documents if document.id in result.pdf_by_document_id],
            list(_DEFAULT_PREVIEW_NAMES),
        )
        self.assertTrue(all(Path(item["filepath"]).name.endswith(".xml") for item in received))
        self.assertTrue(all(item["wenjianbs"].startswith("preview-") for item in received))

    def test_keeps_successes_when_one_document_has_an_official_error(self) -> None:
        def fake_get(_url: str, **kwargs):
            code = kwargs["params"]["wenjianlx"]
            if code == "110401":
                return _Response(content=b"form is not supported", status_code=500, text="form is not supported")
            return _Response(content=b"%PDF-1.7\nmock")

        renderer = CnipaXmlRenderer(_Service(), request_get=fake_get)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "case.zip"
            path.write_bytes(_case_zip_bytes())
            result = renderer.render_case(str(path))

        failed = next(document for document in result.documents if document.code == "110401")
        self.assertEqual(len(result.pdf_by_document_id), 5)
        self.assertIn("HTTP 500", result.errors_by_document_id[failed.id])
        self.assertIn("form is not supported", result.errors_by_document_id[failed.id])

    def test_renders_only_selected_documents_in_user_supplied_order(self) -> None:
        received: list[str] = []

        def fake_get(_url: str, **kwargs):
            received.append(kwargs["params"]["wenjianlx"])
            return _Response(content=b"%PDF-1.7\nmock")

        renderer = CnipaXmlRenderer(_Service(), request_get=fake_get)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "case.zip"
            path.write_bytes(_case_zip_bytes())
            with prepare_preview_package(path) as package:
                documents = tuple(document for document in package.documents if document.code in {"100001", "110401"})
            ordered_documents = tuple(reversed(documents))
            result = renderer.render_case(
                str(path),
                documents=ordered_documents,
                selected_document_ids=tuple(document.id for document in ordered_documents),
            )

        self.assertEqual(received, ["100001", "110401"])
        self.assertEqual([document.code for document in result.documents], ["100001", "110401"])
        self.assertEqual(len(result.pdf_by_document_id), 2)

    def test_stops_before_next_document_when_cancelled(self) -> None:
        calls = 0

        def fake_get(_url: str, **_kwargs):
            nonlocal calls
            calls += 1
            return _Response(content=b"%PDF-1.7\nmock")

        def cancelled() -> bool:
            return calls >= 2

        renderer = CnipaXmlRenderer(_Service(), request_get=fake_get)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "case.zip"
            path.write_bytes(_case_zip_bytes())
            result = renderer.render_case(str(path), cancelled=cancelled)

        self.assertTrue(result.cancelled)
        self.assertEqual(calls, 2)
        self.assertEqual(len(result.pdf_by_document_id), 2)

    def test_forwards_cold_start_wait_updates_to_caller(self) -> None:
        received: list[float] = []

        def fake_get(_url: str, **_kwargs):
            return _Response(content=b"%PDF-1.7\nmock")

        service = _Service()
        renderer = CnipaXmlRenderer(service, request_get=fake_get)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "case.zip"
            path.write_bytes(_case_zip_bytes())
            renderer.render_case(str(path), startup_wait=received.append)

        self.assertEqual([12.0], received)


if __name__ == "__main__":
    unittest.main()
