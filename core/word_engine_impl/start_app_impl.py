from __future__ import annotations

from .start_app_steps.dispatch import start_app_dispatch_flow
from .start_app_steps.ownership import record_start_app_ownership
from .start_app_steps.post_setup import run_start_app_post_setup
from .start_app_steps.preflight import run_start_app_preflight


def start_app(engine, append_word_startup_faq):
    run_start_app_preflight(engine)
    result = start_app_dispatch_flow(engine, append_word_startup_faq)
    run_start_app_post_setup(engine)
    record_start_app_ownership(engine)
    return result
