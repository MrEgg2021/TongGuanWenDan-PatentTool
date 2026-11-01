from __future__ import annotations

import http.client
import ipaddress
import logging
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import yaml

from .codeset_local import start_local_codeset_server

_LOGGER = logging.getLogger(__name__)

# The official xml2pdf library resolves code-set values (CN -> 中国) over HTTP and
# ships an unreachable intranet default address, which costs one ~10 s timeout per
# code-set field.  Only the two scalars below are read from the installed client;
# its Spring configuration is never loaded and its service is never started here.
APPLICATION_YML_RELATIVE_PATH = Path("plugins/as/cpc-main-as/conf/application.yml")
LOOPBACK_BASE_PATH_TEMPLATE = "http://127.0.0.1:{port}/public-base/codeset/findByCode"
# Nothing listens on port 1, so the library's code-set lookup fails immediately
# instead of waiting for its own timeout on every field.
UNREACHABLE_BASE_PATH = "http://127.0.0.1:1/base/codeset/findByCode"
PROBE_TIMEOUT_SECONDS = 1.0
# Bounds both connect and read for the renderer's code-set lookups.  The address itself
# decides most of the cost: the library's intranet default spends ~10 s per field, while
# a local address that nobody answers costs only a couple of seconds.
CONNECT_TIMEOUT_MILLIS = 1500
READ_TIMEOUT_MILLIS = 5000
PROBE_CODE_TYPE = "GUOBIE"
PROBE_CODE = "CN"
_PROBE_BODY_LIMIT = 512
NOT_DETECTED_DETAIL = "尚未检测官方客户端本地代码集服务。"
CODESET_UNAVAILABLE_NOTICE = (
    "未检测到官方客户端的本地代码集服务，请求书类文书中的代码字段会显示为代码值（如 CN、330000）；"
    "打开官方客户端后重试即可显示中文名称。"
)
LOCAL_CODESET_NOTICE = (
    "当前使用本机码表：国别、省市字段已翻译为中文名称，代理机构代码等官方登记字段仍显示原值；"
    "打开官方客户端后重新生成可获得最完整的结果。"
)
LOCAL_CODESET_DETAIL_PREFIX = "未检测到官方客户端本地代码集服务，已启用自带本机码表"
_NO_LOCAL_CODESET_DETAIL_PREFIX = "自带本机码表不可用"

# Loopback traffic must never be diverted through a configured system proxy.
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


@dataclass(frozen=True)
class CodesetEndpoint:
    """The two official-client scalars this module is allowed to read."""

    base_path: str = ""
    server_port: int | None = None


@dataclass(frozen=True)
class CodesetState:
    """One detection round.  ``base`` is the effective address handed to the renderer JVM.

    ``local_table`` marks the fallback to the name tables shipped with this application,
    which cover country and province/city fields but not official registry fields.
    """

    available: bool
    base: str
    detail: str
    local_table: bool = False


def read_codeset_endpoint(client_root: str | Path) -> CodesetEndpoint | None:
    """Read only ``server.port`` and ``xml2pdf-plugin.codeset.base-path``; missing means None."""
    config = Path(client_root) / APPLICATION_YML_RELATIVE_PATH
    try:
        document = yaml.safe_load(config.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        _LOGGER.info("Official client code-set configuration is unreadable: %s (%s)", config, exc)
        return None
    if not isinstance(document, dict):
        return None
    server = document.get("server")
    plugin = document.get("xml2pdf-plugin")
    codeset = plugin.get("codeset") if isinstance(plugin, dict) else None
    base_path = codeset.get("base-path") if isinstance(codeset, dict) else None
    port = server.get("port") if isinstance(server, dict) else None
    return CodesetEndpoint(
        base_path=str(base_path).strip() if isinstance(base_path, str) else "",
        server_port=_normalize_port(port),
    )


def resolve_codeset_endpoint(client_root: str | Path) -> str | None:
    """Return the local code-set address, or None when the client configuration cannot supply one."""
    endpoint = read_codeset_endpoint(client_root)
    if endpoint is None:
        return None
    if endpoint.base_path and _is_loopback_url(endpoint.base_path):
        return endpoint.base_path
    if endpoint.server_port is not None:
        return LOOPBACK_BASE_PATH_TEMPLATE.format(port=endpoint.server_port)
    return None


def probe_url(endpoint: str) -> str:
    query = urllib.parse.urlencode({"codeType": PROBE_CODE_TYPE, "code": PROBE_CODE})
    separator = "&" if "?" in endpoint else "?"
    return f"{endpoint}{separator}{query}"


def probe_endpoint(endpoint: str, *, timeout: float = PROBE_TIMEOUT_SECONDS) -> bool:
    """A code-set service counts as ready only when it answers HTTP < 400 with a non-empty body."""
    url = probe_url(endpoint)
    try:
        status, body = _fetch_probe(url, timeout)
    except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError) as exc:
        _LOGGER.info("Official local code-set service did not answer: %s (%s)", url, exc)
        return False
    return status < 400 and bool(body.strip())


def detect_codeset_state(
    client_root: str | Path,
    *,
    probe=probe_endpoint,
    timeout: float = PROBE_TIMEOUT_SECONDS,
    start_local=start_local_codeset_server,
) -> CodesetState:
    """Resolve the code-set service, always returning a usable renderer address.

    The official client's own local service wins because it holds the complete registry
    data.  Without it the shipped name tables take over; only when both are unavailable
    does the renderer get an address whose lookups fail immediately.
    """
    endpoint = resolve_codeset_endpoint(client_root)
    if endpoint is not None and probe(endpoint, timeout=timeout):
        return CodesetState(True, endpoint, f"已连接官方客户端本地代码集服务：{endpoint}")
    local_base = str(start_local() or "").strip()
    if local_base:
        return CodesetState(True, local_base, f"{LOCAL_CODESET_DETAIL_PREFIX}：{local_base}", local_table=True)
    if endpoint is None:
        return CodesetState(False, UNREACHABLE_BASE_PATH, f"未读取到官方客户端代码集服务地址，{_NO_LOCAL_CODESET_DETAIL_PREFIX}，代码字段将显示为代码值。")
    return CodesetState(False, UNREACHABLE_BASE_PATH, f"官方客户端本地代码集服务未就绪，{_NO_LOCAL_CODESET_DETAIL_PREFIX}：{endpoint}")


def effective_base(codeset: CodesetState | str | None = None) -> str:
    if isinstance(codeset, CodesetState):
        return codeset.base if codeset.available else UNREACHABLE_BASE_PATH
    base = str(codeset or "").strip()
    return base or UNREACHABLE_BASE_PATH


def java_options(codeset: CodesetState | str | None = None) -> tuple[str, ...]:
    """Renderer JVM flags: the code-set address plus bounded network timeouts for both cases."""
    return (
        f"-Decloud.service.base={effective_base(codeset)}",
        f"-Dsun.net.client.defaultConnectTimeout={CONNECT_TIMEOUT_MILLIS}",
        f"-Dsun.net.client.defaultReadTimeout={READ_TIMEOUT_MILLIS}",
    )


def _normalize_port(value: object) -> int | None:
    try:
        port = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return port if 0 < port < 65536 else None


def _is_loopback_url(url: str) -> bool:
    try:
        hostname = urllib.parse.urlsplit(url).hostname
    except ValueError:
        return False
    if not hostname:
        return False
    if hostname.casefold() == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def _fetch_probe(url: str, timeout: float) -> tuple[int, str]:
    request = urllib.request.Request(url, method="GET", headers={"Accept": "*/*"})
    with _OPENER.open(request, timeout=timeout) as response:
        status = getattr(response, "status", None)
        if status is None:
            status = response.getcode()
        body = response.read(_PROBE_BODY_LIMIT)
    if isinstance(body, bytes):
        return int(status), body.decode("utf-8", errors="replace")
    return int(status), str(body)


__all__ = [
    "APPLICATION_YML_RELATIVE_PATH",
    "CODESET_UNAVAILABLE_NOTICE",
    "CodesetEndpoint",
    "CodesetState",
    "LOCAL_CODESET_NOTICE",
    "NOT_DETECTED_DETAIL",
    "UNREACHABLE_BASE_PATH",
    "detect_codeset_state",
    "effective_base",
    "java_options",
    "probe_endpoint",
    "probe_url",
    "read_codeset_endpoint",
    "resolve_codeset_endpoint",
]
