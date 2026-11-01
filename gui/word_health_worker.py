from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, Signal, Slot

from core.word_startup_health import WordStartupHealthResult, check_word_startup_health

try:
    import pythoncom
except Exception:  # pragma: no cover - pywin32 is present in supported Windows runtime.
    pythoncom = None


_ProgressText = tuple[int, str, str]


_PROGRESS_BY_STAGE: dict[str, _ProgressText] = {
    "locate_word": (5, "正在后台检查 Word 环境", "正在定位 Microsoft Word..."),
    "start_word": (15, "正在后台检查 Word 环境", "正在检查 Word 能否正常启动..."),
    "bind_com": (35, "正在后台检查 Word 环境", "正在确认 Word 可用于转换..."),
    "test_pdf_export": (50, "正在检测 Word PDF 导出", "正在检查 Word 能否导出 PDF..."),
    "quit_word": (60, "正在后台检查 Word 环境", "正在关闭本次检查启动的 Word..."),
    "wait_exit": (72, "正在后台检查 Word 环境", "正在确认 Word 能正常退出..."),
    "slow_exit_wait": (82, "Word 首次启动较慢", "仍在等待本次检查启动的 Word 退出，请稍候..."),
    "done": (95, "Word 环境检查完成", "正在继续转换..."),
}


class WordHealthWorker(QObject):
    progress = Signal(int, str, str)
    finished = Signal(object)

    def __init__(
        self,
        *,
        killed_before_check: bool = False,
        health_check: Callable[..., WordStartupHealthResult] = check_word_startup_health,
    ) -> None:
        super().__init__()
        self._killed_before_check = bool(killed_before_check)
        self._health_check = health_check

    @Slot()
    def run(self) -> None:
        initialized = False
        try:
            if pythoncom is not None:
                pythoncom.CoInitialize()
                initialized = True
            result = self._health_check(
                killed_before_check=self._killed_before_check,
                progress_callback=self._on_core_progress,
            )
        except Exception as exc:
            result = WordStartupHealthResult(
                ok=False,
                pid=None,
                binding_progid=None,
                error=str(exc),
                killed_before_check=self._killed_before_check,
                reason_code="health_worker_failed",
                user_message="Word 启动检查未通过。检查未能完成，请重试；如仍失败，请重启程序后重试。",
                technical_detail=repr(exc),
            )
        finally:
            if initialized and pythoncom is not None:
                try:
                    pythoncom.CoUninitialize()
                except Exception:
                    pass
        self.finished.emit(result)

    def _on_core_progress(self, stage: str, payload: dict) -> None:
        percent, primary, detail = _PROGRESS_BY_STAGE.get(
            str(stage or ""),
            (10, "正在后台检查 Word 环境", "正在执行 Word 启动检查..."),
        )
        if str(stage or "") == "slow_exit_wait":
            try:
                timeout = float((payload or {}).get("timeout", 0.0))
            except Exception:
                timeout = 0.0
            if timeout > 0:
                detail = f"Word 首次启动较慢，仍在后台等待退出，最多再等待 {timeout:.0f} 秒..."
        self.progress.emit(int(percent), str(primary), str(detail))


__all__ = ["WordHealthWorker"]
