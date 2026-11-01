def on_tgd_request_manual_entry(window) -> None:
    switch_fn = getattr(window, "_tgd_dm_show_fact_manager", None)
    if callable(switch_fn):
        try:
            switch_fn()
            return
        except Exception:
            pass

    try:
        from gui.dialog_utils import show_blocking_alert_modal

        show_blocking_alert_modal(
            window,
            "提示",
            "请从『数据管理』页面进入『常用信息管理』。",
            primary_text="关闭",
            secondary_text="关闭",
        )
    except Exception:
        pass
