import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from core.archive_safety import ArchiveBudget, ArchiveSafetyError
from core.official_docs import NoticeInputBundle, parse_official_notice_archive, resolve_notice_inputs
from core.official_docs.zip_reader import NoticeZipReader


_NOTICE_LIST_XML = (
    "<NOTICE><FAWENXLH>2026103002872730</FAWENXLH>"
    "<SHUXINGXX><SHENQINGH>2026112333022</SHENQINGH>"
    "<TONGZHISBM>210407</TONGZHISBM><TONGZHISMC>驳回决定通知书</TONGZHISMC>"
    "<FAWENR>2026-10-30</FAWENR></SHUXINGXX></NOTICE>"
).encode("utf-8")


class OfficialDocsInputResolverTests(unittest.TestCase):
    def test_notice_zip_reader_cleans_resources_when_inner_open_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source = self._make_outer_zip(Path(td), "bad-inner.zip", {"inner.zip": b"not a ZIP"})
            reader = NoticeZipReader(str(source))
            opened: list[zipfile.ZipFile] = []
            spooled: list[io.BufferedRandom] = []
            real_zip_file = zipfile.ZipFile
            real_temp_file = tempfile.TemporaryFile

            def tracked_zip_file(*args, **kwargs):
                archive = real_zip_file(*args, **kwargs)
                opened.append(archive)
                return archive

            def tracked_temp_file(*args, **kwargs):
                output = real_temp_file(*args, **kwargs)
                spooled.append(output)
                return output

            with patch("core.official_docs.zip_reader.zipfile.ZipFile", side_effect=tracked_zip_file):
                with patch("core.official_docs.zip_reader.tempfile.TemporaryFile", side_effect=tracked_temp_file):
                    with self.assertRaises(zipfile.BadZipFile):
                        reader.__enter__()
            self.assertIsNone(reader._outer)
            self.assertIsNone(reader._inner_buf)
            self.assertIsNone(reader._active)
            self.assertTrue(opened and all(archive.fp is None for archive in opened))
            self.assertTrue(spooled and all(output.closed for output in spooled))

    def test_notice_zip_reader_limits_cumulative_reads(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source = self._make_outer_zip(Path(td), "notice.zip", {"notice.pdf": b"12345678"})
            with patch("core.official_docs.zip_reader.ArchiveBudget", return_value=ArchiveBudget(max_total_bytes=12)):
                with NoticeZipReader(str(source)) as reader:
                    self.assertEqual(reader.read_bytes("notice.pdf"), b"12345678")
                    with self.assertRaisesRegex(ArchiveSafetyError, "实际解压大小"):
                        reader.read_bytes("notice.pdf")

    def test_corrupt_child_is_reported_while_valid_sibling_remains(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            outer = root / "bundle.zip"
            with zipfile.ZipFile(outer, "w", compression=zipfile.ZIP_STORED) as zf:
                zf.writestr("A.zip", b"BROKEN_A")
                zf.writestr("B.zip", b"PK\x05\x06" + b"\x00" * 18)
            outer.write_bytes(outer.read_bytes().replace(b"BROKEN_A", b"BROKEN_B", 1))

            result = resolve_notice_inputs([str(outer)], temp_root_dir=str(root / "temp"))

            self.assertEqual([leaf.inner_zip_name for leaf in result.leaves], ["B.zip"])
            self.assertEqual(len(result.ignored), 1)
            self.assertEqual(result.ignored[0].source_path, str(outer))
            self.assertEqual(result.ignored[0].display_name, "A.zip")
            self.assertIn("CRC", result.ignored[0].reason)
            self.assertEqual(len(list((root / "temp").glob("*.zip"))), 1)

    def test_invalid_inner_zip_and_unsafe_inner_member_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inner = io.BytesIO()
            with zipfile.ZipFile(inner, "w") as zf:
                zf.writestr("../escape.pdf", b"payload")
            outer = self._make_outer_zip(root, "bundle.zip", {
                "A.zip": b"not a ZIP",
                "B.zip": b"PK\x05\x06" + b"\x00" * 18,
                "C.zip": inner.getvalue(),
            })

            result = resolve_notice_inputs([str(outer)], temp_root_dir=str(root / "temp"))

            self.assertEqual([leaf.inner_zip_name for leaf in result.leaves], ["B.zip"])
            self.assertEqual([item.display_name for item in result.ignored], ["A.zip", "C.zip"])
            self.assertIn("File is not a zip file", result.ignored[0].reason)
            self.assertIn("路径不安全", result.ignored[1].reason)
            self.assertEqual(len(list((root / "temp").glob("*.zip"))), 1)

    def test_single_nested_zip_in_each_child_shares_outer_budget(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            innermost = b"PK\x05\x06" + b"\x00" * 18
            child_buffer = io.BytesIO()
            with zipfile.ZipFile(child_buffer, "w", compression=zipfile.ZIP_STORED) as zf:
                zf.writestr("inner.zip", innermost)
                zf.writestr("empty-dir\\", b"")
            child = child_buffer.getvalue()
            outer = self._make_outer_zip(root, "bundle.zip", {"A.zip": child, "B.zip": child})
            limit = len(child) * 2 + len(innermost) + 1

            with patch("core.official_docs.input_resolver.ArchiveBudget", side_effect=lambda: ArchiveBudget(max_total_bytes=limit)):
                result = resolve_notice_inputs([str(outer)], temp_root_dir=str(root / "temp"))

            self.assertEqual([leaf.inner_zip_name for leaf in result.leaves], ["A.zip"])
            self.assertEqual([item.display_name for item in result.ignored], ["B.zip"])
            self.assertIn("总解压大小超出限制", result.ignored[0].reason)
            with NoticeZipReader(result.leaves[0].zip_path) as reader:
                self.assertEqual(reader.iter_entries(), [])

    def test_bare_root_directory_entry_does_not_block_outer_archive(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            zip_path = root / "notice.zip"
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.writestr(zipfile.ZipInfo("/"), b"")
                zf.writestr("list.xml", _NOTICE_LIST_XML)
                zf.writestr("210407.pdf", b"%PDF-1.4\n")

            result = resolve_notice_inputs([str(zip_path)], temp_root_dir=str(root / "temp"))

            self.assertEqual(len(result.leaves), 1)
            self.assertEqual(result.ignored, [])

    def test_bare_root_directory_entry_inside_single_inner_zip_parses(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inner = io.BytesIO()
            with zipfile.ZipFile(inner, "w") as zf:
                zf.writestr(zipfile.ZipInfo("/"), b"")
                zf.writestr("list.xml", _NOTICE_LIST_XML)
                zf.writestr("210407.pdf", b"%PDF-1.4\n")
            outer = self._make_outer_zip(root, "notice.zip", {"inner.zip": inner.getvalue()})

            result = resolve_notice_inputs([str(outer)], temp_root_dir=str(root / "temp"))

            self.assertEqual(len(result.leaves), 1)
            self.assertEqual(result.ignored, [])
            parsed = parse_official_notice_archive(result.leaves[0].zip_path)
            self.assertEqual(parsed.errors, [])
            self.assertEqual(parsed.meta.notice_code, "210407")
            self.assertEqual([source.display_name for source in parsed.pdf_entries], ["210407.pdf"])

    def _make_outer_zip(self, root: Path, name: str, entries: dict[str, bytes]) -> Path:
        zip_path = root / name
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for entry_name, payload in entries.items():
                zf.writestr(entry_name, payload)
        return zip_path

    def test_bundle_zip_is_expanded_to_multiple_leaves(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            temp_root = root / "temp"
            temp_root.mkdir(parents=True, exist_ok=True)

            outer_zip = self._make_outer_zip(
                root,
                "bundle.zip",
                {
                    "A.zip": b"PK\x05\x06" + b"\x00" * 18,
                    "B.zip": b"PK\x05\x06" + b"\x00" * 18,
                },
            )

            result = resolve_notice_inputs([str(outer_zip)], temp_root_dir=str(temp_root))
            self.assertEqual(len(result.nodes), 1)
            self.assertEqual(result.ignored, [])
            bundle = result.nodes[0]
            self.assertIsInstance(bundle, NoticeInputBundle)
            self.assertEqual(len(bundle.children), 2)
            self.assertEqual(len(result.leaves), 2)
            self.assertEqual(
                [leaf.source_label for leaf in result.leaves],
                ["bundle.zip > A.zip", "bundle.zip > B.zip"],
            )
            for leaf in result.leaves:
                self.assertTrue(str(leaf.zip_path).lower().endswith(".zip"))
                self.assertTrue(Path(leaf.zip_path).exists())
                self.assertTrue(Path(leaf.zip_path).is_file())

    def test_flat_multi_pdf_defaults_to_split_each_pdf_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            temp_root = root / "temp"
            temp_root.mkdir(parents=True, exist_ok=True)

            outer_zip = self._make_outer_zip(
                root,
                "flat.zip",
                {
                    "1 (1).pdf": b"%PDF-1.4\none\n",
                    "1 (2).pdf": b"%PDF-1.4\ntwo\n",
                },
            )

            result = resolve_notice_inputs([str(outer_zip)], temp_root_dir=str(temp_root))

            self.assertEqual(len(result.nodes), 1)
            self.assertEqual(result.ignored, [])
            bundle = result.nodes[0]
            self.assertIsInstance(bundle, NoticeInputBundle)
            self.assertEqual(bundle.display_name, "flat")
            self.assertEqual(len(bundle.children), 2)
            self.assertEqual(
                [leaf.source_label for leaf in bundle.children],
                ["flat.zip > 1 (1).pdf", "flat.zip > 1 (2).pdf"],
            )
            self.assertEqual(
                [leaf.inner_zip_name for leaf in bundle.children],
                ["1 (1).pdf", "1 (2).pdf"],
            )

            for leaf in bundle.children:
                self.assertTrue(Path(leaf.zip_path).exists())
                with NoticeZipReader(leaf.zip_path) as reader:
                    pdf_entries = reader.iter_pdfs()
                self.assertEqual(len(pdf_entries), 1)
                self.assertEqual(pdf_entries[0].display_name, leaf.inner_zip_name)

    def test_flat_multi_pdf_can_stay_merge_all_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            temp_root = root / "temp"
            temp_root.mkdir(parents=True, exist_ok=True)

            outer_zip = self._make_outer_zip(
                root,
                "flat-merge.zip",
                {
                    "A.pdf": b"%PDF-1.4\none\n",
                    "B.pdf": b"%PDF-1.4\ntwo\n",
                },
            )

            result = resolve_notice_inputs(
                [str(outer_zip)],
                temp_root_dir=str(temp_root),
                no_list_multi_pdf_mode="merge_all",
            )

            self.assertEqual(len(result.nodes), 1)
            self.assertEqual(len(result.leaves), 1)
            self.assertEqual(result.ignored, [])
            leaf = result.leaves[0]
            self.assertEqual(Path(leaf.zip_path), outer_zip)
            self.assertEqual(leaf.source_label, "")

    def test_mixed_child_zip_and_flat_pdf_is_ignored_with_clear_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            temp_root = root / "temp"
            temp_root.mkdir(parents=True, exist_ok=True)

            outer_zip = self._make_outer_zip(
                root,
                "mixed.zip",
                {
                    "child.zip": b"PK\x05\x06" + b"\x00" * 18,
                    "notice.pdf": b"%PDF-1.4\nchild\n",
                },
            )

            result = resolve_notice_inputs([str(outer_zip)], temp_root_dir=str(temp_root))

            self.assertEqual(result.nodes, [])
            self.assertEqual(result.leaves, [])
            self.assertEqual(len(result.ignored), 1)
            ignored = result.ignored[0]
            self.assertEqual(ignored.display_name, "mixed.zip")
            self.assertIn("子 ZIP 与平铺 PDF 混合", ignored.reason)
            self.assertEqual(ignored.source_path, str(outer_zip))


if __name__ == "__main__":
    unittest.main()
