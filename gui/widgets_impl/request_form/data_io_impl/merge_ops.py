def _merge_data_mgmt_draft_if_any(self, info):
    if not isinstance(info, dict):
        return info

    cache = None
    key = ""
    try:
        cache = getattr(self, "_request_form_cache", None)
    except Exception:
        cache = None
    try:
        key = str(getattr(self, "_request_form_cache_key", "") or "")
    except Exception:
        key = ""

    if not (isinstance(cache, dict) and key):
        return info

    entry = cache.get(key)
    if not isinstance(entry, dict):
        return info

    draft = entry.get("data_mgmt_draft")
    if not isinstance(draft, dict):
        return info

    try:
        merged = dict(info)
        if "group_name" in draft:
            merged["group_name"] = draft.get("group_name")
        if "applicants" in draft:
            merged["applicants"] = draft.get("applicants")
        if "inventors" in draft:
            merged["inventors"] = draft.get("inventors")
        if "contact" in draft:
            merged["contact"] = draft.get("contact")
        return merged
    except Exception:
        return info
