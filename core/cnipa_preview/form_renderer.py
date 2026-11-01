from __future__ import annotations

import os
import subprocess
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .runtime import RuntimeLayout


class FormRenderCancelled(RuntimeError):
    pass


_SCRIPT = """import com.gwssi.commons.xml2pdf.factories.ModelFactory
import com.gwssi.commons.xml.parse.callback.SimpleCallback
ModelFactory.builder(args[0]).saveToPDF(args[1], args[2] ?: null, args[3], new SimpleCallback[0])
"""


def _classpath(layout: RuntimeLayout) -> str:
    """Preserve the official library order; wildcard JARs load conflicting POI versions."""
    entries = []
    cwd = layout.wrapper_config.parent
    for line in layout.wrapper_config.read_text(encoding="utf-8").splitlines():
        if not line.startswith("wrapper.java.classpath."):
            continue
        key, value = line.split("=", 1)
        value = value.replace("%APP_HOME%", os.path.relpath(layout.app_root, cwd))
        value = value.replace("%COMMONS_HOME%", os.path.relpath(layout.client_root / "commons", cwd))
        if "%" in value:
            raise RuntimeError("官方运行时 classpath 含未识别变量，请检查导入的运行时。")
        entries.append((int(key.rsplit(".", 1)[1]), value))
    if not entries:
        raise RuntimeError("官方运行时缺少渲染库 classpath 配置，请重新导入。")
    return os.pathsep.join(value for _, value in sorted(entries))


def render_opinion_pdf(
    layout: RuntimeLayout,
    xml_path: Path,
    *,
    cancelled: Callable[[], bool] | None = None,
    timeout_seconds: float = 120.0,
) -> bytes:
    """Render the supplied form and continuation through the private official library."""
    section = xml_path.with_name("section_1.xml")
    if any(p.name != "section_1.xml" for p in xml_path.parent.glob("section_*.xml")):
        raise RuntimeError("意见陈述书包含多个 section 附页文件，当前尚未验证此结构，已停止生成以免遗漏内容。")
    java = layout.client_root / "commons/jre/win32/jre8/bin/java.exe"
    classpath = _classpath(layout)
    with tempfile.TemporaryDirectory(prefix="cnipa_form_") as tmp:
        workspace = Path(tmp)
        script = workspace / "render.groovy"
        output = workspace / "output.pdf"
        script.write_text(_SCRIPT, encoding="utf-8")
        command = [
            str(java), f"-Dcpc.home={layout.app_root}", "-Dfile.encoding=UTF-8",
            f"-Djava.io.tmpdir={workspace}", "-cp", classpath, "groovy.ui.GroovyMain",
            str(script), "100012", str(xml_path), str(section) if section.is_file() else "", str(output),
        ]
        if cancelled and cancelled():
            raise FormRenderCancelled("已取消意见陈述书预览。")
        with tempfile.TemporaryFile() as log:
            process = subprocess.Popen(
                command, cwd=layout.wrapper_config.parent, stdout=log, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            deadline = time.monotonic() + timeout_seconds
            try:
                while True:
                    if cancelled and cancelled():
                        raise FormRenderCancelled("已取消意见陈述书预览。")
                    if time.monotonic() >= deadline:
                        raise TimeoutError("意见陈述书渲染超时，请检查案卷内容后重试。")
                    try:
                        process.wait(timeout=0.2)
                        break
                    except subprocess.TimeoutExpired:
                        continue
            finally:
                if process.poll() is None:
                    process.kill()
                process.wait()
            if cancelled and cancelled():
                raise FormRenderCancelled("已取消意见陈述书预览。")
            if process.returncode != 0 or not output.is_file():
                log.seek(0, os.SEEK_END)
                log.seek(max(0, log.tell() - 2000))
                detail = log.read().decode("utf-8", errors="replace").strip()
                raise RuntimeError(f"官方意见陈述书渲染失败（退出码 {process.returncode}）：{detail}")
        content = output.read_bytes()
        if not content.startswith(b"%PDF-"):
            raise RuntimeError("官方意见陈述书渲染器未输出有效 PDF。")
        return content
