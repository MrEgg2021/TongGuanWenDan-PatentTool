from __future__ import annotations

import time

from core.logging_utils import logger

from .write_commands import MarkerNormalizationApplyReport


def _range_with_retry(doc, start: int, end: int, retries: int = 2, retry_delay: float = 0.4):
    last_exc: Exception | None = None
    for attempt in range(0, retries + 1):
        try:
            return doc.Range(int(start), int(end))
        except Exception as exc:
            last_exc = exc
            if attempt >= retries:
                break
            time.sleep(max(0.0, float(retry_delay)))
    raise RuntimeError(str(last_exc or "Range 读取失败"))


def _revision_count(doc) -> int:
    try:
        revs = getattr(doc, "Revisions", None)
        if revs is None:
            return 0
        return int(getattr(revs, "Count", 0) or 0)
    except Exception:
        return 0


def _ensure_revision_view_visible(doc) -> None:
    try:
        app = getattr(doc, "Application", None)
        wnd = getattr(app, "ActiveWindow", None) if app is not None else None
        if wnd is None:
            return
        try:
            wnd.View.ShowRevisionsAndComments = True
        except Exception:
            pass
        try:
            # wdRevisionsViewFinal = 0
            wnd.View.RevisionsView = 0
        except Exception:
            pass
    except Exception:
        return


def apply_write_commands(
    doc,
    *,
    commands,
    enforce_track_revisions: bool = True,
    atomic_commit: bool = True,
) -> MarkerNormalizationApplyReport:
    planned = len(list(commands or []))
    applied = 0
    inserted = 0
    replaced = 0
    errors: list[str] = []
    warnings: list[str] = []
    failed_cmd_ids: list[str] = []
    undo_started = False
    undo_record = None
    revisions_before = 0
    revisions_after = 0

    if planned <= 0:
        return MarkerNormalizationApplyReport(
            committed=True,
            planned_count=0,
            applied_count=0,
            inserted_count=0,
            replaced_count=0,
            failed_count=0,
            failed_cmd_ids=[],
            errors=[],
            warnings=[],
        )

    def _end_undo_record() -> None:
        nonlocal undo_started
        if (not undo_started) or undo_record is None:
            return
        try:
            undo_record.EndCustomRecord()
        except Exception:
            pass
        undo_started = False

    try:
        if enforce_track_revisions:
            try:
                doc.TrackRevisions = True
            except Exception as exc:
                raise RuntimeError(f"无法开启修订模式：{exc}") from exc
            try:
                track_on = bool(getattr(doc, "TrackRevisions", False))
            except Exception:
                track_on = False
            logger.debug("[formal_review][write_executor] track_on_check=%s", track_on)
            if not track_on:
                raise RuntimeError("修订模式未生效，已阻断提交。")
            revisions_before = _revision_count(doc)
            logger.debug("[formal_review][write_executor] revision_count_before=%s", int(revisions_before))
        try:
            app = doc.Application
            undo_record = getattr(app, "UndoRecord", None)
            if undo_record is not None:
                undo_record.StartCustomRecord("形式审查修订应用")
                undo_started = True
        except Exception:
            undo_record = None

        if bool(atomic_commit):
            for cmd in list(commands or []):
                rng = _range_with_retry(doc, int(cmd.word_start), int(cmd.word_end))
                current = str(getattr(rng, "Text", "") or "")
                expected = str(getattr(cmd, "expected_old_fragment", "") or "")
                if current != expected:
                    raise RuntimeError(
                        f"{cmd.cmd_id} 预期片段不一致，执行中止。expected={expected!r}, actual={current!r}"
                    )
                rng.Text = str(getattr(cmd, "replacement_text", "") or "")
                applied += 1
                if str(getattr(cmd, "action_kind", "")) == "insert_after_name":
                    inserted += 1
                else:
                    replaced += 1
        else:
            for cmd in list(commands or []):
                cmd_id = str(getattr(cmd, "cmd_id", "") or "")
                try:
                    rng = _range_with_retry(doc, int(cmd.word_start), int(cmd.word_end))
                    current = str(getattr(rng, "Text", "") or "")
                    expected = str(getattr(cmd, "expected_old_fragment", "") or "")
                    if current != expected:
                        raise RuntimeError(f"预期片段不一致。expected={expected!r}, actual={current!r}")
                    rng.Text = str(getattr(cmd, "replacement_text", "") or "")
                    applied += 1
                    if str(getattr(cmd, "action_kind", "")) == "insert_after_name":
                        inserted += 1
                    else:
                        replaced += 1
                except Exception as cmd_exc:
                    failed_cmd_ids.append(cmd_id)
                    errors.append(f"{cmd_id}: {cmd_exc}")
                    logger.warning(
                        "[formal_review][write_executor] partial_cmd_failed cmd_id=%s error=%s",
                        cmd_id,
                        cmd_exc,
                    )
                    continue
        if enforce_track_revisions:
            revisions_after = _revision_count(doc)
            logger.debug("[formal_review][write_executor] revision_count_after=%s", int(revisions_after))
            if bool(atomic_commit):
                if int(revisions_after) <= int(revisions_before):
                    raise RuntimeError("未检测到修订痕迹增长，已阻断提交并回滚。")
            elif int(applied) > 0 and int(revisions_after) <= int(revisions_before):
                raise RuntimeError("未检测到修订痕迹增长，已阻断提交。")
            if int(applied) > 0:
                _ensure_revision_view_visible(doc)
    except Exception as exc:
        errors.append(str(exc))
        if bool(atomic_commit) and undo_started:
            _end_undo_record()
            try:
                doc.Application.Undo()
                warnings.append("执行失败，已尝试撤销本次统一标号。")
                logger.warning("[formal_review][write_executor] rollback_result=success")
            except Exception as rollback_exc:
                warnings.append(f"执行失败且撤销失败：{rollback_exc}")
                logger.warning("[formal_review][write_executor] rollback_result=failed error=%s", rollback_exc)
        return MarkerNormalizationApplyReport(
            committed=False,
            planned_count=planned,
            applied_count=applied,
            inserted_count=inserted,
            replaced_count=replaced,
            failed_count=int(len(failed_cmd_ids)),
            failed_cmd_ids=list(failed_cmd_ids),
            errors=errors,
            warnings=warnings,
        )
    finally:
        _end_undo_record()

    if not bool(atomic_commit):
        committed = int(applied) > 0 and (not enforce_track_revisions or int(revisions_after) > int(revisions_before))
        return MarkerNormalizationApplyReport(
            committed=bool(committed),
            planned_count=planned,
            applied_count=applied,
            inserted_count=inserted,
            replaced_count=replaced,
            failed_count=int(len(failed_cmd_ids)),
            failed_cmd_ids=list(failed_cmd_ids),
            errors=errors,
            warnings=warnings,
        )

    return MarkerNormalizationApplyReport(
        committed=True,
        planned_count=planned,
        applied_count=applied,
        inserted_count=inserted,
        replaced_count=replaced,
        failed_count=int(len(failed_cmd_ids)),
        failed_cmd_ids=list(failed_cmd_ids),
        errors=errors,
        warnings=warnings,
    )
