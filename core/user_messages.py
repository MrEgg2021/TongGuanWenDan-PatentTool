from __future__ import annotations

import re



_TECHNICAL_ERROR = re.compile(
    r"\[(?:Errno|WinError)\s+\d+\]|\b\w*(?:Error|Exception)\b(?=\s*[:(])|"
    r"Traceback|(?:HTTPS?|HTTP)ConnectionPool|Max retries exceeded|"
    r"java\.lang\.|groovy\.|pywintypes\.|\(-?\d{8,},"
)
_CHINESE = re.compile(r"[\u4e00-\u9fff]")


def user_error_text(message: str) -> str:
    """Translate technical error lines into actionable user text."""
    translated = []
    for line in message.splitlines():
        lowered = line.lower()
        technical = _TECHNICAL_ERROR.search(line)
        if not technical and (_CHINESE.search(line) or not re.search(r"[A-Za-z]", line)):
            translated.append(line)
            continue
        if not technical and (
            re.match(r"\s*(?:[A-Za-z]:[\\/]|[/\\]{2}|https?://)", line)
            or re.fullmatch(r"[^\r\n<>:*?|]+\.[A-Za-z0-9]{1,8}", line.strip())
            or "@" in line
        ):
            translated.append(line)
            continue

        if any(word in lowered for word in ("permission denied", "access is denied", "拒绝访问")):
            reason = "无法读写文件，请检查目录权限，以及文件是否被其他程序占用。"
        elif any(word in lowered for word in ("no such file", "cannot find", "找不到指定", "filenotfounderror")):
            reason = "找不到所需文件，请确认文件仍存在后重新选择。"
        elif any(word in lowered for word in ("used by another process", "being used", "另一个程序", "winerror 32")):
            reason = "文件正被其他程序占用，请关闭占用该文件的程序后重试。"
        elif any(word in lowered for word in ("no space left", "disk full", "磁盘空间", "winerror 112")):
            reason = "磁盘可用空间不足，请释放空间后重试。"
        elif any(word in lowered for word in ("outofmemory", "memoryerror", "heap space", "reserve enough space")):
            reason = "可用内存不足，请减少本次处理的文件数量后重试。"
        elif any(word in lowered for word in ("timeout", "timed out", "超时")):
            reason = "等待操作完成超时，请确认相关程序或服务可用后重试。"
        elif any(word in lowered for word in ("connection", "max retries", "连接")):
            reason = "无法连接所需服务，请确认服务已启动并检查连接设置。"
        elif any(word in lowered for word in ("modulenotfound", "importerror", "dll load failed")):
            reason = "程序所需组件无法加载，请重新下载完整程序后重试。"
        else:
            reason = "操作未完成，请重试；如仍失败，请查看程序日志排查。"

        prefix = line[:technical.start()].rstrip(" ：:（(\t") if technical else ""
        rendered = f"{prefix}：{reason}" if _CHINESE.search(prefix) else reason
        if not translated or translated[-1] != rendered:
            translated.append(rendered)

    text = "\n".join(translated)
    return text
