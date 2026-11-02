import io
import stat
import unittest
import zipfile

from core.archive_safety import ArchiveBudget, ArchiveSafetyError


class ArchiveSafetyTests(unittest.TestCase):
    def test_validate_rejects_link_and_member_count(self) -> None:
        data = io.BytesIO()
        link = zipfile.ZipInfo("linked.xml")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        with zipfile.ZipFile(data, "w") as archive:
            archive.writestr("normal.xml", b"ok")
            archive.writestr(link, b"target")
        with zipfile.ZipFile(data, "r") as archive:
            with self.assertRaisesRegex(ArchiveSafetyError, "链接"):
                ArchiveBudget().validate(archive)
            with self.assertRaisesRegex(ArchiveSafetyError, "数量"):
                ArchiveBudget(max_members=1).validate(archive)
        win_data = io.BytesIO()
        win_link = zipfile.ZipInfo("windows-link.xml")
        win_link.create_system = 0
        win_link.external_attr = 0x400 << 16
        with zipfile.ZipFile(win_data, "w") as archive:
            archive.writestr(win_link, b"target")
        with zipfile.ZipFile(win_data, "r") as archive:
            with self.assertRaisesRegex(ArchiveSafetyError, "链接"):
                ArchiveBudget().validate(archive)

    def test_copy_counts_actual_bytes_even_if_header_understates_size(self) -> None:
        class FalseHeaderArchive:
            def open(self, _info, _mode):
                return io.BytesIO(b"12345")

        info = zipfile.ZipInfo("data.bin")
        info.file_size = 1
        with self.assertRaisesRegex(ArchiveSafetyError, "实际解压大小"):
            ArchiveBudget(max_member_bytes=4).copy(FalseHeaderArchive(), info, io.BytesIO())

    def test_validate_skips_directory_entries_including_bare_root(self) -> None:
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as archive:
            archive.writestr(zipfile.ZipInfo("/"), b"")
            archive.writestr("folder/", b"")
            archive.writestr("folder/notice.xml", b"ok")
        with zipfile.ZipFile(data, "r") as archive:
            infos = ArchiveBudget().validate(archive)
        self.assertEqual([info.filename for info in infos], ["/", "folder/", "folder/notice.xml"])

    def test_validate_still_rejects_absolute_file_entries(self) -> None:
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as archive:
            archive.writestr("/absolute/notice.xml", b"ok")
        with zipfile.ZipFile(data, "r") as archive:
            with self.assertRaisesRegex(ArchiveSafetyError, "路径不安全"):
                ArchiveBudget().validate(archive)


if __name__ == "__main__":
    unittest.main()
