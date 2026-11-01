from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

from core.official_docs.image_to_pdf import image_bytes_to_pdf_bytes


IMAGE_SUFFIXES = frozenset({".bmp", ".gif", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"})
_PDF_MAGIC = b"%PDF-"


def looks_like_pdf(data: bytes) -> bool:
    """Detect the PDF header; a bare header on its own is not a PDF."""
    payload = bytes(data or b"")
    return len(payload) > len(_PDF_MAGIC) and payload.lstrip().startswith(_PDF_MAGIC)


def looks_like_image(data: bytes) -> bool:
    """Let PIL identify the format from the header only; pixel data is never decoded here."""
    payload = bytes(data or b"")
    if not payload:
        return False
    try:
        with Image.open(io.BytesIO(payload)) as image:
            return bool(image.format)
    except Exception:
        # PIL reports unknown or truncated content through several exception types.
        return False


def unsupported_attachment_message(name: str) -> str:
    return f"附件无法并入预览：{name} 不是 PDF 也不是可识别的图片。"


def attachment_to_pdf_bytes(path: str | Path) -> bytes:
    """Return one case-package attachment as PDF: PDFs pass through, images are converted."""
    source = Path(path)
    try:
        payload = source.read_bytes()
    except OSError as exc:
        raise ValueError(f"无法读取案卷附件：{source.name}（{exc}）") from exc
    if looks_like_pdf(payload):
        return payload
    try:
        return image_bytes_to_pdf_bytes(payload)
    except Exception as exc:
        raise ValueError(unsupported_attachment_message(source.name)) from exc


__all__ = [
    "IMAGE_SUFFIXES",
    "attachment_to_pdf_bytes",
    "looks_like_image",
    "looks_like_pdf",
    "unsupported_attachment_message",
]
