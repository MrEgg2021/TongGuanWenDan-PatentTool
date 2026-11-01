from __future__ import annotations

import fitz


def merge_pdf_bytes(sources: list[bytes]) -> bytes:
    if not sources:
        raise ValueError("no PDF sources to merge")

    out_doc = fitz.open()
    try:
        for b in sources:
            if not b:
                continue
            src = fitz.open(stream=b, filetype="pdf")
            try:
                out_doc.insert_pdf(src)
            finally:
                src.close()
        data = out_doc.tobytes()
        if not data:
            raise RuntimeError("merged PDF is empty")
        return data
    finally:
        out_doc.close()


__all__ = ["merge_pdf_bytes"]

