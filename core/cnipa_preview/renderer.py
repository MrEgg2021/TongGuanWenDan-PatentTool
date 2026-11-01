from __future__ import annotations

import contextlib
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

import requests

from .attachments import attachment_to_pdf_bytes, looks_like_pdf
from .models import PreviewDocument, PreviewRenderResult
from .package import prepare_preview_package
from .form_renderer import FormRenderCancelled, render_opinion_pdf

if TYPE_CHECKING:
    from .runtime import RuntimeLayout


class PreviewRendererError(RuntimeError):
    pass


class RendererService(Protocol):
    def ensure_runtime(self) -> RuntimeLayout: ...

    def ensure_running(
        self,
        *,
        startup_wait_callback: Callable[[float], None] | None = None,
        cancelled: CancellationCheck | None = None,
    ) -> str: ...


ProgressCallback = Callable[[int, int, str], None]
CancellationCheck = Callable[[], bool]


def _is_pdf(content: bytes) -> bool:
    return looks_like_pdf(content)


def _short_response_error(response: requests.Response) -> str:
    try:
        body = str(response.text or "").strip()
    except Exception:
        body = ""
    if len(body) > 800:
        body = body[:800] + "…"
    if body:
        return f"HTTP {response.status_code}: {body}"
    return f"HTTP {response.status_code}"


class CnipaXmlRenderer:
    """Calls the official XML-to-PDF endpoint through an application-owned service."""

    def __init__(
        self,
        service: RendererService,
        *,
        request_get: Callable[..., requests.Response] = requests.get,
        request_timeout: tuple[float, float] = (5.0, 120.0),
    ) -> None:
        self._service = service
        self._request_get = request_get
        self._request_timeout = request_timeout

    def render_case(
        self,
        zip_path: str,
        *,
        documents: tuple[PreviewDocument, ...] | None = None,
        selected_document_ids: tuple[str, ...] | None = None,
        progress: ProgressCallback | None = None,
        cancelled: CancellationCheck | None = None,
        startup_wait: Callable[[float], None] | None = None,
    ) -> PreviewRenderResult:
        with prepare_preview_package(zip_path) as package:
            package_documents = {document.id: document for document in package.documents}
            if documents is None:
                ordered_documents = package.documents
            else:
                ordered_documents = tuple(
                    package_documents[document.id]
                    for document in documents
                    if document.id in package_documents
                )
            if selected_document_ids is None:
                selected_ids = {document.id for document in ordered_documents}
            else:
                selected_ids = set(selected_document_ids)
            pdf_by_document_id: dict[str, bytes] = {}
            errors = {
                document_id: message
                for document_id, message in package.errors_by_document_id.items()
                if document_id in {document.id for document in ordered_documents}
            }
            passthrough_documents = [
                document
                for document in ordered_documents
                if document.id in selected_ids and document.id in package.pdf_paths_by_document_id
            ]
            passthrough_document_ids = frozenset(document.id for document in passthrough_documents)
            for document in passthrough_documents:
                try:
                    pdf_by_document_id[document.id] = attachment_to_pdf_bytes(
                        package.pdf_paths_by_document_id[document.id]
                    )
                except ValueError as exc:
                    errors[document.id] = str(exc)
            renderable = [
                document
                for document in ordered_documents
                if document.id in selected_ids and document.id in package.xml_paths_by_document_id
            ]

            if not renderable:
                return PreviewRenderResult(
                    documents=ordered_documents,
                    pdf_by_document_id=pdf_by_document_id,
                    passthrough_document_ids=passthrough_document_ids,
                    errors_by_document_id=errors,
                )

            with self._service_session(startup_wait=startup_wait, cancelled=cancelled) as base_url:
                return self._render_documents(
                    base_url=base_url,
                    ordered_documents=ordered_documents,
                    renderable=renderable,
                    xml_paths=package.xml_paths_by_document_id,
                    pdf_by_document_id=pdf_by_document_id,
                    passthrough_document_ids=passthrough_document_ids,
                    errors=errors,
                    progress=progress,
                    cancelled=cancelled,
                )

    @contextlib.contextmanager
    def _service_session(
        self,
        *,
        startup_wait: Callable[[float], None] | None,
        cancelled: CancellationCheck | None,
    ):
        library_session = getattr(self._service, "library_session", None)
        if callable(library_session):
            with library_session(startup_wait_callback=startup_wait, cancelled=cancelled):
                yield ""
            return
        render_session = getattr(self._service, "render_session", None)
        try:
            if callable(render_session):
                session = render_session(startup_wait_callback=startup_wait, cancelled=cancelled)
            else:
                try:
                    base_url = self._service.ensure_running(startup_wait_callback=startup_wait, cancelled=cancelled)
                except TypeError:
                    base_url = self._service.ensure_running(startup_wait_callback=startup_wait)
                session = contextlib.nullcontext(base_url)
            with session as base_url:
                normalized = str(base_url).rstrip("/")
                if not normalized.startswith("http://127.0.0.1:"):
                    raise PreviewRendererError("全量预览官方渲染器未运行在受控的本机回环地址。")
                yield normalized
        except PreviewRendererError:
            raise
        except Exception as exc:
            raise PreviewRendererError(f"无法启动全量预览官方渲染器：{exc}") from exc

    def _render_documents(
        self,
        *,
        base_url: str,
        ordered_documents: tuple[PreviewDocument, ...],
        renderable: list[PreviewDocument],
        xml_paths: dict[str, Path],
        passthrough_document_ids: frozenset[str],
        pdf_by_document_id: dict[str, bytes],
        errors: dict[str, str],
        progress: ProgressCallback | None,
        cancelled: CancellationCheck | None,
    ) -> PreviewRenderResult:
        session_id = f"preview-{uuid.uuid4().hex}"
        total = len(renderable)
        for completed, document in enumerate(renderable, start=1):
            if cancelled and cancelled():
                return PreviewRenderResult(
                    documents=ordered_documents,
                    pdf_by_document_id=pdf_by_document_id,
                    passthrough_document_ids=passthrough_document_ids,
                    errors_by_document_id=errors,
                    cancelled=True,
                )
            if progress:
                progress(completed - 1, total, document.display_name)

            try:
                library_render = getattr(self._service, "render_document", None)
                if callable(library_render):
                    content = library_render(xml_paths[document.id], document.code, cancelled=cancelled)
                elif document.code == "100012":
                    content = render_opinion_pdf(
                        self._service.ensure_runtime(), xml_paths[document.id], cancelled=cancelled,
                    )
                else:
                    content = self._render_document(
                        base_url=base_url,
                        xml_path=xml_paths[document.id],
                        document_code=document.code,
                        submission_id=session_id,
                    )
                pdf_by_document_id[document.id] = content
            except FormRenderCancelled:
                return PreviewRenderResult(
                    documents=ordered_documents, pdf_by_document_id=pdf_by_document_id,
                    passthrough_document_ids=passthrough_document_ids,
                    errors_by_document_id=errors, cancelled=True,
                )
            except Exception as exc:
                errors[document.id] = str(exc)

        if progress:
            progress(total, total, "")
        return PreviewRenderResult(
            documents=ordered_documents,
            pdf_by_document_id=pdf_by_document_id,
            passthrough_document_ids=passthrough_document_ids,
            errors_by_document_id=errors,
        )

    def _render_document(
        self,
        *,
        base_url: str,
        xml_path: Path,
        document_code: str,
        submission_id: str,
    ) -> bytes:
        try:
            response = self._request_get(
                base_url + "/preview/xml2pdf",
                params={
                    "filepath": str(xml_path),
                    "wenjianbs": submission_id,
                    "wenjianlx": document_code,
                },
                timeout=self._request_timeout,
                proxies={"http": None, "https": None},
            )
        except requests.RequestException as exc:
            raise PreviewRendererError(f"调用官方渲染器失败：{exc}") from exc
        except Exception as exc:
            raise PreviewRendererError(f"调用官方渲染器失败：{exc}") from exc

        if int(response.status_code) >= 400:
            raise PreviewRendererError(_short_response_error(response))
        content = bytes(response.content or b"")
        if not _is_pdf(content):
            raise PreviewRendererError(f"官方渲染器未返回有效 PDF：{_short_response_error(response)}")
        return content


__all__ = ["CnipaXmlRenderer", "PreviewRendererError", "RendererService"]
