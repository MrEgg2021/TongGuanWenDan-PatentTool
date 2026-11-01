import os


def _word_compatibility_mode_current() -> int:
    try:
        from win32com.client import constants  # type: ignore

        value = getattr(constants, "wdWord2013", None)
        if value is not None:
            return int(value)
    except Exception:
        pass
    return 15


def _word_version_float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_get_word_version(engine) -> float | None:
    version = _word_version_float(getattr(engine, "version", None))
    if version is not None:
        return version
    try:
        app = getattr(engine, "app", None)
        if app is not None:
            return _word_version_float(getattr(app, "Version", None))
    except Exception:
        return None
    return None


def _target_compatibility_mode_for_word_version(word_version: object) -> int:
    version = _word_version_float(word_version)
    if version is None:
        return _word_compatibility_mode_current()
    if version >= 15.0:
        return 15
    if version >= 14.0:
        return 14
    if version >= 12.0:
        return 12
    return _word_compatibility_mode_current()


def _target_compatibility_mode(engine) -> int:
    return _target_compatibility_mode_for_word_version(_safe_get_word_version(engine))


def _safe_get_compatibility_mode(doc) -> object:
    try:
        return getattr(doc, "CompatibilityMode", None)
    except Exception:
        return None


def _safe_document_media_inventory(doc) -> dict[str, int]:
    inventory: dict[str, int] = {}
    for key, attr_name in (
        ("inline_shapes", "InlineShapes"),
        ("floating_shapes", "Shapes"),
    ):
        try:
            collection = getattr(doc, attr_name)
            inventory[key] = int(getattr(collection, "Count", 0) or 0)
        except Exception:
            inventory[key] = 0
    return inventory


def _requires_modern_compat_conversion(
    source_suffix: str,
    compatibility_mode: object,
    target_compatibility_mode: int | None = None,
) -> bool:
    suffix = str(source_suffix or "").lower()
    return suffix == ".doc"


def _compat_conversion_failure_message(source_suffix: str) -> str:
    suffix = str(source_suffix or "").lower()
    if suffix == ".doc":
        return "该 DOC 无法后台转换为新格式，请先用 Word 手动另存为 DOCX 后重试。"
    return "该 Word 文档无法后台转换为新格式，请先用 Word 手动另存为新的 DOCX 后重试。"


def _open_temp_docx_for_processing(engine, temp_path: str):
    return engine.app.Documents.Open(
        FileName=temp_path,
        ConfirmConversions=False,
        ReadOnly=False,
        AddToRecentFiles=False,
        Revert=False,
        Visible=False,
        OpenAndRepair=False,
        NoEncodingDialog=True,
    )


def _apply_configured_zoom(engine) -> None:
    try:
        zoom_percent = engine.config.get("zoom_percentage")
        if zoom_percent:
            win = engine.app.ActiveWindow
            if win is not None:
                win.View.Zoom.Percentage = zoom_percent
                engine._logger.info(f"🔎 Word 视图缩放已设置为 {zoom_percent}%")
    except Exception as e:
        engine._logger.warning(f"⚠️ 调整 Word 视图缩放失败: {e}")


def _save_legacy_doc_as_modern_docx(
    engine,
    source_path: str,
    temp_path: str,
    *,
    source_suffix: str = ".doc",
    target_compatibility_mode: int | None = None,
) -> str:
    """Convert legacy .doc documents before parser access."""
    doc = getattr(engine, "doc", None)
    if doc is None:
        raise RuntimeError("Word document is not open")

    app = getattr(engine, "app", None)
    if app is None:
        raise RuntimeError("Word application is not available")

    logger = getattr(engine, "_logger", None)
    before_mode = _safe_get_compatibility_mode(doc)
    source_media_inventory = _safe_document_media_inventory(doc)
    if logger is not None:
        try:
            logger.info(
                "[DOC_COMPAT_CONVERT] begin source=%s suffix=%s compatibility_before=%s temp=%s",
                source_path,
                source_suffix,
                before_mode,
                temp_path,
            )
        except Exception:
            pass

    old_alerts = None
    had_alerts = False
    try:
        old_alerts = getattr(app, "DisplayAlerts")
        had_alerts = True
        app.DisplayAlerts = 0
    except Exception:
        had_alerts = False

    try:
        try:
            doc.Convert()
        except Exception as first_exc:
            if logger is not None:
                try:
                    logger.warning("[DOC_COMPAT_CONVERT] readonly_convert_failed retrying_readwrite error=%s", first_exc)
                except Exception:
                    pass
            try:
                doc.Close(SaveChanges=False)
            except Exception:
                pass
            doc = app.Documents.Open(
                FileName=source_path,
                ConfirmConversions=False,
                ReadOnly=False,
                AddToRecentFiles=False,
                Revert=False,
                Visible=False,
                OpenAndRepair=False,
                NoEncodingDialog=True,
            )
            engine.doc = doc
            try:
                doc.Convert()
            except Exception as second_exc:
                try:
                    doc.Close(SaveChanges=False)
                except Exception:
                    pass
                raise RuntimeError(_compat_conversion_failure_message(source_suffix)) from second_exc

        after_convert_mode = _safe_get_compatibility_mode(doc)
        compat_mode = int(target_compatibility_mode or _target_compatibility_mode(engine))
        try:
            doc.SaveAs2(FileName=temp_path, FileFormat=12, CompatibilityMode=compat_mode)
        except Exception as saveas2_exc:
            try:
                doc.Close(SaveChanges=False)
            except Exception:
                pass
            raise RuntimeError(_compat_conversion_failure_message(source_suffix)) from saveas2_exc

        if logger is not None:
            try:
                logger.info(
                    "[DOC_COMPAT_CONVERT] saved compatibility_after_convert=%s target_compatibility=%s temp=%s",
                    after_convert_mode,
                    compat_mode,
                    temp_path,
                )
            except Exception:
                pass

        try:
            doc.Close(SaveChanges=False)
        except Exception:
            pass
        engine.doc = _open_temp_docx_for_processing(engine, temp_path)
        reopened_media_inventory = _safe_document_media_inventory(engine.doc)
        engine._legacy_drawings_inventory = {
            "source": source_media_inventory,
            "reopened": reopened_media_inventory,
            "source_path": source_path,
            "reopened_path": temp_path,
        }
        if logger is not None:
            try:
                logger.info(
                    "[DOC_COMPAT_CONVERT] reopened temp=%s compatibility_reopened=%s source_media=%s reopened_media=%s",
                    temp_path,
                    _safe_get_compatibility_mode(engine.doc),
                    source_media_inventory,
                    reopened_media_inventory,
                )
                if source_media_inventory != reopened_media_inventory:
                    logger.warning(
                        "[LEGACY_DRAWINGS_INVENTORY_CHANGED] source=%s reopened=%s",
                        source_media_inventory,
                        reopened_media_inventory,
                    )
            except Exception:
                pass
        return temp_path
    finally:
        if had_alerts:
            try:
                app.DisplayAlerts = old_alerts
            except Exception:
                pass


def open_doc(engine, file_path):
    """
    打开文档并执行预处理 (Unlink, AcceptRevisions)
    .doc 会转为临时 DOCX；.docx 保持已打开文档供解析
    """
    if not engine.app:
        engine.start_app()

    engine._runtime_guard_check()

    abs_path = os.path.abspath(file_path)
    engine._legacy_drawings_inventory = None
    engine._logger.info(f"📂 打开文档: {abs_path}")

    try:
        # 以只读方式打开源文件
        engine.doc = engine.app.Documents.Open(
            FileName=abs_path,
            ConfirmConversions=False,
            ReadOnly=True,
            AddToRecentFiles=False,
            Revert=False,
            Visible=False,
            OpenAndRepair=False,
            NoEncodingDialog=True,
        )

        # 0. 硬校验：拒绝包含批注或未接受修订的文档
        try:
            rev_count = engine.doc.Revisions.Count
            comment_count = engine.doc.Comments.Count
        except Exception as e:
            engine._logger.error(f"❌ 检查批注/修订状态失败: {e}")
            raise

        if rev_count > 0 or comment_count > 0:
            engine._logger.error(
                f"❌ 文档包含批注或未接受的修订 (Revisions={rev_count}, Comments={comment_count})，"
                "本工具只接受已删除所有批注并接受全部修订的干净 DOCX，请在 Word 中清理后重试。"
            )
            raise RuntimeError("Document contains comments or tracked changes")

        # 1. 清除域代码 (转静态公式)
        engine._logger.info("⚡ 执行 Unlink Fields (跳过 OLE/Embed 对象)...")
        # 从后向前遍历，防止索引错位
        # wdFieldEmbed = 58, wdFieldLink = 56 (保留链接对象)
        try:
            fields_count = engine.doc.Fields.Count
            for i in range(fields_count, 0, -1):
                fld = engine.doc.Fields(i)
                # 仅 Unlink 非嵌入式对象
                if fld.Type != 58:
                    fld.Unlink()
        except Exception as e:
            engine._logger.warning(f"⚠️ Unlink Fields 过程中遇到错误: {e}")

        if rev_count > 0:
            engine._logger.info("📝 接受所有修订...")
            accept_ok = False
            last_err = None
            try:
                if hasattr(engine.doc, "AcceptAllRevisions"):
                    engine.doc.AcceptAllRevisions()
                    accept_ok = True
                    engine._logger.info("[ACCEPT_ALL] method=AcceptAllRevisions ok=True")
            except Exception as e:
                last_err = e
                engine._logger.warning(f"[ACCEPT_ALL] method=AcceptAllRevisions ok=False error={e}")
            if not accept_ok:
                try:
                    engine.doc.Revisions.AcceptAll()
                    accept_ok = True
                    engine._logger.info("[ACCEPT_ALL] method=Revisions.AcceptAll ok=True")
                except Exception as e:
                    last_err = e
                    engine._logger.error(f"[ACCEPT_ALL] method=Revisions.AcceptAll ok=False error={e}")
            if not accept_ok and last_err is not None:
                raise last_err
        else:
            engine._logger.info("📝 无修订，跳过 AcceptAll")

        # 3. 另存为临时文件
        temp_dir = os.path.abspath(engine.config.get("temp_dir", "temp_processing"))
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)

        temp_path = os.path.join(temp_dir, "temp_clean.docx")
        source_suffix = os.path.splitext(abs_path)[1].lower()
        compatibility_mode = _safe_get_compatibility_mode(engine.doc)
        target_compatibility_mode = _target_compatibility_mode(engine)
        try:
            engine._logger.info(
                "[DOC_PREPROCESS] source_suffix=%s compatibility_mode=%s target_compatibility_mode=%s word_version=%s",
                source_suffix,
                compatibility_mode,
                target_compatibility_mode,
                _safe_get_word_version(engine),
            )
        except Exception:
            pass
        if _requires_modern_compat_conversion(
            source_suffix,
            compatibility_mode,
            target_compatibility_mode,
        ):
            _save_legacy_doc_as_modern_docx(
                engine,
                abs_path,
                temp_path,
                source_suffix=source_suffix,
                target_compatibility_mode=target_compatibility_mode,
            )
            engine._logger.info(f"💾 已另存为预处理文件: {temp_path}")
        else:
            if source_suffix == ".docx":
                try:
                    engine._logger.info(
                        "[DOC_PREPROCESS] modern_docx_keep_open source=%s compatibility_mode=%s",
                        abs_path,
                        compatibility_mode,
                    )
                except Exception:
                    pass
                _apply_configured_zoom(engine)
                return

            # wdFormatXMLDocument = 12 (.docx)
            try:
                engine.doc.SaveAs2(FileName=temp_path, FileFormat=12)
            except Exception as e_save2:
                # 向下兼容 Word 2007：若 SaveAs2 不可用，则回退到 SaveAs
                engine._logger.warning(f"⚠️ SaveAs2 失败，将尝试回退 SaveAs: {e_save2}")
                try:
                    engine.doc.SaveAs(FileName=temp_path, FileFormat=12)
                except Exception as e_save:
                    engine._logger.error(f"❌ SaveAs 回退也失败: {e_save}")
                    raise
            engine._logger.info(f"💾 已另存为预处理文件: {temp_path}")

        _apply_configured_zoom(engine)

        # SaveAs2 后 engine.doc 已经指向新文件了，无需重新打开

    except Exception as e:
        engine._logger.error(f"❌ 文档预处理失败: {e}")
        engine.close_doc()
        raise


def open_doc_for_review(engine, file_path):
    """
    形式审查专用：只读打开文档，不做“批注/修订拒绝”与 SaveAs 预处理。
    该入口允许读取本身已包含批注或修订的文档。
    """
    if not engine.app:
        engine.start_app()

    engine._runtime_guard_check()

    abs_path = os.path.abspath(file_path)
    engine._logger.info(f"📂 [FORMAL_REVIEW] 打开文档(只读): {abs_path}")

    try:
        engine.doc = engine.app.Documents.Open(
            FileName=abs_path,
            ConfirmConversions=False,
            ReadOnly=True,
            AddToRecentFiles=False,
            Revert=False,
            Visible=False,
            OpenAndRepair=False,
            NoEncodingDialog=True,
        )

        try:
            zoom_percent = engine.config.get("zoom_percentage")
            if zoom_percent:
                win = engine.app.ActiveWindow
                if win is not None:
                    win.View.Zoom.Percentage = zoom_percent
        except Exception:
            pass
    except Exception as e:
        engine._logger.error(f"❌ [FORMAL_REVIEW] 文档打开失败: {e}")
        engine.close_doc()
        raise
