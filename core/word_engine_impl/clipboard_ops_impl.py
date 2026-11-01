import time


from PIL import Image

from core.word_engine_impl.com_compat import add_hidden_document


def _force_render_range(range_obj) -> None:
    """Best-effort: force Word to layout equations/fields before copy."""
    if range_obj is None:
        return
    try:
        fields = getattr(range_obj, "Fields", None)
        if fields is not None:
            fields.Update()
    except Exception:
        pass
    try:
        omaths = getattr(range_obj, "OMaths", None)
        if omaths is not None:
            # Range.OMaths.BuildUp builds all equations in range.
            omaths.BuildUp()
    except Exception:
        pass


def _try_copy_as_picture_via_selection(engine, range_obj) -> bool:
    """Best-effort: Selection.CopyAsPicture tends to include floating shapes/OLE."""
    try:
        app = getattr(engine, "app", None)
        if app is None or range_obj is None:
            return False

        _force_render_range(range_obj)

        # Ensure the owning document is active before using Selection.
        try:
            doc = getattr(range_obj, "Document", None)
            if doc is not None:
                fn_act = getattr(doc, "Activate", None)
                if callable(fn_act):
                    fn_act()
        except Exception:
            pass

        # For tables, selecting the table object is more likely to include floating shapes/OLE.
        selected = False
        try:
            tables = getattr(range_obj, "Tables", None)
            if tables is not None:
                try:
                    if int(tables.Count) >= 1:
                        tables(1).Select()
                        selected = True
                except Exception:
                    selected = False
        except Exception:
            selected = False
        if not selected:
            range_obj.Select()

        sel = getattr(app, "Selection", None)
        if sel is None:
            return False
        fn = getattr(sel, "CopyAsPicture", None)
        if not callable(fn):
            return False
        fn()
        return True
    except Exception:
        return False


def copy_range_as_picture(engine, range_obj, use_copy_as_picture: bool = False):
    """将指定 Range 复制为图片到剪贴板"""
    # 为了兼容 ImageGrab 及后续 EMF 读取，这里采用“两级复制策略”:
    # 1) 优先使用 Select + Copy，通常会在剪贴板中提供标准位图格式，
    #    便于 ImageGrab 直接获取；
    # 2) 若 Select + Copy 失败，再回退到 CopyAsPicture。
    try:
        engine._runtime_guard_check()

        _force_render_range(range_obj)
        if use_copy_as_picture:
            try:
                if _try_copy_as_picture_via_selection(engine, range_obj):
                    return True
                range_obj.CopyAsPicture()
                return True
            except Exception as e_force:
                engine._logger.warning(f"⚠️ CopyAsPicture 复制 Range 失败，将回退 Select+Copy: {e_force}")

        try:
            range_obj.Select()
            selection = engine.app.Selection
            selection.Copy()
            # engine._logger.debug("📋 已通过 Select+Copy 复制 Range 到剪贴板")
            return True
        except Exception as e1:
            engine._logger.warning(f"⚠️ Select+Copy 复制 Range 失败，将回退 CopyAsPicture: {e1}")

            # 回退方案：使用 CopyAsPicture() 复制为 Metafile
            range_obj.CopyAsPicture()
            # engine._logger.debug("📋 已通过 CopyAsPicture 复制 Range 到剪贴板")
            return True
    except Exception as e2:
        engine._logger.error(f"❌ 截图失败: {e2}")
        return False


def copy_shape_to_clipboard(engine, shape_obj, use_copy_as_picture: bool = False):
    """复制 InlineShape 到剪贴板（用于普通图片）"""
    try:
        if use_copy_as_picture:
            try:
                # 尝试获取 Range 并使用 CopyAsPicture
                rng = None
                try:
                    rng = shape_obj.Range
                except Exception:
                    pass
                
                if rng:
                    # 尝试通过 Selection 方式 (往往兼容性更好)
                    if _try_copy_as_picture_via_selection(engine, rng):
                        engine._logger.debug("📋 [Force] 已通过 Select+CopyAsPicture 复制 Shape")
                        return True
                    
                    rng.CopyAsPicture()
                    engine._logger.debug("📋 [Force] 已通过 Range.CopyAsPicture 复制 Shape")
                    return True
            except Exception as e:
                engine._logger.warning(f"⚠️ CopyAsPicture 尝试失败，将回退标准复制: {e}")

        # 先选择，再复制
        shape_obj.Select()

        # 获取选中的内容并复制
        selection = engine.app.Selection
        selection.Copy()

        engine._logger.debug("📋 已复制图片到剪贴板")
        return True
    except Exception as e:
        engine._logger.error(f"❌ 复制图片失败: {e}")
        return False


def copy_shape_to_clipboard_scaled(engine, shape_obj, scale_factor: float = 1.0, use_copy_as_picture: bool = True):
    """Copy the current visible shape after a temporary display-size scale."""
    try:
        scale = float(scale_factor or 1.0)
    except Exception:
        scale = 1.0
    if scale <= 1.01:
        return copy_shape_to_clipboard(engine, shape_obj, use_copy_as_picture=use_copy_as_picture)

    original_width = None
    original_height = None
    try:
        original_width = float(getattr(shape_obj, "Width"))
    except Exception:
        original_width = None
    try:
        original_height = float(getattr(shape_obj, "Height"))
    except Exception:
        original_height = None

    changed_width = False
    changed_height = False
    try:
        if original_width and original_width > 0:
            try:
                shape_obj.Width = float(original_width * scale)
                changed_width = True
            except Exception:
                changed_width = False
        if original_height and original_height > 0:
            try:
                shape_obj.Height = float(original_height * scale)
                changed_height = True
            except Exception:
                changed_height = False
        if changed_width or changed_height:
            time.sleep(0.05)
        return copy_shape_to_clipboard(engine, shape_obj, use_copy_as_picture=use_copy_as_picture)
    finally:
        if changed_height and original_height is not None:
            try:
                shape_obj.Height = float(original_height)
            except Exception:
                pass
        if changed_width and original_width is not None:
            try:
                shape_obj.Width = float(original_width)
            except Exception:
                pass


def _ensure_jpeg_file(path: str, config: dict | None = None) -> bool:
    try:
        with Image.open(path) as img:
            fmt = getattr(img, "format", None)
            info = getattr(img, "info", {}) or {}
            dpi = info.get("dpi")
            if fmt == "JPEG":
                return True
            rgb = img.convert("RGB")
    except Exception:
        return False

    try:
        cfg = config or {}
        try:
            quality = int(cfg.get("jpeg_quality", 95))
        except Exception:
            quality = 95
        try:
            subsampling = int(cfg.get("jpeg_subsampling", 0))
        except Exception:
            subsampling = 0
        if isinstance(dpi, tuple) and len(dpi) == 2:
            rgb.save(path, quality=quality, subsampling=subsampling, dpi=dpi)
        else:
            rgb.save(path, quality=quality, subsampling=subsampling)
        return True
    except Exception:
        return False


def export_inline_shape_as_picture(engine, inline_shape, output_path: str) -> bool:
    try:
        engine._runtime_guard_check()
    except Exception:
        pass

    if not output_path:
        return False

    try:
        fn = getattr(inline_shape, "SaveAsPicture", None)
        if callable(fn):
            fn(output_path)
            return bool(_ensure_jpeg_file(output_path, (getattr(engine, "config", None) or {}).get("image_processing")))
    except Exception as e:
        try:
            engine._logger.warning(f"⚠️ InlineShape.SaveAsPicture 失败，将回退临时文档导出: {e}")
        except Exception:
            pass

    try:
        app = getattr(engine, "app", None)
        if app is None:
            return False
        
        # [Performance] Use persistent canvas
        temp_doc = engine.get_canvas_doc()
        used_canvas = True
        if not temp_doc:
            try:
                temp_doc = add_hidden_document(app, logger=getattr(engine, "_logger", None))
                used_canvas = False
            except Exception:
                return False
        else:
            try:
                temp_doc.Content.Delete()
            except Exception:
                pass

        try:
            try:
                inline_shape.Range.Copy()
            except Exception:
                try:
                    inline_shape.Select()
                    app.Selection.Copy()
                except Exception:
                    return False

            try:
                dest = temp_doc.Range(0, 0)
                dest.Paste()
            except Exception:
                return False

            time.sleep(0.1)

            try:
                inshapes = getattr(temp_doc, "InlineShapes", None)
                if inshapes is not None and inshapes.Count >= 1:
                    pic = inshapes(1)
                    fn2 = getattr(pic, "SaveAsPicture", None)
                    if callable(fn2):
                        fn2(output_path)
                        return bool(_ensure_jpeg_file(output_path, (getattr(engine, "config", None) or {}).get("image_processing")))
            except Exception:
                pass

            try:
                shapes = getattr(temp_doc, "Shapes", None)
                if shapes is not None and shapes.Count >= 1:
                    shp = shapes(1)
                    fn3 = getattr(shp, "SaveAsPicture", None)
                    if callable(fn3):
                        fn3(output_path)
                        return bool(_ensure_jpeg_file(output_path, (getattr(engine, "config", None) or {}).get("image_processing")))
            except Exception:
                pass

            return False
        finally:
            if not used_canvas:
                try:
                    temp_doc.Close(SaveChanges=0)
                except Exception:
                    pass
    except Exception:
        return False


def export_shape_as_picture(engine, shape_obj, output_path: str) -> bool:
    try:
        engine._runtime_guard_check()
    except Exception:
        pass

    if not output_path:
        return False

    try:
        fn = getattr(shape_obj, "SaveAsPicture", None)
        if callable(fn):
            fn(output_path)
            return bool(_ensure_jpeg_file(output_path, (getattr(engine, "config", None) or {}).get("image_processing")))
    except Exception as e:
        try:
            engine._logger.warning(f"⚠️ Shape.SaveAsPicture 失败，将尝试转换为 InlineShape 再导出: {e}")
        except Exception:
            pass

    try:
        app = getattr(engine, "app", None)
        if app is None:
            return False
        
        # [Performance] Use persistent canvas
        temp_doc = engine.get_canvas_doc()
        used_canvas = True
        if not temp_doc:
            try:
                temp_doc = add_hidden_document(app, logger=getattr(engine, "_logger", None))
                used_canvas = False
            except Exception:
                return False
        else:
            try:
                temp_doc.Content.Delete()
            except Exception:
                pass

        try:
            try:
                shape_obj.Select()
                app.Selection.Copy()
            except Exception:
                return False

            try:
                dest = temp_doc.Range(0, 0)
                dest.Paste()
            except Exception:
                return False

            time.sleep(0.1)

            try:
                shapes = getattr(temp_doc, "Shapes", None)
                if shapes is not None and shapes.Count >= 1:
                    shp = shapes(1)
                    fn2 = getattr(shp, "SaveAsPicture", None)
                    if callable(fn2):
                        fn2(output_path)
                        return bool(_ensure_jpeg_file(output_path, (getattr(engine, "config", None) or {}).get("image_processing")))
                    # Some Word versions expose picture Shapes without SaveAsPicture;
                    # try converting to InlineShape on the canvas doc and export again.
                    conv = getattr(shp, "ConvertToInlineShape", None)
                    if callable(conv):
                        try:
                            inl = conv()
                            fn2b = getattr(inl, "SaveAsPicture", None)
                            if callable(fn2b):
                                fn2b(output_path)
                                return bool(_ensure_jpeg_file(output_path, (getattr(engine, "config", None) or {}).get("image_processing")))
                        except Exception:
                            pass
            except Exception:
                pass

            try:
                inshapes = getattr(temp_doc, "InlineShapes", None)
                if inshapes is not None and inshapes.Count >= 1:
                    pic = inshapes(1)
                    fn3 = getattr(pic, "SaveAsPicture", None)
                    if callable(fn3):
                        fn3(output_path)
                        return bool(_ensure_jpeg_file(output_path, (getattr(engine, "config", None) or {}).get("image_processing")))
            except Exception:
                pass

            return False
        finally:
            if not used_canvas:
                try:
                    temp_doc.Close(SaveChanges=0)
                except Exception:
                    pass
    except Exception:
        return False
