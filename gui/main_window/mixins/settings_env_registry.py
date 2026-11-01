from core.word_engine_impl.registry_probe import (
    discover_ms_word_versions_from_registry,
    parse_localserver_exe_path,
    probe_word_com_registration,
    progid_localserver32,
    reg_read_default,
)


def probe_word_env_from_registry() -> dict:
    probed = probe_word_com_registration()
    hijacked = bool(probed.get("hijacked", False))
    fallback_possible = bool(probed.get("fallback_possible", False))
    word_ok = bool(probed.get("word_ok", False))

    word_error = ""
    if hijacked:
        if fallback_possible:
            word_error = "WPS 接管了 Word 连接，但本机仍有可用的 Microsoft Word。"
        else:
            word_error = "检测到 Word.Application 可能被 WPS 接管，且未发现可用的 Microsoft Word。"
    elif not word_ok:
        word_error = "未检测到可用的 Microsoft Word，请确认已安装完整 Office，并尝试手动打开 Word。"

    return {
        "word_ok": bool(word_ok),
        "hijacked": bool(hijacked),
        "word_version": probed.get("word_version"),
        "word_error": str(word_error or ""),
        "localserver32": str(probed.get("localserver32", "") or ""),
        "fallback_possible": bool(fallback_possible),
        "block_reason": str(probed.get("block_reason", "") or ""),
        "default_com_target": str(probed.get("default_com_target", "") or ""),
        "default_com_path_exists": bool(probed.get("default_com_path_exists", False)),
    }


__all__ = [
    "discover_ms_word_versions_from_registry",
    "parse_localserver_exe_path",
    "probe_word_env_from_registry",
    "progid_localserver32",
    "reg_read_default",
]
