"""Progress events for a research run.

The web server installs a callback for the worker thread running a job; the
pipeline calls ``emit`` at each step. Outside a job (CLI, tests) ``emit`` is a
no-op, so pipeline code never needs to know who is listening.
"""
from __future__ import annotations

import contextvars
import time
from contextlib import contextmanager

_SINK = contextvars.ContextVar("sektoral_progress_sink", default=None)
STAGES = ("memory", "plan", "tool", "signals", "synthesis", "research",
          "forecast", "report", "done")


def emit(stage: str, label: str, detail: str | None = None, *,
         status: str = "ok", tool: str | None = None) -> None:
    sink = _SINK.get()
    if sink is None:
        return
    callback, started = sink
    event = {"stage": stage if stage in STAGES else "research",
             "label": str(label)[:160], "status": status if status in ("ok", "warn", "error", "run") else "ok",
             "t": round(time.monotonic() - started, 1)}
    if detail:
        event["detail"] = str(detail)[:280]
    if tool:
        event["tool"] = str(tool)[:40]
    try:
        callback(event)
    except Exception:  # a listener must never break the research run
        pass


@contextmanager
def capture(callback):
    token = _SINK.set((callback, time.monotonic()))
    try:
        yield
    finally:
        _SINK.reset(token)
