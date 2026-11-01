from __future__ import annotations

import contextlib
import json
import logging
import os
import queue
import re
import subprocess
import tempfile
import threading
import time
import zipfile
from collections import deque
from pathlib import Path

from core.paths_utils import get_user_data_dir

from .codeset import (
    NOT_DETECTED_DETAIL, UNREACHABLE_BASE_PATH, CodesetState, detect_codeset_state, java_options,
)
from .codeset_local import stop_local_codeset_server
from .form_renderer import FormRenderCancelled
from .installed_client import (
    InstalledClient, component_signature, detect_client, inspect_installed_client,
    java_classpath_manifest, remember_client, remembered_client_path,
)
from .models import RendererState, RendererStateInfo
from .runtime import PreviewRuntimeError


_PREFIX = "CPC_PREVIEW:"
_HEAP_RESERVATION_ERROR = "could not reserve enough space for"
_LOGGER = logging.getLogger(__name__)
_WORKER = r'''
import groovy.json.JsonOutput
import groovy.json.JsonSlurper
import com.gwssi.commons.xml2pdf.factories.ModelFactory
import com.gwssi.commons.xml.parse.callback.SimpleCallback

def reply = { data -> println('CPC_PREVIEW:' + JsonOutput.toJson(data)); System.out.flush() }
// Constructing the model alone leaves PDF classes and embedded fonts cold.
// Exercise the real PDF path only in our disposable working directory.
def warmXml = new File('warmup.xml')
def warmPdf = new File('warmup.pdf')
try {
    warmXml.setText('<cn-application-body lang="zh" country="CN"><cn-claims><claim id="c1" num="1"><claim-text>Preview warmup.</claim-text></claim></cn-claims></cn-application-body>', 'UTF-8')
    ModelFactory.builder('100001').saveToPDF(warmXml.absolutePath.replace('\\', '/'),
        null, warmPdf.absolutePath.replace('\\', '/'), new SimpleCallback[0])
    if (!warmPdf.isFile() || warmPdf.length() == 0) {
        throw new IllegalStateException('Preview warmup did not produce a PDF')
    }
} finally {
    warmXml.delete()
    warmPdf.delete()
}
reply([ready:true])
def input = new BufferedReader(new InputStreamReader(System.in, 'UTF-8'))
String line
while ((line = input.readLine()) != null) {
    try {
        def request = new JsonSlurper().parseText(line)
        ModelFactory.builder(request.code).saveToPDF(request.xml as String,
            request.section ? request.section as String : null,
            request.output as String, new SimpleCallback[0])
        reply([ok:true])
    } catch (Throwable error) {
        error.printStackTrace()
        reply([ok:false, message:error.toString()])
    }
}
'''


def build_java_command(client, workspace, heap_mib: int, codeset_base: str, extra_flags=()) -> list[str]:
    """Pure command line for the owned rendering JVM; every flow-control path shares it."""
    work = Path(workspace)
    return [
        str(client.java),
        f"-Xmx{heap_mib}m",
        "-Dfile.encoding=UTF-8",
        f"-Dcpc.home={work}",
        f"-Dcpc_path={work / 'data'}",
        f"-Djava.io.tmpdir={work / 'tmp'}",
        *java_options(codeset_base),
        *extra_flags,
        "-cp",
        str(work / "classpath.jar"),
        "groovy.ui.GroovyMain",
        str(work / "render.groovy"),
    ]


class InstalledLibraryManager:
    """One owned rendering JVM; installation supplies read-only binaries, never state."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._client: InstalledClient | None = None
        self._invalid = ""
        self._discovery_attempted = False
        self._process = None
        self._workspace = None
        self._reader = None
        self._messages: queue.Queue = queue.Queue()
        self._logs: deque[str] = deque(maxlen=12)
        self._memory_exhausted = False
        self._state = RendererState.STOPPED
        self._rendering = False
        self._shutdown = threading.Event()
        self._codeset = CodesetState(False, UNREACHABLE_BASE_PATH, NOT_DETECTED_DETAIL)

    def configured_path(self) -> str | None:
        return str(self._client.root) if self._client else remembered_client_path()

    def configuration_error(self) -> str:
        return self._invalid

    def codeset_state(self) -> CodesetState:
        """Latest code-set detection; the GUI reads availability from here, never by raising."""
        return self._codeset

    def configure(self, path: str | None = None, *, detect: bool = False) -> InstalledClient:
        if not self._lock.acquire(blocking=False):
            raise PreviewRuntimeError("正在启动或生成预览，请完成或取消后再选择客户端。")
        try:
            if self._rendering:
                raise PreviewRuntimeError("正在生成预览，请完成或取消后再选择客户端。")
            client = detect_client() if detect else inspect_installed_client(path)
            unchanged = (
                self._client is not None
                and client.root == self._client.root
                and client.signature == self._client.signature
            )
            if not unchanged:
                self._stop()
                self._codeset = CodesetState(False, UNREACHABLE_BASE_PATH, NOT_DETECTED_DETAIL)
            remember_client(client)
            self._client = client
            self._invalid = ""
            self._discovery_attempted = True
            return client
        finally:
            self._lock.release()

    def _resolve_client(self) -> InstalledClient:
        if self._invalid:
            raise PreviewRuntimeError(self._invalid)
        try:
            if self._client is None:
                path = remembered_client_path()
                if path:
                    self._client = inspect_installed_client(path)
                elif not self._discovery_attempted:
                    self._discovery_attempted = True
                    self._client = detect_client()
                    remember_client(self._client)
                else:
                    from .installed_client import CLIENT_MISSING
                    raise PreviewRuntimeError(CLIENT_MISSING)
            elif component_signature(self._client.watched) != self._client.signature:
                self._stop()
                self._client = inspect_installed_client(self._client.root)
            return self._client
        except (OSError, PreviewRuntimeError) as exc:
            self._stop()
            self._invalid = str(exc) + "\n请在全量预览设置中重新检测或选择客户端目录。"
            self._state = RendererState.FAILED
            raise PreviewRuntimeError(self._invalid) from exc

    def state_info(self) -> RendererStateInfo:
        state = self._state
        if state == RendererState.RUNNING and not self.is_running():
            state = RendererState.STOPPED
        return RendererStateInfo(state, runtime_id=self.configured_path() or "", detail=self._invalid)

    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None and self._state == RendererState.RUNNING

    def is_rendering(self) -> bool:
        return self._rendering

    @contextlib.contextmanager
    def _acquire(self, cancelled=None, startup_wait_callback=None):
        start = time.monotonic()
        while not self._lock.acquire(timeout=0.1):
            self._check_cancel(cancelled)
            if startup_wait_callback:
                startup_wait_callback(time.monotonic() - start)
        try:
            self._check_cancel(cancelled)
            yield
        finally:
            self._lock.release()

    def _check_cancel(self, cancelled) -> None:
        if self._shutdown.is_set() or (cancelled and cancelled()):
            raise FormRenderCancelled("已取消全量预览。")

    def _read_messages(self, process, messages) -> None:
        try:
            for line in process.stdout:
                if line.startswith(_PREFIX):
                    try:
                        messages.put(json.loads(line[len(_PREFIX):]))
                    except ValueError:
                        messages.put(None)
                else:
                    if "java.lang.OutOfMemoryError" in line:
                        self._memory_exhausted = True
                    self._logs.append(line.rstrip()[-500:])
        finally:
            messages.put(None)

    def _wait(self, *, cancelled=None, progress=None, timeout=120):
        start = time.monotonic()
        last_report = -1
        while True:
            self._check_cancel(cancelled)
            elapsed = time.monotonic() - start
            if elapsed > timeout:
                raise TimeoutError("官方文书渲染超时，已停止本次任务，请检查案卷或重试。")
            if progress and int(elapsed) != last_report:
                last_report = int(elapsed)
                progress(elapsed)
            try:
                message = self._messages.get(timeout=0.1)
            except queue.Empty:
                continue
            if message is None:
                raise PreviewRuntimeError("官方渲染进程已退出：" + "\n".join(self._logs))
            return message

    @staticmethod
    def _java_data_model(java: Path) -> int:
        """Return the launched JVM data model; unknown runtimes default to 32-bit safety."""
        try:
            result = subprocess.run(
                [str(java), "-XshowSettings:properties", "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except (OSError, subprocess.SubprocessError):
            return 32
        match = re.search(r"(?m)^\s*sun\.arch\.data\.model\s*=\s*(32|64)\s*$", result.stdout or "")
        return int(match.group(1)) if match else 32

    @staticmethod
    def _heap_candidates(java_data_model: int) -> tuple[int, ...]:
        if java_data_model == 64:
            return (1536, 1024)
        return (1024, 768)

    @staticmethod
    def _is_heap_reservation_failure(error: BaseException) -> bool:
        return _HEAP_RESERVATION_ERROR in str(error).casefold()

    def _start(self, client, *, cancelled=None, startup_wait_callback=None):
        java_data_model = self._java_data_model(client.java)
        heap_candidates = self._heap_candidates(java_data_model)
        for index, heap_mib in enumerate(heap_candidates):
            try:
                self._start_once(
                    client,
                    heap_mib=heap_mib,
                    java_data_model=java_data_model,
                    cancelled=cancelled,
                    startup_wait_callback=startup_wait_callback,
                )
                return
            except PreviewRuntimeError as exc:
                self._stop()
                if index + 1 >= len(heap_candidates) or not self._is_heap_reservation_failure(exc):
                    raise
                _LOGGER.warning(
                    "Full preview JVM could not reserve %s MiB; retrying with %s MiB",
                    heap_mib,
                    heap_candidates[index + 1],
                )

    def _start_once(self, client, *, heap_mib, java_data_model, cancelled=None, startup_wait_callback=None):
        started = time.monotonic()
        base = Path(get_user_data_dir()) / "preview-work"
        base.mkdir(parents=True, exist_ok=True)
        self._workspace = tempfile.TemporaryDirectory(prefix="session-", dir=base)
        work = Path(self._workspace.name)
        (work / "tmp").mkdir()
        (work / "data").mkdir()
        script = work / "render.groovy"
        script.write_text(_WORKER, encoding="utf-8")
        launcher = work / "classpath.jar"
        with zipfile.ZipFile(launcher, "w") as archive:
            archive.writestr("META-INF/MANIFEST.MF", java_classpath_manifest(client))
        self._state = RendererState.STARTING
        self._messages = queue.Queue()
        self._logs.clear()
        _LOGGER.info("Starting full preview JVM: java_data_model=%s heap_mib=%s", java_data_model, heap_mib)
        command = build_java_command(client, work, heap_mib, self._codeset.base)
        self._process = subprocess.Popen(
            command,
            cwd=work, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        self._reader = threading.Thread(target=self._read_messages, args=(self._process, self._messages), daemon=True)
        self._reader.start()
        message = self._wait(cancelled=cancelled, progress=startup_wait_callback, timeout=60)
        if message != {"ready": True}:
            raise PreviewRuntimeError("官方渲染库初始化失败，请重新检测客户端。")
        self._state = RendererState.RUNNING
        _LOGGER.info("Full preview JVM and PDF warmup completed in %.3f s", time.monotonic() - started)

    def prewarm(self, *, startup_wait_callback=None, cancelled=None):
        with self._acquire(cancelled, startup_wait_callback):
            self._ensure_ready(cancelled=cancelled, startup_wait_callback=startup_wait_callback)

    def _ensure_ready(self, *, cancelled=None, startup_wait_callback=None, refresh_codeset: bool = True):
        client = self._resolve_client()
        if self.is_running():
            if not refresh_codeset:
                return
            # The client may have been started or closed since the batch before, so a
            # batch only reuses this JVM while its code-set address still matches.
            codeset = detect_codeset_state(client.root)
            if (codeset.available, codeset.base) == (self._codeset.available, self._codeset.base):
                return
            _LOGGER.info("Code-set service changed to %s (%s); restarting full preview JVM", codeset.base, codeset.detail)
        else:
            codeset = detect_codeset_state(client.root)
        self._codeset = codeset
        self._stop()
        try:
            self._start(client, cancelled=cancelled, startup_wait_callback=startup_wait_callback)
        except BaseException as exc:
            self._stop()
            if not isinstance(exc, FormRenderCancelled):
                self._invalid = f"无法加载客户端渲染组件：{exc}\n请重新检测或选择客户端目录。"
                self._state = RendererState.FAILED
            raise

    @contextlib.contextmanager
    def library_session(self, *, startup_wait_callback=None, cancelled=None):
        with self._acquire(cancelled, startup_wait_callback):
            self._ensure_ready(cancelled=cancelled, startup_wait_callback=startup_wait_callback)
            self._rendering = True
            try:
                yield self
            finally:
                self._rendering = False

    def render_document(self, xml_path: Path, code: str, *, cancelled=None) -> bytes:
        # Documents render inside one batch session, which already validated the code-set address.
        self._ensure_ready(cancelled=cancelled, refresh_codeset=False)
        started = time.monotonic()
        section = xml_path.with_name("section_1.xml")
        if any(p.name != "section_1.xml" for p in xml_path.parent.glob("section_*.xml")):
            raise PreviewRuntimeError("检测到多个 section 附页文件，尚未验证此结构，已停止生成以免遗漏内容。")
        work = Path(self._workspace.name)
        output = work / "output.pdf"
        output.unlink(missing_ok=True)
        # Official form models split paths on '/', including on Windows.
        request = {"code": code, "xml": xml_path.as_posix(), "section": section.as_posix() if section.is_file() else "", "output": output.as_posix()}
        try:
            self._check_cancel(cancelled)
            self._memory_exhausted = False
            self._process.stdin.write(json.dumps(request, ensure_ascii=True) + "\n")
            self._process.stdin.flush()
            result = self._wait(cancelled=cancelled)
            if component_signature(self._client.watched) != self._client.signature:
                self._stop()
                raise PreviewRuntimeError("客户端组件在预览期间发生变化，本次结果未采用，请等待客户端更新完成后重试。")
            if not result.get("ok"):
                if self._memory_exhausted:
                    self._stop()
                    raise PreviewRuntimeError("官方渲染器内存不足，已停止本次渲染进程。请减少同时预览的文书后重试；单份文书仍失败时需检查其中的大尺寸图片。")
                raise PreviewRuntimeError("官方渲染失败：" + str(result.get("message", "未知错误")))
            content = output.read_bytes()
            if not content.startswith(b"%PDF-"):
                raise PreviewRuntimeError("官方渲染器未生成有效 PDF。")
            _LOGGER.info("Full preview document %s rendered in %.3f s", code, time.monotonic() - started)
            return content
        except (FormRenderCancelled, TimeoutError):
            self._stop()
            raise
        except (OSError, PreviewRuntimeError) as exc:
            if self._process is not None and self._process.poll() is not None:
                self._invalid = f"客户端渲染进程异常退出，请重新检测或选择目录。{exc}"
                self._stop()
                self._state = RendererState.FAILED
            raise

    def _stop(self):
        if self._process is not None:
            if self._process.poll() is None:
                self._process.kill()
            self._process.wait()
            self._process.stdin.close()
            if self._reader:
                self._reader.join(timeout=2)
            self._process.stdout.close()
            self._process = None
        if self._workspace is not None:
            self._workspace.cleanup()
            self._workspace = None
        self._state = RendererState.STOPPED

    def shutdown(self):
        self._shutdown.set()
        with self._lock:
            self._stop()
        stop_local_codeset_server()
