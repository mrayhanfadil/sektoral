"""Progress events for a research run.

The web server installs a callback for the worker thread running a job; the
pipeline calls ``emit`` at each step. Outside a job (CLI, tests) ``emit`` is a
no-op, so pipeline code never needs to know who is listening.
``research.run`` also records its own events (``recording``) and stores them
with the run outputs, so a finished run can be played back in the web app.

An event is ``{stage, label, status, t}`` plus optional ``detail`` (why a step
started or what it found), ``tool`` (the tool or kind of step, e.g.
``find_peers``, ``cache_get``, ``gate_3``), ``agent`` (the emitter when the
stage does not name it, e.g. ``riset`` or ``forecast.news``) and ``data`` (a
few short structured fields such as a gate verdict; strings, except the raw
numbers in ``NUMBERS``). ``label_en`` and ``detail_en`` are the English twins
the web app shows in English (#34): given by the emitter (an agent's own
English), else filled in for host-written text (``app.host_lang``), else absent.
"""
from __future__ import annotations

import contextvars
import math
import re
import time
from contextlib import contextmanager

_SINK = contextvars.ContextVar("sektoral_progress_sink", default=None)
STAGES = ("memory", "plan", "tool", "signals", "synthesis", "research", "news",
          "forecast", "gate", "report", "done")
STATUSES = ("ok", "warn", "error", "run")
_AGENT = re.compile(r"^[a-z]{2,12}(\.[a-z_]{2,20})?$")
_KEY = re.compile(r"^[a-z_]{1,20}$")
# data keys kept as numbers (the web formats them); every other value is a short string.
NUMBERS = frozenset({"tp_value", "upside_pct"})


def _finite(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _english(given, text):
    """An English twin: the one given, else the host text's own (app.host_lang)."""
    if isinstance(given, str) and given.strip():
        return given
    from . import host_lang  # imports the analyst's signal tables
    return host_lang.english(str(text))


def event(stage: str, label: str, detail=None, *, status: str = "ok", tool=None,
          agent=None, data=None, t: float = 0.0, label_en=None, detail_en=None) -> dict:
    """One bounded, typed event; unknown values fall back or are dropped."""
    out = {"stage": stage if stage in STAGES else "research",
           "label": str(label)[:160], "status": status if status in STATUSES else "ok",
           "t": round(float(t), 1)}
    english = _english(label_en, label)
    if english:
        out["label_en"] = str(english)[:160]
    if detail:
        out["detail"] = str(detail)[:400]
        english = _english(detail_en, detail)
        if english:
            out["detail_en"] = str(english)[:400]
    if tool:
        out["tool"] = str(tool)[:40]
    if agent and _AGENT.fullmatch(str(agent)):
        out["agent"] = str(agent)
    if isinstance(data, dict):
        clean = {k: v if k in NUMBERS else str(v)[:120] for k, v in list(data.items())[:8]
                 if isinstance(k, str) and _KEY.fullmatch(k) and v is not None and str(v) != ""
                 and (_finite(v) or k not in NUMBERS)}
        if clean:
            out["data"] = clean
    return out


def emit(stage: str, label: str, detail: str | None = None, *,
         status: str = "ok", tool: str | None = None, agent: str | None = None,
         data: dict | None = None, label_en: str | None = None,
         detail_en: str | None = None) -> None:
    sink = _SINK.get()
    if sink is None:
        return
    callback, started = sink
    try:
        callback(event(stage, label, detail, status=status, tool=tool, agent=agent, data=data,
                       t=time.monotonic() - started, label_en=label_en, detail_en=detail_en))
    except Exception:  # a listener must never break the research run
        pass


@contextmanager
def capture(callback):
    token = _SINK.set((callback, time.monotonic()))
    try:
        yield
    finally:
        _SINK.reset(token)


@contextmanager
def recording(limit: int = 600):
    """Keep this run's events in a list, still passing each to an outer listener."""
    events: list[dict] = []
    outer = _SINK.get()
    started = outer[1] if outer else time.monotonic()

    def keep(item):
        if len(events) < limit:
            events.append(item)
        if outer:
            outer[0](item)

    token = _SINK.set((keep, started))
    try:
        yield events
    finally:
        _SINK.reset(token)


def public(events) -> list[dict]:
    """Stored events re-validated for the browser (they are read back from the database)."""
    out = []
    for item in events if isinstance(events, list) else []:
        if not isinstance(item, dict) or not item.get("label"):
            continue
        t = item.get("t")
        out.append(event(str(item.get("stage")), str(item["label"]), item.get("detail"),
                         status=str(item.get("status")), tool=item.get("tool"),
                         agent=item.get("agent"), data=item.get("data"),
                         t=t if isinstance(t, (int, float)) and not isinstance(t, bool) else 0.0,
                         label_en=item.get("label_en"), detail_en=item.get("detail_en")))
    return out[:600]
