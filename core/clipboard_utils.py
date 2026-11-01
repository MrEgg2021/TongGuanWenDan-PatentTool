import win32clipboard
import win32ui
import win32gui
import win32con
import struct
from PIL import Image
import ctypes
from ctypes import wintypes
from core.logging_utils import logger
import os
import time

# GDI+ constants and structures if needed, but we try to use win32gui first.

EMF_CLIPBOARD_FORMATS = (win32con.CF_ENHMETAFILE,)
IMAGE_CLIPBOARD_FORMATS = (
    win32con.CF_DIB,
    win32con.CF_BITMAP,
    win32con.CF_ENHMETAFILE,
)


def get_clipboard_sequence_number():
    try:
        return int(win32clipboard.GetClipboardSequenceNumber())
    except Exception as e:
        logger.debug(f"Clipboard sequence unavailable: {e}")
        return None


def _clipboard_has_any_format(formats):
    opened = False
    try:
        win32clipboard.OpenClipboard()
        opened = True
        return any(win32clipboard.IsClipboardFormatAvailable(fmt) for fmt in formats)
    except Exception as e:
        logger.debug(f"Clipboard format check failed: {e}")
        return False
    finally:
        if opened:
            try:
                win32clipboard.CloseClipboard()
            except Exception:
                pass


def wait_for_clipboard_fresh_content(previous_sequence, formats, timeout_s=1.0, poll_s=0.05):
    if previous_sequence is None:
        return False

    deadline = time.monotonic() + float(timeout_s)
    while True:
        current_sequence = get_clipboard_sequence_number()
        if (
            current_sequence is not None
            and current_sequence != previous_sequence
            and _clipboard_has_any_format(formats)
        ):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(float(poll_s))


def get_clipboard_emf_content():
    """从剪贴板获取 EMF 数据 (bytes)"""
    content = None
    opened = False
    try:
        win32clipboard.OpenClipboard()
        opened = True
        if win32clipboard.IsClipboardFormatAvailable(win32con.CF_ENHMETAFILE):
            content = win32clipboard.GetClipboardData(win32con.CF_ENHMETAFILE)
    except Exception as e:
        logger.warning(f"Clipboard Error: {e}")
    finally:
        if opened:
            try:
                win32clipboard.CloseClipboard()
            except Exception:
                pass
    return content


def render_emf_bytes_to_png(
    emf_bytes,
    output_path,
    scale=4.0,
    min_width=1000,
    *,
    trim_render_margin: bool = False,
):
    """将 EMF 二进制数据渲染为 PNG。"""
    if not emf_bytes:
        return False

    try:
        logger.debug(
            "[EMF_RENDER] start bytes=%d scale=%r min_width=%r output=%r",
            len(emf_bytes) if hasattr(emf_bytes, "__len__") else -1,
            scale,
            min_width,
            output_path,
        )
    except Exception:
        pass

    # 1. 将 bytes 转换为 EMF Handle
    # win32gui 没有暴露 SetEnhMetaFileBits，改用 ctypes 调用 gdi32
    try:
        gdi32 = ctypes.windll.gdi32
        # HENHMETAFILE SetEnhMetaFileBits(UINT cbBuffer, const BYTE *lpData);
        SetEnhMetaFileBits = gdi32.SetEnhMetaFileBits
        SetEnhMetaFileBits.argtypes = [wintypes.UINT, ctypes.POINTER(ctypes.c_byte)]
        SetEnhMetaFileBits.restype = wintypes.HANDLE

        # 创建字节数组指针
        byte_array = (ctypes.c_byte * len(emf_bytes)).from_buffer_copy(emf_bytes)
        hEMF = SetEnhMetaFileBits(len(emf_bytes), byte_array)
    except Exception as e:
        logger.error(f"GDI32 API Error: {e}")
        hEMF = None

    if not hEMF:
        logger.error("Failed to create EMF handle from bits")
        return False

    try:
        # 2. 获取 Header 以计算尺寸
        # 直接解析 ENHMETAHEADER.rclFrame (0.01mm 单位)
        rclFrame = struct.unpack("iiii", emf_bytes[24:40])
        left, top, right, bottom = rclFrame

        width_01mm = right - left
        height_01mm = bottom - top

        # 转换为像素 (假设 96 DPI)
        # 1 inch = 25.4 mm = 2540 (0.01mm)
        # px = (units / 2540) * dpi
        width_px_96 = (width_01mm / 2540.0) * 96
        height_px_96 = (height_01mm / 2540.0) * 96

        try:
            logger.debug(
                "[EMF_RENDER] rclFrame=%r width_01mm=%r height_01mm=%r width_px_96=%.3f height_px_96=%.3f",
                rclFrame,
                width_01mm,
                height_01mm,
                width_px_96,
                height_px_96,
            )
        except Exception:
            pass

        # 确定渲染尺寸
        target_width = max(int(width_px_96 * scale), min_width)
        scale_ratio = target_width / max(width_px_96, 1e-6)
        target_height = int(height_px_96 * scale_ratio)

        # 使用较大的内部渲染边距，防止 EMF 内容溢出 rclFrame 边界
        render_margin = 200
        canvas_width = target_width + 2 * render_margin
        canvas_height = target_height + 2 * render_margin

        try:
            logger.debug(
                "[EMF_RENDER] target=%dx%d canvas=%dx%d margin=%d scale_ratio=%.6f",
                target_width,
                target_height,
                canvas_width,
                canvas_height,
                render_margin,
                scale_ratio,
            )
        except Exception:
            pass

        # 3. 创建 DC 和 Bitmap
        # 获取屏幕 DC
        hDC_screen = win32gui.GetDC(0)

        try:
            screen_dpi_x = None
            screen_dpi_y = None
            try:
                _dc = win32ui.CreateDCFromHandle(hDC_screen)
                screen_dpi_x = _dc.GetDeviceCaps(win32con.LOGPIXELSX)
                screen_dpi_y = _dc.GetDeviceCaps(win32con.LOGPIXELSY)
            except Exception:
                screen_dpi_x = None
                screen_dpi_y = None
            logger.debug("[EMF_RENDER] screen_dpi=%r x %r", screen_dpi_x, screen_dpi_y)
        except Exception:
            pass

        # 创建兼容 DC
        hDC = win32gui.CreateCompatibleDC(hDC_screen)
        # 创建位图
        hBitmap = win32gui.CreateCompatibleBitmap(hDC_screen, canvas_width, canvas_height)

        win32gui.SelectObject(hDC, hBitmap)

        # 4. 绘制背景 (白色)
        brush = win32gui.GetStockObject(win32con.WHITE_BRUSH)
        win32gui.FillRect(hDC, (0, 0, canvas_width, canvas_height), brush)

        # 5. 绘制 EMF
        # PlayEnhMetaFile(hdc, hemf, rect)
        # rect 是 (left, top, right, bottom)
        # win32gui 同样没有暴露 PlayEnhMetaFile，改用 ctypes
        # BOOL PlayEnhMetaFile(HDC hdc, HENHMETAFILE hemf, const RECT *lpRect);
        try:
            PlayEnhMetaFile = gdi32.PlayEnhMetaFile
            PlayEnhMetaFile.argtypes = [wintypes.HDC, wintypes.HANDLE, ctypes.POINTER(wintypes.RECT)]
            PlayEnhMetaFile.restype = wintypes.BOOL

            rect_struct = wintypes.RECT(
                render_margin,
                render_margin,
                render_margin + target_width,
                render_margin + target_height,
            )
            played_ok = PlayEnhMetaFile(hDC, hEMF, ctypes.byref(rect_struct))
            if not played_ok:
                logger.error("PlayEnhMetaFile failed")
            try:
                logger.debug("[EMF_RENDER] PlayEnhMetaFile ok=%r rect=%r", bool(played_ok), (rect_struct.left, rect_struct.top, rect_struct.right, rect_struct.bottom))
            except Exception:
                pass
        except Exception as e:
            logger.error(f"PlayEnhMetaFile Error: {e}")

        # 6. 提取位图数据
        # 使用 win32ui 包装以便于操作
        win32ui.CreateDCFromHandle(hDC)
        mfcBitmap = win32ui.CreateBitmapFromHandle(hBitmap)

        # GetBitmapBits
        bmpinfo = mfcBitmap.GetInfo()
        bmpstr = mfcBitmap.GetBitmapBits(True)

        try:
            logger.debug(
                "[EMF_RENDER] bitmap_info width=%r height=%r bitsPixel=%r bmWidthBytes=%r",
                bmpinfo.get("bmWidth"),
                bmpinfo.get("bmHeight"),
                bmpinfo.get("bmBitsPixel"),
                bmpinfo.get("bmWidthBytes"),
            )
        except Exception:
            pass

        # 转 PIL
        img = Image.frombuffer(
            "RGB",
            (bmpinfo["bmWidth"], bmpinfo["bmHeight"]),
            bmpstr,
            "raw",
            "BGRX",
            0,
            1,
        )

        try:
            ext = None
            try:
                ext = os.path.splitext(str(output_path))[1].lower()
            except Exception:
                ext = None
            logger.debug("[EMF_RENDER] pil_image_size=%r output_ext=%r", getattr(img, "size", None), ext)
        except Exception:
            pass

        # 7. 直接保存渲染结果，后续由 ImageProcessor._crop_white_borders 做统一白边裁剪
        try:
            parent_dir = os.path.dirname(os.path.abspath(str(output_path)))
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
        except Exception as ensure_err:
            raise OSError(f"EMF 输出目录不存在且无法创建: {output_path}") from ensure_err

        output_img = img
        if trim_render_margin:
            output_img = img.crop(
                (
                    render_margin,
                    render_margin,
                    render_margin + target_width,
                    render_margin + target_height,
                )
            )
        output_img.save(output_path, format="PNG", dpi=(300, 300))

        try:
            out_size = None
            try:
                out_size = os.path.getsize(output_path)
            except Exception:
                out_size = None
            logger.debug("[EMF_RENDER] saved path=%r file_size=%r", output_path, out_size)
        except Exception:
            pass

        # 清理
        win32gui.DeleteObject(hBitmap)
        win32gui.DeleteDC(hDC)
        win32gui.ReleaseDC(0, hDC_screen)

        return True

    except Exception as e:
        logger.exception(f"EMF Render Error: {e}")
        return False
    finally:
        try:
            gdi32.DeleteEnhMetaFile(hEMF)
        except Exception:
            pass

