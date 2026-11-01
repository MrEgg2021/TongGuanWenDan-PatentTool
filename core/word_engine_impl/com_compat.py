from __future__ import annotations


def add_hidden_document(app, *, logger=None):
    documents = getattr(app, "Documents", None)
    if documents is None:
        raise RuntimeError("Word Documents collection is not available")
    try:
        return documents.Add(Visible=False)
    except Exception as first_exc:
        if logger is not None:
            try:
                logger.warning("[WORD_COM_COMPAT] Documents.Add(Visible=False) failed, retrying without Visible: %s", first_exc)
            except Exception:
                pass
        return documents.Add()
