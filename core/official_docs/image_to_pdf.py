from __future__ import annotations

import io

from PIL import Image, ImageSequence


def _frame_to_rgb(frame: Image.Image) -> Image.Image:
    if frame.mode in ("RGBA", "LA") or (frame.mode == "P" and "transparency" in frame.info):
        rgba = frame.convert("RGBA")
        background = Image.new("RGB", rgba.size, "white")
        background.paste(rgba, mask=rgba.split()[-1])
        return background
    if frame.mode == "RGB":
        return frame.copy()
    return frame.convert("RGB")


def image_bytes_to_pdf_bytes(image_bytes: bytes) -> bytes:
    payload = bytes(image_bytes or b"")
    if not payload:
        raise ValueError("empty image bytes")

    frames: list[Image.Image] = []
    with Image.open(io.BytesIO(payload)) as image:
        frame_count = max(1, int(getattr(image, "n_frames", 1) or 1))
        if frame_count <= 1:
            frames.append(_frame_to_rgb(image))
        else:
            for frame in ImageSequence.Iterator(image):
                frames.append(_frame_to_rgb(frame))

    if not frames:
        raise RuntimeError("failed to decode image bytes")

    out = io.BytesIO()
    head, *tail = frames
    head.save(out, format="PDF", save_all=bool(tail), append_images=tail)
    data = out.getvalue()
    if not data:
        raise RuntimeError("generated PDF is empty")
    return data


__all__ = ["image_bytes_to_pdf_bytes"]
