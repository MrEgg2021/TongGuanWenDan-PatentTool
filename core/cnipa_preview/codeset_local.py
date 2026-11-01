from __future__ import annotations

import atexit
import http.client
import http.server
import json
import logging
import socketserver
import threading
import urllib.parse
from functools import lru_cache
from typing import Callable

from core.paths_utils import get_resource_path
from core.regions_cn import CITIES_BY_PROVINCE, PROVINCES

_LOGGER = logging.getLogger(__name__)

# The official xml2pdf library resolves form code-set values over one HTTP route.  When
# the installed client is not running this module serves that route from data we ship,
# so country and province/city fields render as Chinese names without the client.
CODESET_PATH = "/public-base/codeset/findByCode"
COUNTRY_RESOURCE_FILE = "codeset_local_guobie.json"
COUNTRY_CODE_TYPE = "GUOBIE"
PROVINCE_CODE_TYPE = "SHENG"
CITY_CODE_TYPE = "SHI"
AGENCY_CODE_TYPE = "DLJGDM"
SELF_CHECK_COUNTRY_CODE = "CN"
SELF_CHECK_TIMEOUT_SECONDS = 1.0
_SELF_CHECK_BODY_LIMIT = 512
_REGION_CODE_TYPES = frozenset({PROVINCE_CODE_TYPE, CITY_CODE_TYPE})
EMPTY_BODY = ""
# GB/T 2260 uses one "市辖区" entry per direct-controlled municipality; the shipped
# province/city constant file carries their districts but not that row.
MUNICIPALITY_DISTRICT_NAME = "市辖区"
_MUNICIPALITY_CODES = ("110000", "120000", "310000", "500000")
# Present in the city map but not in the province list of the generated constant file.
_PROVINCE_NAME_SUPPLEMENTS = {"810000": "香港特别行政区", "820000": "澳门特别行政区"}


@lru_cache(maxsize=1)
def country_names() -> dict[str, str]:
    """GUOBIE table (upper-case two-letter code -> Chinese short name); unreadable file means empty."""
    path = get_resource_path(COUNTRY_RESOURCE_FILE)
    try:
        with open(path, "r", encoding="utf-8") as stream:
            raw = json.load(stream)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        _LOGGER.warning("本机码表国别表不可读：%s（%s）；国别字段将显示原值。", path, exc)
        return {}
    if not isinstance(raw, dict):
        _LOGGER.warning("本机码表国别表格式无效：%s；国别字段将显示原值。", path)
        return {}
    table: dict[str, str] = {}
    for key, value in raw.items():
        code = str(key).strip().upper()
        name = str(value).strip()
        if not code or code.startswith("_") or not name:
            continue
        table[code] = name
    return table


@lru_cache(maxsize=1)
def region_names() -> dict[str, str]:
    """Province and city names keyed by their administrative code, plus the two supplements."""
    table: dict[str, str] = {}
    for entry in PROVINCES:
        table[str(entry["code"])] = str(entry["name"])
    table.update(_PROVINCE_NAME_SUPPLEMENTS)
    for cities in CITIES_BY_PROVINCE.values():
        for entry in cities:
            table[str(entry["code"])] = str(entry["name"])
    for province_code in _MUNICIPALITY_CODES:
        table[province_code[:2] + "0100"] = MUNICIPALITY_DISTRICT_NAME
    return table


def restore_request_text(text: str) -> str:
    """Undo ``http.server``'s latin-1 request-line decoding so raw UTF-8 query values survive.

    The renderer sends an agency name as raw UTF-8 bytes in the query string, which the
    standard library hands us as one character per byte. Percent-encoded values are
    unaffected: they are ASCII, so the round trip leaves them for ``parse_qs`` to decode.
    """
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError) as exc:
        _LOGGER.debug("码表查询参数不是 UTF-8，按原样处理：%s（%s）", text, exc)
        return text


def resolve_codeset_name(
    code_type: str,
    code: str,
    *,
    agency_lookup: Callable[[str], str] | None = None,
) -> str:
    """Return the local name for one code, or the code itself when this table cannot translate it.

    Both region code types share one administrative-code table: every code in it is
    unambiguous, so a province code in a city field still resolves to the right name.
    """
    text = str(code or "").strip()
    if not text:
        return EMPTY_BODY
    kind = str(code_type or "").strip().upper()
    if kind in _REGION_CODE_TYPES:
        return region_names().get(text.upper(), text)
    if kind == COUNTRY_CODE_TYPE:
        return country_names().get(text.upper(), text)
    if kind == AGENCY_CODE_TYPE and agency_lookup is not None:
        name = str(agency_lookup(text) or "").strip()
        return name or text
    return text


class _CodesetRequestHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "TongGuanWenDanCodesetLocal/1.0"

    def do_GET(self):  # noqa: N802 - BaseHTTPRequestHandler naming
        name = self._lookup_name()
        if name is None:
            self._reply(404, "not found")
            return
        self._reply(200, name)

    def do_HEAD(self):  # noqa: N802 - BaseHTTPRequestHandler naming
        name = self._lookup_name()
        self._reply_without_body(404 if name is None else 200)

    def do_POST(self):  # noqa: N802 - BaseHTTPRequestHandler naming
        # Only the one lookup route is served, and only with GET.
        self._reply(404, "not found")

    do_PUT = do_PATCH = do_DELETE = do_POST

    def _lookup_name(self) -> str | None:
        """The resolved name, or None when the request is not for the code-set route."""
        target = urllib.parse.urlsplit(self.path)
        if target.path != CODESET_PATH:
            return None
        query = urllib.parse.parse_qs(restore_request_text(target.query), keep_blank_values=True)
        code_type = (query.get("codeType") or [""])[0]
        code = (query.get("code") or [""])[0]
        return self.server.resolve(code_type, code)

    def _reply(self, status: int, body: str) -> None:
        payload = body.encode("utf-8")
        self._write_headers(status, str(len(payload)))
        if payload:
            self.wfile.write(payload)

    def _reply_without_body(self, status: int) -> None:
        self._write_headers(status, "0")

    def _write_headers(self, status: int, content_length: str) -> None:
        # The renderer's HTTP client abandons idle keep-alive sockets, which a waiting
        # server thread can only report as a reset; one response per connection stays quiet.
        self.close_connection = True
        self.send_response(status)
        self.send_header("Content-Type", "text/plain;charset=UTF-8")
        self.send_header("Content-Length", content_length)
        self.send_header("Connection", "close")
        self.end_headers()

    def log_message(self, format, *args):  # noqa: A002 - BaseHTTPRequestHandler signature
        _LOGGER.debug("本机码表服务 %s - %s", self.address_string(), format % args)


class _LocalCodesetHttpServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, handler, *, resolve: Callable[[str, str], str]) -> None:
        self.resolve = resolve
        super().__init__(address, handler)


def _answers_self_check(port: int) -> bool:
    """Round-trip one known lookup through the freshly started server."""
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=SELF_CHECK_TIMEOUT_SECONDS)
    try:
        connection.request(
            "GET", f"{CODESET_PATH}?codeType={COUNTRY_CODE_TYPE}&code={SELF_CHECK_COUNTRY_CODE}",
        )
        response = connection.getresponse()
        body = response.read(_SELF_CHECK_BODY_LIMIT)
        return int(response.status) == 200 and bool(body.strip())
    except (OSError, http.client.HTTPException) as exc:
        _LOGGER.warning("本机码表服务自检请求失败：%s", exc)
        return False
    finally:
        connection.close()


class LocalCodesetServer:
    """Loopback stand-in for the official client's code-set route; loopback only, one port."""

    def __init__(self, *, agency_lookup: Callable[[str], str] | None = None) -> None:
        self._agency_lookup = agency_lookup
        self._lock = threading.Lock()
        self._server: _LocalCodesetHttpServer | None = None
        self._thread: threading.Thread | None = None
        self._base_url = ""

    @property
    def base_url(self) -> str:
        """The renderer-facing address, empty until the server is listening."""
        return self._base_url

    def start(self) -> str:
        """Bind 127.0.0.1 on an ephemeral port and serve; repeat calls return the same address."""
        with self._lock:
            if self._server is not None:
                return self._base_url
            try:
                server = _LocalCodesetHttpServer(
                    ("127.0.0.1", 0), _CodesetRequestHandler, resolve=self._resolve,
                )
            except OSError as exc:
                _LOGGER.warning("本机码表服务启动失败：%s", exc)
                return ""
            host, port = server.server_address[0], server.server_address[1]
            thread = threading.Thread(
                target=server.serve_forever, name="codeset-local-server", daemon=True,
            )
            thread.start()
            if not _answers_self_check(port):
                # A listening socket that cannot answer is worse than none: the renderer
                # would wait on every lookup and the preview page would claim names exist.
                _LOGGER.warning("本机码表服务自检失败，按不可用处理。")
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)
                return ""
            self._server = server
            self._thread = thread
            self._base_url = f"http://{host}:{port}{CODESET_PATH}"
            _LOGGER.info("本机码表服务已启动：%s", self._base_url)
            return self._base_url

    def stop(self) -> None:
        """Stop serving and release the port; safe to call when never started or twice."""
        with self._lock:
            server, thread = self._server, self._thread
            self._server = None
            self._thread = None
            self._base_url = ""
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2)

    def _resolve(self, code_type: str, code: str) -> str:
        return resolve_codeset_name(code_type, code, agency_lookup=self._agency_lookup)


_SERVER_LOCK = threading.Lock()
_SERVER: LocalCodesetServer | None = None


def get_local_codeset_server() -> LocalCodesetServer:
    """The one process-wide instance; the renderer may only ever point at one address."""
    global _SERVER
    with _SERVER_LOCK:
        if _SERVER is None:
            _SERVER = LocalCodesetServer()
        return _SERVER


def start_local_codeset_server() -> str:
    """Start the shared server and return its address, or an empty string when it cannot start."""
    return get_local_codeset_server().start()


def stop_local_codeset_server() -> None:
    with _SERVER_LOCK:
        server = _SERVER
    if server is not None:
        server.stop()


atexit.register(stop_local_codeset_server)


__all__ = [
    "AGENCY_CODE_TYPE",
    "CITY_CODE_TYPE",
    "CODESET_PATH",
    "COUNTRY_RESOURCE_FILE",
    "COUNTRY_CODE_TYPE",
    "EMPTY_BODY",
    "LocalCodesetServer",
    "MUNICIPALITY_DISTRICT_NAME",
    "PROVINCE_CODE_TYPE",
    "country_names",
    "get_local_codeset_server",
    "region_names",
    "resolve_codeset_name",
    "restore_request_text",
    "start_local_codeset_server",
    "stop_local_codeset_server",
]
