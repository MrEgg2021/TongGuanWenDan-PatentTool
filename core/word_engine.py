import logging
import time
import psutil

from core.office_process_safety import scan_office_processes
from core.word_engine_impl.start_app import start_app as _start_app
from core.word_engine_impl.com_compat import add_hidden_document
from core.word_engine_impl.doc_ops import open_doc as _open_doc, open_doc_for_review as _open_doc_for_review
from core.word_engine_impl.clipboard_ops import (
    copy_range_as_picture as _copy_range_as_picture,
    copy_shape_to_clipboard as _copy_shape_to_clipboard,
    copy_shape_to_clipboard_scaled as _copy_shape_to_clipboard_scaled,
    export_inline_shape_as_picture as _export_inline_shape_as_picture,
    export_shape_as_picture as _export_shape_as_picture,
)

from core.word_engine_impl.process_registry import (
    _load_office_process_registry as _load_office_process_registry_impl,
    _unregister_office_process,
    terminate_owned_office_processes,
)
from core.word_engine_impl.process_utils import _is_same_process
from core.word_engine_impl.owned_process_claim import try_claim_word_process_for_engine
from core.word_engine_impl.window_probe import _visible_window_pids


def _append_word_startup_faq(message: str) -> str:
    try:
        msg = str(message or "").strip()
    except Exception:
        msg = ""

    marker = "[WORD_STARTUP_FAQ]"
    if marker in msg:
        return msg

    faq = (
        marker
        + "\n若你遇到 Word 启动失败/卡住/偶发闪现/文件被占用，建议按以下思路排查："
        + "\n1) 请确认已关闭所有 Word/WPS（任务管理器中也不要残留 WINWORD.EXE/WPS.EXE）。"
        + "\n2) 若 Word 以隐藏方式启动后崩溃，可能残留后台进程导致文件锁死；可先结束残留 WINWORD.EXE 再重试。"
        + "\n3) 可能存在 Word ‘欢迎/开始屏幕’或‘首次启动隐私引导’弹窗干扰静默 COM；建议手动打开一次 Word 完成引导，"
        + "\n   并在 Word 选项中关闭启动时显示开始屏幕（不同版本名称可能不同）。"
        + "\n4) 若仍失败，请重启电脑后再试，以清理系统级残留句柄/加载项影响。"
    )

    if not msg:
        return faq
    return msg + "\n\n" + faq


def _load_office_process_registry() -> tuple[str, list[dict]]:
    """Compatibility export for callers importing from core.word_engine."""
    return _load_office_process_registry_impl()


class WordComHijackedError(RuntimeError):
    def __init__(self, message, *, attempted_progids=None, last_diag=None, last_error=None):
        super().__init__(message)
        self.attempted_progids = attempted_progids or []
        self.last_diag = last_diag
        self.last_error = last_error


class WordEngine:
    """
    Word 自动化操作引擎
    负责：进程管理、文档打开/预处理、对象截图
    """

    def __init__(self, config):
        self.config = config
        self.app = None
        self.doc = None
        self._canvas_doc = None  # 常驻画布文档
        self._owned_pid = None
        self._owned_create_time = None
        self._app_started_ts = None
        self._app_start_before_snapshot = None
        self._app_start_min_create_time = None
        self._visible_true_since_ts = None
        self._runtime_guard_last_check_ts = 0.0
        self._logger = logging.getLogger(__name__)

    def _abort_owned_process(self, reason: str) -> None:
        allow_kill = False
        try:
            allow_kill = bool((self.config or {}).get("allow_kill", False))
        except Exception:
            allow_kill = False

        try:
            pid = self._owned_pid
            ct = self._owned_create_time
            if pid and ct is not None:
                if _is_same_process(int(pid), float(ct), target_names={"winword.exe"}):
                    p = psutil.Process(int(pid))
                    try:
                        p.terminate()
                    except Exception:
                        pass
                    try:
                        p.wait(timeout=3)
                    except Exception:
                        if allow_kill:
                            try:
                                p.kill()
                            except Exception:
                                pass
        except Exception:
            pass
        finally:
            try:
                _unregister_office_process(self._owned_pid, self._owned_create_time)
            except Exception:
                pass
            self._owned_pid = None
            self._owned_create_time = None
            self.doc = None
            self.app = None

        raise RuntimeError(reason)

    def _runtime_guard_check(self) -> None:
        try:
            now = time.time()
        except Exception:
            now = 0.0
        try:
            if now and (now - float(self._runtime_guard_last_check_ts)) < 1.0:
                return
        except Exception:
            pass
        try:
            self._runtime_guard_last_check_ts = float(now)
        except Exception:
            self._runtime_guard_last_check_ts = 0.0

        if not self.app:
            return

        try:
            visible = bool(getattr(self.app, "Visible", False))
        except Exception:
            visible = False

        in_grace = False
        try:
            if self._app_started_ts is not None and now:
                in_grace = (now - float(self._app_started_ts)) < 5.0
        except Exception:
            in_grace = False

        if visible:
            try:
                self.app.Visible = False
            except Exception:
                pass

            if not in_grace:
                try:
                    if self._visible_true_since_ts is None:
                        self._visible_true_since_ts = float(now) if now else 0.0
                        self._logger.warning(
                            "[WORD_GUARD] 检测到 Word Visible=True，已尝试强制隐藏。若该状态持续，将中止转换以避免产出错误。"
                        )
                except Exception:
                    self._visible_true_since_ts = float(now) if now else 0.0

                sustained = False
                try:
                    if now and self._visible_true_since_ts is not None:
                        sustained = (now - float(self._visible_true_since_ts)) >= 2.0
                except Exception:
                    sustained = False

                if sustained:
                    self._abort_owned_process(
                        "检测到在本工具运行期间 Word 窗口持续可见（疑似用户介入）。为避免生成错误案卷包并保护环境，本工具已中止。请关闭所有 Word/WPS 后重试。"
                    )
        else:
            self._visible_true_since_ts = None

        owned_pid = None
        try:
            owned_pid = int(self._owned_pid) if self._owned_pid else None
        except Exception:
            owned_pid = None
        if owned_pid is None and in_grace:
            claim_min_create_time = None
            try:
                claim_min_create_time = (
                    float(self._app_start_min_create_time)
                    if self._app_start_min_create_time is not None
                    else float(self._app_started_ts)
                    if self._app_started_ts is not None
                    else None
                )
            except Exception:
                claim_min_create_time = None
            try:
                claim_before_snapshot = (
                    dict(self._app_start_before_snapshot)
                    if isinstance(self._app_start_before_snapshot, dict)
                    else None
                )
            except Exception:
                claim_before_snapshot = None
            try:
                try_claim_word_process_for_engine(
                    self,
                    before_snapshot=claim_before_snapshot,
                    min_create_time=claim_min_create_time,
                    reason="runtime_guard_startup_grace",
                )
            except Exception:
                pass
            try:
                owned_pid = int(self._owned_pid) if self._owned_pid else None
            except Exception:
                owned_pid = None
        visible_pids = None
        try:
            visible_pids = _visible_window_pids()
        except Exception:
            visible_pids = None
        foreign = [
            (item.name.lower(), item.pid)
            for item in scan_office_processes()
            if item.pid != owned_pid
        ]

        if foreign:
            try:
                self._logger.warning(
                    "[WORD_GUARD_FOREIGN] aborting conversion owned_pid=%r foreign=%r visible_pids=%r",
                    owned_pid,
                    foreign,
                    visible_pids,
                )
            except Exception:
                pass
            self._abort_owned_process(
                "检测到未被本工具认领的 Word/WPS 进程，可能是历史残留、其他程序启动或用户新开。"
                "该状态会影响本工具的安全与产出正确性，本工具已中止。请关闭所有 Word/WPS 后重试。"
            )

    def get_canvas_doc(self):
        """获取或创建常驻画布文档 (用于截图中转)"""
        if self._canvas_doc:
            try:
                # 检查是否还活着
                _ = self._canvas_doc.Name
                return self._canvas_doc
            except Exception:
                self._canvas_doc = None

        if not self.app:
            return None

        try:
            self._logger.debug("[CANVAS] Creating new persistent canvas document...")
            # 创建新文档，隐藏
            doc = add_hidden_document(self.app, logger=self._logger)
            try:
                doc.Activate()
                # 调整视图模式为普通视图或页面视图，避免 Web 版式影响
                # wdPrintView = 3
                if self.app.ActiveWindow:
                    self.app.ActiveWindow.View.Type = 3
            except Exception:
                pass
            self._canvas_doc = doc
            return doc
        except Exception as e:
            self._logger.warning(f"⚠️ Failed to create canvas doc: {e}")
            return None

    def clean_zombie_processes(self):
        """清理残留的 Word/WPS 进程"""
        if not self.config.get('kill_zombies', True):
            return

        self._logger.info("🔍 扫描僵尸 Word/WPS 进程...")
        count = 0
        try:
            allow_kill = False
            try:
                allow_kill = bool((self.config or {}).get("allow_kill", False))
            except Exception:
                allow_kill = False
            count = int(terminate_owned_office_processes(allow_kill=allow_kill))
        except Exception:
            count = 0

        if count > 0:
            self._logger.info(f"🧹 已清理 {count} 个僵尸 Word/WPS 进程")
            time.sleep(1)  # 等待清理完成

    def start_app(self):
        """启动 Word 进程 (静默模式)"""
        try:
            return _start_app(self, _append_word_startup_faq)
        except Exception as e:
            msg = ""
            try:
                msg = str(e)
            except Exception:
                msg = ""
            if "[WORD_STARTUP_FAQ]" in msg:
                raise WordComHijackedError(msg, last_error=repr(e)) from e
            raise

    def open_doc(self, file_path):
        """
        打开文档并执行预处理 (Unlink, AcceptRevisions)
        .doc 会转为临时 DOCX；.docx 保持已打开文档供解析
        """
        return _open_doc(self, file_path)

    def open_doc_for_review(self, file_path):
        """
        形式审查专用入口：
        只读打开文档，允许源文档包含批注/修订，不改变原文档内容。
        """
        return _open_doc_for_review(self, file_path)

    def copy_range_as_picture(self, range_obj, use_copy_as_picture=False):
        """将指定 Range 复制为图片到剪贴板"""
        return bool(_copy_range_as_picture(self, range_obj, use_copy_as_picture=use_copy_as_picture))
    
    def copy_shape_to_clipboard(self, shape_obj, use_copy_as_picture=False):
        """复制 InlineShape 到剪贴板（用于普通图片）"""
        return bool(_copy_shape_to_clipboard(self, shape_obj, use_copy_as_picture=use_copy_as_picture))

    def copy_shape_to_clipboard_scaled(self, shape_obj, scale_factor=1.0, use_copy_as_picture=True):
        return bool(
            _copy_shape_to_clipboard_scaled(
                self,
                shape_obj,
                scale_factor=scale_factor,
                use_copy_as_picture=use_copy_as_picture,
            )
        )

    def export_inline_shape_as_picture(self, inline_shape, output_path: str) -> bool:
        return bool(_export_inline_shape_as_picture(self, inline_shape, output_path))

    def export_shape_as_picture(self, shape_obj, output_path: str) -> bool:
        return bool(_export_shape_as_picture(self, shape_obj, output_path))

    def close_doc(self):
        """关闭文档"""
        # 先清理画布
        if self._canvas_doc:
            try:
                self._canvas_doc.Close(SaveChanges=0)
            except Exception:
                pass
            self._canvas_doc = None

        if self.doc:
            try:
                # wdDoNotSaveChanges = 0
                self.doc.Close(SaveChanges=0)
                self._logger.info("📕 文档已关闭")
            except Exception as e:
                self._logger.warning(f"⚠️ 关闭文档时出错: {e}")
            finally:
                self.doc = None

    def quit_app(self):
        """退出 Word 进程 (确保无残留)"""
        self.close_doc()
        
        if self.app:
            try:
                self._logger.info("🛑 正在退出 Word 进程...")
                self.app.Quit(SaveChanges=0)
            except Exception as e:
                self._logger.warning(f"⚠️ 退出 Word 时出错: {e}")
            finally:
                self.app = None

        try:
            if self._owned_pid and self._owned_create_time is not None:
                try:
                    allow_kill = False
                    try:
                        allow_kill = bool((self.config or {}).get("allow_kill", False))
                    except Exception:
                        allow_kill = False

                    if _is_same_process(int(self._owned_pid), float(self._owned_create_time), target_names={"winword.exe"}):
                        p = psutil.Process(int(self._owned_pid))
                        try:
                            p.wait(timeout=10)
                        except Exception:
                            try:
                                p.terminate()
                            except Exception:
                                pass
                            try:
                                p.wait(timeout=3)
                            except Exception:
                                if allow_kill:
                                    try:
                                        p.kill()
                                    except Exception:
                                        pass
                except Exception:
                    pass
        finally:
            try:
                _unregister_office_process(self._owned_pid, self._owned_create_time)
            except Exception:
                pass
            self._owned_pid = None
            self._owned_create_time = None
