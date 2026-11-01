from __future__ import annotations

import json
import socket
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from unittest.mock import patch

from core import regions_cn
from core.cnipa_preview import codeset_local

# Loopback traffic must never be diverted through a configured system proxy.
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _get(url: str, *, timeout: float = 5.0) -> tuple[int, str, str]:
    request = urllib.request.Request(url, method="GET")
    try:
        with _OPENER.open(request, timeout=timeout) as response:
            return int(response.status), str(response.headers.get("Content-Type", "")), response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return int(exc.code), str(exc.headers.get("Content-Type", "")), exc.read().decode("utf-8")


def _query(base_url: str, params: dict[str, str]) -> tuple[int, str, str]:
    separator = "&" if "?" in base_url else "?"
    return _get(f"{base_url}{separator}{urllib.parse.urlencode(params)}")


class LocalTableLookupTests(unittest.TestCase):
    def test_province_city_and_municipality_district_codes_resolve(self) -> None:
        cases = {
            ("SHENG", "330000"): "浙江省",
            ("SHI", "330100"): "杭州市",
            ("SHENG", "110000"): "北京市",
            ("SHI", "110101"): "东城区",
            ("SHI", "110100"): codeset_local.MUNICIPALITY_DISTRICT_NAME,
            ("SHENG", "820000"): "澳门特别行政区",
            ("SHENG", "810000"): "香港特别行政区",
        }
        for (code_type, code), expected in cases.items():
            with self.subTest(code_type=code_type, code=code):
                self.assertEqual(expected, codeset_local.resolve_codeset_name(code_type, code))

    def test_every_province_and_municipality_code_is_covered(self) -> None:
        table = codeset_local.region_names()
        for entry in regions_cn.PROVINCES:
            with self.subTest(code=entry["code"]):
                self.assertEqual(entry["name"], table[str(entry["code"])])
        for province_code in ("110000", "120000", "310000", "500000"):
            with self.subTest(province=province_code):
                self.assertEqual(
                    codeset_local.MUNICIPALITY_DISTRICT_NAME, table[province_code[:2] + "0100"],
                )

    def test_country_codes_ignore_case_and_surrounding_whitespace(self) -> None:
        for code in ("CN", "cn", " Cn "):
            with self.subTest(code=code):
                self.assertEqual("中国", codeset_local.resolve_codeset_name("GUOBIE", code))
        self.assertEqual("美国", codeset_local.resolve_codeset_name("guobie", " us "))
        self.assertEqual("中国台湾", codeset_local.resolve_codeset_name("GUOBIE", "TW"))

    def test_unknown_values_keep_the_raw_code(self) -> None:
        cases = {
            "未知国别": ("GUOBIE", "ZZ"),
            "代理机构代码默认不翻译": ("DLJGDM", "北京某某专利代理事务所"),
            "未知类型": ("QITA", "cn"),
            "国别代码是中文": ("GUOBIE", "中国"),
            "地区代码不存在": ("SHENG", "990000"),
        }
        for label, (code_type, code) in cases.items():
            with self.subTest(label):
                self.assertEqual(code, codeset_local.resolve_codeset_name(code_type, code))

    def test_empty_and_missing_codes_produce_an_empty_body(self) -> None:
        for code_type, code in (("GUOBIE", ""), ("SHENG", "   "), ("", ""), ("GUOBIE", None)):
            with self.subTest(code_type=code_type, code=code):
                self.assertEqual("", codeset_local.resolve_codeset_name(code_type, code))

    def test_optional_agency_lookup_is_used_only_when_injected(self) -> None:
        def lookup(code: str) -> str:
            return {"12345": "某某专利代理事务所"}.get(code, "")

        self.assertEqual(
            "某某专利代理事务所",
            codeset_local.resolve_codeset_name("DLJGDM", "12345", agency_lookup=lookup),
        )
        self.assertEqual("99999", codeset_local.resolve_codeset_name("DLJGDM", "99999", agency_lookup=lookup))


class CountryResourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.path = Path(__file__).resolve().parents[1] / "resources" / codeset_local.COUNTRY_RESOURCE_FILE

    def test_resource_exists_and_is_parsable_utf8(self) -> None:
        self.assertTrue(self.path.is_file(), f"缺少资源文件：{self.path}")
        self.assertIsInstance(json.loads(self.path.read_text(encoding="utf-8")), dict)

    def test_resource_documents_its_source_and_fallback(self) -> None:
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        note = str(raw.get("_note", "")).strip()
        self.assertTrue(note, "国别表缺少 _note 说明")
        self.assertIn("原值", note)

    def test_resource_covers_the_common_countries(self) -> None:
        table = codeset_local.country_names()
        self.assertEqual("中国", table["CN"])
        self.assertGreaterEqual(len(table), 50)
        for code in ("US", "JP", "KR", "DE", "FR", "GB", "RU", "CA", "AU", "IN", "SG", "HK", "TW"):
            with self.subTest(code=code):
                self.assertIn(code, table)


class RequestQueryDecodingTests(unittest.TestCase):
    def test_percent_encoded_values_pass_through(self) -> None:
        self.assertEqual("codeType=GUOBIE&code=CN", codeset_local.restore_request_text("codeType=GUOBIE&code=CN"))
        self.assertEqual("code=%E6%9D%AD", codeset_local.restore_request_text("code=%E6%9D%AD"))

    def test_latin1_request_line_view_is_restored_to_utf8(self) -> None:
        name = "杭州君度专利代理事务所（特殊普通合伙）"
        latin1_view = name.encode("utf-8").decode("latin-1")
        self.assertEqual(name, codeset_local.restore_request_text(latin1_view))

    def test_values_that_are_not_utf8_are_kept_as_is(self) -> None:
        raw = "\xff\xfe\x00"
        self.assertEqual(raw, codeset_local.restore_request_text(raw))


class LocalCodesetServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = codeset_local.LocalCodesetServer()
        self.addCleanup(self.server.stop)

    def test_start_serves_the_code_set_route_on_loopback_only(self) -> None:
        base_url = self.server.start()
        parts = urllib.parse.urlsplit(base_url)
        self.assertEqual("http", parts.scheme)
        self.assertEqual("127.0.0.1", parts.hostname)
        self.assertNotEqual(9999, parts.port)
        self.assertEqual(codeset_local.CODESET_PATH, parts.path)
        self.assertEqual(base_url, self.server.base_url)

        status, content_type, body = _query(base_url, {"codeType": "GUOBIE", "code": "cn"})
        self.assertEqual(200, status)
        self.assertIn("text/plain", content_type.lower())
        self.assertIn("charset=UTF-8", content_type)
        self.assertEqual("中国", body)

    def test_other_paths_are_not_found(self) -> None:
        base_url = self.server.start()
        origin = f"{urllib.parse.urlsplit(base_url).scheme}://{urllib.parse.urlsplit(base_url).netloc}"
        for path in ("/", "/public-base/codeset", "/public-base/codeset/findByCodes", "/v2/api-docs"):
            with self.subTest(path=path):
                status, _content_type, _body = _get(f"{origin}{path}")
                self.assertEqual(404, status)

    def test_other_methods_are_not_served(self) -> None:
        base_url = self.server.start()
        parts = urllib.parse.urlsplit(base_url)
        request = (
            f"POST {codeset_local.CODESET_PATH} HTTP/1.1\r\nHost: 127.0.0.1\r\n"
            "Content-Length: 0\r\nConnection: close\r\n\r\n"
        ).encode("ascii")
        with socket.create_connection((parts.hostname, parts.port), timeout=5.0) as connection:
            connection.sendall(request)
            head = connection.recv(4096)
        self.assertIn(b"404", head.split(b"\r\n")[0])

    def test_missing_query_values_return_an_empty_body(self) -> None:
        base_url = self.server.start()
        for params in ({}, {"codeType": "GUOBIE"}, {"codeType": "", "code": "  "}):
            with self.subTest(params=params):
                status, content_type, body = _query(base_url, params)
                self.assertEqual(200, status)
                self.assertIn("text/plain", content_type.lower())
                self.assertEqual("", body)

    def test_injected_agency_lookup_is_served(self) -> None:
        server = codeset_local.LocalCodesetServer(agency_lookup=lambda code: "某某专利代理事务所")
        self.addCleanup(server.stop)
        base_url = server.start()
        status, _content_type, body = _query(base_url, {"codeType": "DLJGDM", "code": "1234567"})
        self.assertEqual(200, status)
        self.assertEqual("某某专利代理事务所", body)

    def test_percent_encoded_agency_name_is_echoed_as_is(self) -> None:
        base_url = self.server.start()
        name = "杭州君度专利代理事务所（特殊普通合伙）"
        status, _content_type, body = _query(base_url, {"codeType": "DLJGDM", "code": name})
        self.assertEqual(200, status)
        self.assertEqual(name, body)

    def test_raw_utf8_agency_name_in_the_request_line_is_decoded(self) -> None:
        # The renderer puts the agency name in the query as raw UTF-8 bytes, not percent-encoded.
        base_url = self.server.start()
        parts = urllib.parse.urlsplit(base_url)
        name = "杭州君度专利代理事务所（特殊普通合伙）"
        request = (
            f"GET {codeset_local.CODESET_PATH}?codeType=DLJGDM&code=".encode("ascii")
            + name.encode("utf-8")
            + b" HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n"
        )
        with socket.create_connection((parts.hostname, parts.port), timeout=5.0) as connection:
            connection.sendall(request)
            chunks = []
            while True:
                chunk = connection.recv(4096)
                if not chunk:
                    break
                chunks.append(chunk)
        head, _separator, body = b"".join(chunks).partition(b"\r\n\r\n")
        self.assertIn(b"200", head.split(b"\r\n")[0])
        self.assertEqual(name, body.decode("utf-8"))

    def test_self_check_failure_is_reported_as_unavailable(self) -> None:
        with patch.object(codeset_local, "_answers_self_check", return_value=False):
            self.assertEqual("", self.server.start())
        self.assertEqual("", self.server.base_url)

    def test_start_is_reentrant_and_stop_releases_the_port(self) -> None:
        base_url = self.server.start()
        self.assertEqual(base_url, self.server.start())
        port = urllib.parse.urlsplit(base_url).port
        self.server.stop()
        self.assertEqual("", self.server.base_url)
        with self.assertRaises((urllib.error.URLError, OSError)):
            _get(f"{base_url}?codeType=GUOBIE&code=CN", timeout=2.0)
        self.assertFalse(_port_accepts_connections(port))
        self.server.stop()
        restarted = self.server.start()
        self.assertEqual("中国", _query(restarted, {"codeType": "GUOBIE", "code": "CN"})[2])


class SharedLocalCodesetServerTests(unittest.TestCase):
    def test_one_process_wide_instance_serves_every_caller(self) -> None:
        self.addCleanup(codeset_local.stop_local_codeset_server)
        first = codeset_local.start_local_codeset_server()
        second = codeset_local.start_local_codeset_server()
        self.assertTrue(first)
        self.assertEqual(first, second)
        self.assertIs(codeset_local.get_local_codeset_server(), codeset_local.get_local_codeset_server())
        self.assertEqual("浙江省", _query(first, {"codeType": "SHENG", "code": "330000"})[2])
        codeset_local.stop_local_codeset_server()
        self.assertEqual("", codeset_local.get_local_codeset_server().base_url)


def _port_accepts_connections(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(1.0)
        return probe.connect_ex(("127.0.0.1", port)) == 0


if __name__ == "__main__":
    unittest.main()
