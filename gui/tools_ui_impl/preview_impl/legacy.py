from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from pathlib import Path

import fitz
import requests
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel, QSpinBox, QVBoxLayout

from core.cnipa_preview.models import LegacyPreviewResult, PreviewDocument, PreviewRenderResult
from core.app_preferences import get_pdf_preview_port, set_pdf_preview_port

from .zip_utils import build_preview_zip_without_case_root


LEGACY_PREVIEW_DOCUMENTS = (
    PreviewDocument("100001", "100001", "权利要求书", "100001.xml"),
    PreviewDocument("100002", "100002", "说明书", "100002.xml"),
    PreviewDocument("100003", "100003", "说明书附图", "100003.xml"),
    PreviewDocument("100004", "100004", "说明书摘要", "100004.xml"),
)

ProgressCallback = Callable[[int, int, str], None]
CancellationCheck = Callable[[], bool]


def read_legacy_preview_port() -> int:
    port = get_pdf_preview_port()
    return int(port) if port is not None else 8080


def build_legacy_preview_base_url(port: int | None = None) -> str:
    return f"http://127.0.0.1:{int(port if port is not None else read_legacy_preview_port())}"


def ping_legacy_preview_service(base_url: str) -> bool:
    try:
        response = requests.get(
            base_url.rstrip("/") + "/",
            timeout=2,
            proxies={"http": None, "https": None},
        )
        return int(response.status_code) < 400
    except requests.RequestException:
        return False


def prompt_legacy_preview_port(parent) -> int | None:
    dialog = QDialog(parent)
    dialog.setWindowTitle("修改轻量预览服务端口")
    dialog.setModal(True)
    dialog.setMinimumWidth(430)
    layout = QVBoxLayout(dialog)
    tip = QLabel("请输入官方轻量预览服务正在监听的本机端口。默认端口为 8080。")
    tip.setWordWrap(True)
    layout.addWidget(tip)
    form = QFormLayout()
    port_input = QSpinBox(dialog)
    port_input.setRange(1, 65535)
    port_input.setValue(read_legacy_preview_port())
    form.addRow("服务端口：", port_input)
    layout.addLayout(form)
    status = QLabel("")
    layout.addWidget(status)
    buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel, parent=dialog)
    buttons.button(QDialogButtonBox.Save).setText("检测并保存")
    buttons.button(QDialogButtonBox.Cancel).setText("取消")
    layout.addWidget(buttons)

    accepted_port: list[int | None] = [None]

    def verify_and_accept() -> None:
        port = int(port_input.value())
        status.setText("正在检测服务……")
        if not ping_legacy_preview_service(build_legacy_preview_base_url(port)):
            status.setText("未检测到服务，请确认官方轻量预览插件已启动。")
            return
        set_pdf_preview_port(port)
        accepted_port[0] = port
        dialog.accept()

    buttons.accepted.connect(verify_and_accept)
    buttons.rejected.connect(dialog.reject)
    dialog.exec()
    return accepted_port[0]


def _parse_upload_response(text: str) -> str:
    value = str(text or "").strip()
    if value.lower().startswith(("http://", "https://")):
        return value
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise RuntimeError("轻量预览服务未返回有效的预览地址。") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("轻量预览服务返回格式无效。")
    code = payload.get("code")
    if code not in (None, 0, 200, "0", "200"):
        message = str(payload.get("message") or payload.get("msg") or "未知错误")
        raise RuntimeError(f"轻量预览服务返回错误：{message}（code={code}）")
    candidates: list[object] = [payload.get("url"), payload.get("preview_url")]
    data = payload.get("data")
    if isinstance(data, str):
        candidates.append(data)
    elif isinstance(data, dict):
        candidates.extend((data.get("url"), data.get("preview_url")))
    for candidate in candidates:
        url = str(candidate or "").strip()
        if url.lower().startswith(("http://", "https://")):
            return url
    raise RuntimeError("轻量预览服务未返回有效的预览地址。")


def _preview_token(preview_url: str) -> tuple[str, str]:
    matched = re.match(r"^(https?://[^/]+)/view/([^/?#]+)", preview_url.strip())
    if matched is None:
        raise RuntimeError("轻量预览地址格式无效。")
    return matched.group(1), matched.group(2)


def _is_pdf(content: bytes) -> bool:
    if not content.lstrip().startswith(b"%PDF-"):
        return False
    document = fitz.open(stream=content, filetype="pdf")
    try:
        return document.page_count > 0
    finally:
        document.close()


def render_legacy_preview(
    zip_path: str,
    base_url: str,
    *,
    progress: ProgressCallback | None = None,
    cancelled: CancellationCheck | None = None,
) -> LegacyPreviewResult:
    def check_cancelled() -> None:
        if cancelled is not None and cancelled():
            raise InterruptedError("轻量预览已取消。")

    temporary_paths: list[str] = []
    preview_zip = build_preview_zip_without_case_root(zip_path, temporary_paths)
    try:
        check_cancelled()
        if progress is not None:
            progress(0, 5, "正在上传案卷包")
        with open(preview_zip, "rb") as source:
            response = requests.post(
                base_url.rstrip("/") + "/api/upload-zip/sync",
                files={"file": (os.path.basename(preview_zip), source, "application/zip")},
                timeout=(5, 240),
                proxies={"http": None, "https": None},
            )
        response.raise_for_status()
        preview_url = _parse_upload_response(response.text)
        origin, token = _preview_token(preview_url)
        session = requests.Session()
        session.proxies = {"http": None, "https": None}
        session.cookies.update(response.cookies)
        headers = {"Referer": preview_url, "User-Agent": "TongGuanWenDan/legacy-preview"}
        session.get(preview_url, timeout=(5, 15), headers=headers)
        pdf_map: dict[str, bytes] = {}
        errors: dict[str, str] = {}
        for index, document in enumerate(LEGACY_PREVIEW_DOCUMENTS, start=1):
            check_cancelled()
            if progress is not None:
                progress(index, 5, document.display_name)
            viewer_url = origin.rstrip("/") + f"/pdf/web/viewer.html?file=/view-pdf/{token}/{document.code}.pdf"
            pdf_url = origin.rstrip("/") + f"/view-pdf/{token}/{document.code}.pdf"
            last_error = ""
            for attempt in range(3):
                try:
                    session.get(viewer_url, timeout=(5, 15), headers=headers)
                    pdf_response = session.get(
                        pdf_url,
                        timeout=(5, 30),
                        headers={"Referer": viewer_url, "User-Agent": headers["User-Agent"]},
                    )
                    pdf_response.raise_for_status()
                    content = bytes(pdf_response.content or b"")
                    if not _is_pdf(content):
                        raise RuntimeError("服务返回的内容不是有效 PDF。")
                    pdf_map[document.id] = content
                    last_error = ""
                    break
                except (requests.RequestException, RuntimeError, ValueError) as exc:
                    last_error = str(exc)
                    if attempt < 2:
                        check_cancelled()
            if last_error:
                errors[document.id] = last_error
        return LegacyPreviewResult(
            preview_url=preview_url,
            render_result=PreviewRenderResult(
                documents=LEGACY_PREVIEW_DOCUMENTS,
                pdf_by_document_id=pdf_map,
                errors_by_document_id=errors,
            ),
        )
    finally:
        for path in temporary_paths:
            try:
                Path(path).unlink()
            except FileNotFoundError:
                pass


__all__ = [
    "LEGACY_PREVIEW_DOCUMENTS",
    "build_legacy_preview_base_url",
    "ping_legacy_preview_service",
    "prompt_legacy_preview_port",
    "read_legacy_preview_port",
    "render_legacy_preview",
]
