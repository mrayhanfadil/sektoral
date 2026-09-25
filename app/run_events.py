"""Run events for the web app: valuation decisions as events, and stored runs to replay.

Two things live here:

- ``valuation_events(doc)``: what the Method Gates decided (Method Gates 0-5
  from the gate verdict), each step of the method chain, and the release
  status, as progress events. ``build.build`` emits them during a live run and
  ``derive`` reuses them, so a live run and a replay show the same decisions.
- ``replay(folder, ticker)``: a finished run to play back. A run recorded by
  ``research.run`` returns its own events (``source: "recorded"``). A run
  stored before events were recorded is rebuilt from its audit trace and report
  document (``source: "derived"``): the same steps in the same order, with
  estimated timing, and nothing the public trace view would not show.
"""
from __future__ import annotations

import re
from pathlib import Path

from . import gallery, outputs, progress, trace_view
from .jobs import text

GATES = ((0, "Model bisnis"), (1, "Kelayakan data"), (2, "Struktur kepemilikan"),
         (3, "Siklus & tahap operasi"), (4, "Tahap siklus hidup"), (5, "Kewajaran hasil"))

# Reader wording of each gate check (app/model_profiles.py ids).
CHECKS = {
    "0_business_model": "model bisnis menentukan metode utama",
    "1a_filing_history": "riwayat laporan keuangan",
    "1b_profitability": "profitabilitas operasi",
    "1c_capital_structure": "struktur modal",
    "1d_equity_base": "ekuitas positif",
    "2_nci": "porsi kepentingan nonpengendali",
    "3_cyclicality": "siklus dan tahap operasi",
    "4_life_cycle": "tahap siklus hidup",
    "5_upside_band": "upside dalam rentang wajar",
    "5_upside_extreme": "upside ekstrem",
    "5_downside_extreme": "downside ekstrem",
    "5_exit_multiple_in_range": "multiple keluar dalam rentang peer",
    "5_exit_multiple_out_of_range": "multiple keluar di luar rentang peer",
    "5_tv_share": "porsi nilai terminal wajar",
    "5_tv_share_high": "porsi nilai terminal tinggi",
}

RELEASE = {"production_ready": "siap produksi",
           "distributable_assumption_led": "dapat didistribusikan, berbasis asumsi analis",
           "draft_non_distributable": "draf, belum didistribusikan"}

SUBAGENTS = {"news": "Dampak berita", "interim": "Skenario interim", "earnings": "Skenario laba FY",
             "stage": "Tahap bisnis", "outyears": "Tahun lanjutan"}


def _check(ids):
    return "; ".join(CHECKS.get(i, i.split("_", 1)[-1].replace("_", " ")) for i in ids)


def gate_rows(verdict: dict | None) -> list[dict]:
    """Six rows {gate, name, verdict, ok, detail} from a model_profiles GateVerdict dict."""
    verdict = verdict if isinstance(verdict, dict) else {}

    def ids(key):
        return [str(i) for i in verdict.get(key) or [] if isinstance(i, str)]

    passed, failed, unassessed = ids("gates_passed"), ids("gates_failed"), ids("gates_unassessed")
    primary = str(verdict.get("primary") or "")
    rows = []
    for n, name in GATES:
        mine = [i for i in passed + failed + unassessed if i[:1] == str(n)]
        unknown = [i for i in unassessed if i[:1] == str(n)]
        bad = [i for i in failed if i[:1] == str(n) and i not in unassessed]
        if unknown:
            word, ok, detail = "tidak dapat dinilai", False, "data belum cukup untuk " + _check(unknown)
        elif bad:
            word, ok, detail = "gagal", False, _check(bad)
        elif mine:
            word, ok, detail = "lolos", True, _check([i for i in passed if i[:1] == str(n)])
        else:
            word, ok = "tidak berlaku", True
            detail = ("lembaga keuangan dinilai dari ekuitas; gerbang ini dilewati"
                      if primary.startswith("DDM") and 1 <= n <= 4 else "tidak dinilai untuk profil ini")
        if n == 0 and primary:
            secondary = str(verdict.get("secondary") or "")
            detail = f"metode utama {primary}" + (f", pembanding {secondary}"
                                                   if secondary and secondary != primary else "")
        rows.append({"gate": n, "name": name, "verdict": word, "ok": ok, "detail": detail})
    return rows


def _chain_rows(doc):
    exhibit = next((e for e in doc.get("exhibits") or []
                    if isinstance(e, dict) and e.get("judul") == "Rantai metode valuasi"), None)
    for row in ((exhibit or {}).get("data") or {}).get("rows") or []:
        if isinstance(row, list) and len(row) >= 3:
            yield {"method": re.sub(r"^\S+\.\s*", "", str(row[0])).replace(" (utama)", ""),
                   "decision": str(row[1]), "value": str(row[2]),
                   "reason": str(row[3]) if len(row) > 3 else ""}


def valuation_events(doc: dict) -> list[dict]:
    """Gate verdicts, method chain and release status as emit() keyword sets."""
    if not isinstance(doc, dict):
        return []
    verdict = ((doc.get("log_gate") or {}).get("release") or {}).get("gate_verdict")
    out = [dict(stage="gate", label="Gerbang metode menilai emiten", status="run", agent="gerbang",
                detail="Method Gates 0-5 memilih metode sebelum nilai dihitung")]
    if isinstance(verdict, dict):
        for row in gate_rows(verdict):
            out.append(dict(stage="gate", label=row["name"], detail=row["detail"],
                            status="ok" if row["ok"] else "warn", tool=f"gate_{row['gate']}",
                            agent="gerbang", data={"gate": row["gate"], "verdict": row["verdict"]}))
    for row in _chain_rows(doc):
        out.append(dict(stage="gate", label=row["method"][:80], detail=row["reason"],
                        tool="chain_step", agent="gerbang",
                        data={"decision": row["decision"][:40], "value": row["value"][:40]}))
    method = str(doc.get("method") or "").split(" [")[0]
    out.append(dict(stage="gate", label=f"Metode utama {method}" if method else "Rantai metode selesai",
                    status="ok", agent="gerbang"))
    meta = doc.get("meta") or {}
    status = str(meta.get("status") or "")
    published = status.startswith("distributable") or status == "production_ready"
    data = {"status": status}
    if published:
        data.update(rating=meta.get("rating"), tp=_rp(meta.get("tp")), upside=_pct(meta.get("upside_persen")))
    blockers = len((doc.get("harness") or {}).get("blockers") or [])
    out.append(dict(stage="report", label="Status rilis: " + RELEASE.get(status, status or "tidak diketahui"),
                    detail=("rating dan target harga diterbitkan" if published else
                            f"{blockers} pemeriksaan menahan rating dan target harga"),
                    status="ok" if published else "warn", tool="release", data=data))
    return out


def emit_valuation(doc: dict) -> None:
    for kwargs in valuation_events(doc):
        progress.emit(**kwargs)


def _rp(value):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    return "Rp" + f"{value:,.0f}".replace(",", ".")


def _pct(value):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    return f"{value:+.1f}%".replace(".", ",").replace("-", "−")


class _Clock:
    """Estimated run time for derived replays (model turns take seconds, tools less)."""

    def __init__(self):
        self.t = 0.0

    def after(self, seconds):
        self.t += seconds
        return self.t


def derive(audit: dict, doc: dict) -> list[dict]:
    """Events of a stored run rebuilt from its public trace view and report document."""
    view = trace_view.build(audit)
    if view is None:
        return []
    clock, events = _Clock(), []

    def add(seconds, stage, label, detail=None, **kw):
        events.append(progress.event(stage, label, detail, t=clock.after(seconds), **kw))

    analyst = view.get("analyst") or {}
    raw_analyst = audit.get("analyst") if isinstance(audit.get("analyst"), dict) else {}
    if analyst:
        changes = analyst.get("changes") or {}
        add(0.1, "memory", "Membaca memori riset",
            "belum ada riset sebelumnya" if changes.get("first_run") or not changes.get("previous_run_at")
            else f"riset terakhir {str(changes['previous_run_at'])[:10]}")
        plan = analyst.get("plan") or {}
        add(0.2, "plan", "Agent menyusun rencana riset", status="run")
        agent_plan = plan.get("source") == "agent"
        add(8.4, "plan", "Rencana siap" if agent_plan else "Rencana standar host dipakai",
            plan.get("question"), status="ok" if agent_plan else "warn")
        for i, hypothesis in enumerate(h for h in plan.get("hypotheses") or [] if h):
            add(0.1, "plan", f"Hipotesis {i + 1}", hypothesis, tool="hypothesis", data={"index": i + 1})
        for step in analyst.get("steps") or []:
            tool = step.get("tool") or "tool"
            add(3.6, "tool", f"Menjalankan {tool}", step.get("why"), status="run", tool=tool)
            if step.get("status") == "error":
                add(0.9, "tool", f"{tool}: data tidak tersedia", step.get("summary"), status="warn", tool=tool)
            else:
                add(0.9, "tool", f"{tool} selesai", step.get("summary"), tool=tool)
        signals = raw_analyst.get("signals") if isinstance(raw_analyst.get("signals"), list) else []
        flagged = sum(1 for s in signals if isinstance(s, dict) and s.get("flag"))
        add(2.4, "signals", f"{len(signals)} sinyal dihitung, {flagged} bertanda")
        synthesis = analyst.get("synthesis") or {}
        add(0.2, "synthesis", "Agent menguji hipotesis dan menulis temuan", status="run")
        agent_synthesis = synthesis.get("source") == "agent"
        add(13.5, "synthesis", "Temuan tervalidasi" if agent_synthesis else "Ringkasan host dipakai",
            synthesis.get("headline"), status="ok" if agent_synthesis else "warn")
        for h in synthesis.get("hypotheses") or []:
            if isinstance(h.get("index"), int) and h.get("verdict"):
                number = h["index"] + 1  # synthesis indexes from 0, the plan from 1
                add(0.1, "synthesis", f"H{number} {h['verdict']}", h.get("reason"), tool="verdict",
                    data={"index": number, "verdict": h["verdict"]})
        add(0.3, "memory", "Memori riset diperbarui")

    research = view.get("research") or {}
    raw_research = audit.get("research") if isinstance(audit.get("research"), dict) else {}
    add(0.4, "research", "Agent riset membaca data dan menyusun brief bersitasi", status="run")
    for endpoint in research.get("endpoints") or []:
        add(2.8, "research", f"Membaca {endpoint}", status="run", tool="cache_get", agent="riset")
        add(0.3, "research", f"{endpoint} terbaca", tool="cache_get", agent="riset")
    insights = len(research.get("insights") or [])
    ok = bool(raw_research.get("ok"))
    add(9.0, "research", "Brief riset tervalidasi" if ok else "Brief riset parsial",
        f"{insights} insight bersitasi" if insights else "tanpa insight yang lolos validasi",
        status="ok" if ok else "warn")

    news = view.get("news") or {}
    search = news.get("search") or {}
    queries = [q for q in search.get("queries") or [] if q]
    add(0.4, "news", "Mencari berita bertanggal",
        f"{len(queries)} kueri pencarian sampai {search.get('as_of') or 'tanggal laporan'}",
        status="run", agent="berita")
    failed = search.get("status") in ("failed", "unavailable")
    add(4.2, "news", "Pencarian berita gagal" if failed else
        f"{len(news.get('articles') or [])} artikel relevan, {news.get('rejected_total') or 0} ditolak",
        search.get("status"), status="warn" if failed else "ok", agent="berita")

    forecast = audit.get("forecast_assumptions") if isinstance(audit.get("forecast_assumptions"), dict) else {}
    add(0.4, "forecast", "Agent asumsi forecast membaca berita dan rilis resmi", status="run")
    if forecast.get("reused"):
        add(0.3, "forecast", "Rencana forecast dipakai ulang", "bukti sama dengan run sebelumnya")
    subagents = forecast.get("subagents") if isinstance(forecast.get("subagents"), dict) else {}
    names = [n for n in SUBAGENTS if isinstance(subagents.get(n), dict)]
    for i, name in enumerate(names):
        add(0.2 if i % 2 else 0.3, "forecast", f"Subagent {SUBAGENTS[name]}", status="run",
            agent=f"forecast.{name}")
    for i, name in enumerate(names):
        result = subagents[name]
        valid = result.get("status") == "validated"
        problems = [p for p in result.get("problems") or [] if isinstance(p, str)]
        add(0.4 if forecast.get("reused") else 24.0 if i == 0 else 6.5, "forecast",
            f"{SUBAGENTS[name]} tervalidasi" if valid else f"{SUBAGENTS[name]} ditolak validator",
            "dipakai ulang untuk bukti yang sama" if forecast.get("reused") and valid
            else (text(problems[0], 200) if problems else None),
            status="ok" if valid else "warn", agent=f"forecast.{name}")
    add(0.5, "forecast", "Asumsi forecast selesai" + (" (dipakai ulang untuk bukti yang sama)"
                                                     if forecast.get("reused") else ""),
        text(forecast.get("status"), 60))

    add(0.4, "report", "Menyusun company update dan memeriksa gate valuasi", status="run")
    for i, kwargs in enumerate(valuation_events(doc)):
        kwargs = dict(kwargs)
        stage, label = kwargs.pop("stage"), kwargs.pop("label")
        add(1.6 if i == 0 else 0.35, stage, label, kwargs.pop("detail", None), **kwargs)
    meta = doc.get("meta") or {}
    add(5.5, "report", "Company update tersusun", meta.get("status"))
    add(0.2, "done", "Selesai")
    return events


def replay(folder, ticker: str) -> dict | None:
    """{ticker, name, source, events, report} for a stored run, or None."""
    t = str(ticker).strip().upper()
    if not gallery.TICKER.fullmatch(t):
        return None
    folder = Path(folder)
    doc = outputs.load(outputs.REPORT, folder, t)
    audit = outputs.load(outputs.TRACE, folder, t)
    if not isinstance(doc, dict) or not isinstance(audit, dict):
        return None
    recorded = outputs.load(outputs.EVENTS, folder, t)
    events = progress.public(recorded) if isinstance(recorded, list) and recorded else []
    source = "recorded" if events else "derived"
    if not events:
        events = derive(audit, doc)
    meta = doc.get("meta") or {}
    return {"ticker": t, "name": text(meta.get("emiten"), 120), "source": source,
            "events": events, "report": gallery.summary(doc, folder, t)}
