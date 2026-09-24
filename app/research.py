"""One-command Sectors-data research run: agent, validation, report, audit trace."""
from __future__ import annotations

import argparse
import html
import json
from datetime import date
from pathlib import Path

from . import build, intake, research_context, ui
from .progress import emit

_TRACE_CSS = (
    "*{box-sizing:border-box}body{margin:0;font:16px/1.6 var(--font);background:var(--canvas);"
    "color:var(--ink)}main{max-width:920px;margin:auto;padding:32px 20px 56px}"
    "header{background:var(--surface);border:1px solid var(--rule);border-top:4px solid var(--blue);"
    "border-radius:var(--radius);padding:24px}header h1{margin:4px 0 10px;font-size:28px}"
    ".eyebrow{color:var(--blue);font-size:12px;font-weight:700;letter-spacing:.12em;text-transform:uppercase}"
    ".meta{display:flex;flex-wrap:wrap;gap:8px}.meta span{background:var(--blue-50);color:var(--blue);"
    "border-radius:999px;padding:2px 10px;font-size:13px;font-weight:700}"
    "h2{margin:32px 0 10px;font-size:20px}h3{margin:0 0 8px;font-size:17px}"
    ".card{background:var(--surface);border:1px solid var(--rule);border-radius:var(--radius);"
    "padding:18px 20px;margin:12px 0}.muted{color:var(--ink-soft)}"
    ".chip{display:inline-block;background:var(--blue-50);color:var(--blue);padding:3px 9px;margin:3px;"
    "border-radius:6px;font:13px var(--mono)}a{color:var(--blue);font-weight:700}"
    ".btn{display:inline-block;margin-top:16px;background:var(--blue);color:#fff;text-decoration:none;"
    "padding:10px 16px;border-radius:var(--radius-sm)}.btn:hover{background:var(--blue-hover)}"
    "small{color:var(--ink-soft)}ul{padding-left:20px}"
)


_ORIGIN = {"agent": "dipilih agent sesuai rencana", "agent_adaptive": "dipilih agent di luar rencana",
           "host": "dijalankan host (langkah rencana yang belum dieksekusi)"}


def _analyst_html(intel, esc):
    """Plan, tool calls, signals and conclusions of the planning analyst agent."""
    if not isinstance(intel, dict) or not intel.get("plan"):
        problems = "; ".join((intel or {}).get("problems") or []) or "tidak dijalankan"
        return [f"<h2>Agent analis</h2><div class='card muted'>{esc(problems)}</div>"]
    plan, synthesis = intel["plan"], intel.get("synthesis") or {}
    by_id = {s.get("id"): s for s in intel.get("signals") or []}
    parts = ["<h2>Rencana agent analis</h2><div class='card'>",
             f"<p><strong>{esc(plan.get('question'))}</strong></p><ol>"]
    verdicts = {v.get("index"): v for v in synthesis.get("hypotheses") or [] if isinstance(v, dict)}
    for index, hypothesis in enumerate(plan.get("hypotheses") or []):
        verdict = verdicts.get(index) or {}
        parts.append(f"<li>{esc(hypothesis)}<br><small>Hasil: <b>{esc(verdict.get('verdict') or 'belum dinilai')}</b>"
                     f" — {esc(verdict.get('reason'))}</small></li>")
    parts.append(f"</ol><small>Sumber rencana: {esc(plan.get('source'))}</small></div>")
    parts.append("<h2>Langkah dan tool yang dipanggil</h2><div class='card'><ol>")
    for step in intel.get("steps") or []:
        parts.append(f"<li><b>{esc(step.get('tool'))}</b> — {esc(step.get('summary'))}<br><small>"
                     f"{esc(_ORIGIN.get(step.get('origin'), step.get('origin')))}; alasan: "
                     f"{esc(step.get('why'))}</small></li>")
    parts.append("</ol></div><h2>Sinyal</h2><div class='card'><ul>")
    for signal in intel.get("signals") or []:
        extra = " · ".join(esc(x) for x in (signal.get("note"), signal.get("period"),
                                              signal.get("flag")) if x)
        parts.append(f"<li>{esc(signal.get('label'))}: <b>{esc(signal.get('display'))}</b>"
                     f" <small>{extra} · {esc(signal.get('source'))}</small></li>")
    parts.append("</ul></div>")
    web = (intel.get("web_news") or {}).get("items") or []
    if web:
        parts.append("<h2>Konteks berita web (Tavily)</h2><div class='card'><p class='muted'>"
                     f"Jendela {esc((intel.get('web_news') or {}).get('window'))}. Hanya konteks naratif, "
                     "bukan data Sectors.</p><ul>")
        parts.extend(f"<li><a href='{esc(item.get('url'))}' rel='noopener noreferrer'>{esc(item.get('title'))}</a>"
                     f" <small>{esc(item.get('date'))} · {esc(item.get('domain'))}</small></li>"
                     for item in web if str(item.get("url") or "").startswith(("http://", "https://")))
        parts.append("</ul></div>")
    parts.append("<h2>Temuan agent analis</h2>")
    parts.append(f"<div class='card'><strong>{esc(synthesis.get('headline'))}</strong><br>"
                 f"<small>Sumber: {esc(synthesis.get('source'))}</small></div>")
    for finding in synthesis.get("findings") or []:
        cited = ", ".join(f"{by_id[i]['label']} {by_id[i]['display']}" for i in
                          finding.get("signal_ids") or [] if i in by_id)
        parts.append(f"<section class='card'><h3>{esc(finding.get('title'))}</h3>"
                     f"<p>{esc(finding.get('interpretation'))}</p><p class='muted'><strong>Batas bukti.</strong> "
                     f"{esc(finding.get('caveat'))}</p><small>Sinyal: {esc(cited)}</small></section>")
    return parts


def _trace_html(ticker, research, report_name, forecast_assumptions=None,
                news_deepdive=None, analyst=None):
    """A small, readable audit view for the analyst and the judging demo."""
    brief = research.get("document") if isinstance(research, dict) else None
    brief = brief if isinstance(brief, dict) else {}
    trace = brief.get("agent_trace") or research.get("agent_trace") or {}
    endpoints = trace.get("selected_cache_endpoints") or []
    insights = brief.get("insights") or []
    esc = lambda value: html.escape(str(value or ""))
    short = lambda value: esc(str(value)[:180] + ("…" if len(str(value)) > 180 else ""))
    parts = [
        "<!doctype html><html lang='id'><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width,initial-scale=1'>",
        f"<title>{esc(ticker)} | Jejak riset Sektoral</title>",
        f"<style>{ui.TOKENS}{_TRACE_CSS}</style><main>",
        f"<header><div class='eyebrow'>Jejak agent</div><h1>Riset {esc(ticker)}</h1><div class='meta'>"
        f"<span>Data: Sectors</span><span>As-of {esc(brief.get('as_of'))}</span>"
        f"<span>Status {esc(brief.get('status'))}</span></div></header>",
        f"<p><a class='btn' href='{esc(report_name)}'>Buka company update</a></p>",
        *_analyst_html(analyst, esc),
        "<h2>Ringkasan agent riset</h2>",
        f"<div class='card'>{esc(brief.get('summary') or research.get('error') or 'Belum ada briefing tervalidasi.')}</div>",
        "<h2>Endpoint data Sectors yang dibaca</h2><div class='card'>",
    ]
    parts.extend(f"<span class='chip'>{esc(endpoint)}</span>" for endpoint in endpoints)
    if not endpoints:
        parts.append("<span class='muted'>Tidak ada endpoint tercatat.</span>")
    parts.append("</div><h2>Temuan dan hubungan sebab-akibat</h2>")
    for insight in insights:
        if not isinstance(insight, dict):
            continue
        parts.append(f"<section class='card'><h3>{esc(insight.get('title') or 'Temuan')}</h3>")
        parts.append(f"<p><strong>Observasi.</strong> {esc(insight.get('observation'))}</p>")
        parts.append(f"<p><strong>Implikasi.</strong> {esc(insight.get('implication'))}</p>")
        parts.append(f"<p><strong>Batas bukti.</strong> {esc(insight.get('caveat'))}</p><ul>")
        for citation in insight.get("citations") or []:
            if not isinstance(citation, dict):
                continue
            parts.append("<li><small>" + esc(citation.get("endpoint")) + " · " +
                         esc(citation.get("field_path")) + " = " +
                         short(citation.get("value")) + "</small></li>")
        parts.append("</ul></section>")
    if not insights:
        parts.append("<div class='card muted'>Belum ada temuan yang lolos validasi sitasi.</div>")
    forecast_assumptions = forecast_assumptions or {}
    parts.append("<h2>Asumsi forecast oleh agent</h2>")
    parts.append(f"<p class='muted'>Status: {esc(forecast_assumptions.get('status'))}</p>")
    plan = forecast_assumptions.get("plan") or {}
    for effect in plan.get("news_effects") or []:
        parts.append("<section class='card'>"
                     f"<strong>{esc(effect.get('driver'))}: {esc(effect.get('change'))}</strong> "
                     f"({esc(', '.join(str(y) for y in effect.get('years') or []))})<br>"
                     f"{esc(effect.get('rationale'))}<br><small>"
                     f"{esc(effect.get('timestamp'))} · {esc(effect.get('source_url'))}"
                     "</small></section>")
    interim = plan.get("interim_scenario") or {}
    if interim:
        parts.append("<section class='card'><strong>Skenario hasil interim</strong><br>"
                     f"{esc(interim.get('rationale'))}<br><small>"
                     f"{esc(interim.get('published_at'))} · {esc(interim.get('source_url'))}"
                     "</small></section>")
    for row in plan.get("outyear_scenario") or []:
        parts.append("<section class='card'><strong>"
                     f"{esc(row.get('year'))} · pertumbuhan revenue "
                     f"{esc(row.get('revenue_growth_pct'))}% · margin EBITDA "
                     f"{esc(row.get('ebitda_margin_pct'))}%</strong><br>"
                     f"Margin laba {esc(row.get('net_income_margin_pct'))}% · "
                     f"capex/revenue {esc(row.get('capex_to_revenue_pct'))}%<br>"
                     f"{esc(row.get('rationale'))}<br><small>"
                     f"Bukti: {esc(', '.join(row.get('source_ids') or []))}"
                     "</small></section>")
    if forecast_assumptions.get("problems"):
        parts.append("<div class='card muted'>" +
                     esc("; ".join(forecast_assumptions["problems"])) + "</div>")
    parts.append("<h2>Deep-dive berita (teks lengkap otomatis)</h2>")
    deepdive = news_deepdive or []
    if not deepdive:
        parts.append("<div class='card muted'>Belum ada hasil deep-dive berita.</div>")
    for item in deepdive:
        if not isinstance(item, dict):
            continue
        status = str(item.get("fetch_status") or "")
        body_preview = str(item.get("full_text") or "")[:400]
        parts.append("<section class='card'>"
                     f"<strong>{esc(item.get('title') or '(tanpa judul)')}</strong><br><small>"
                     f"{esc(item.get('timestamp'))} · {esc(item.get('source_url'))} · "
                     f"status {esc(status)}"
                     + (f" · {esc(item.get('fetched_at'))}" if item.get("fetched_at") else "")
                     + f" · {int(item.get('full_length') or 0)} karakter</small>"
                     + (f"<p>{esc(body_preview)}…</p>" if body_preview and status == "fetched" else
                        "<p class='muted'>Teks lengkap tidak tersedia; memakai ringkasan berita dari Sectors.</p>")
                     + "</section>")
    limitations = brief.get("limitations") or []
    if limitations:
        parts.append("<h2>Bukti yang masih kurang</h2><div class='card'><ul>")
        parts.extend(f"<li>{esc(item)}</li>" for item in limitations)
        parts.append("</ul></div>")
    parts.append("<p><small>Materi informasi dan analisis; bukan rekomendasi investasi.</small></p>")
    parts.append("</main></html>")
    return "\n".join(parts)


def run_analyst(ticker):
    """Planning/peer agent; its failure never blocks the company update."""
    from agents.analyst.run import run as analyst_run
    try:
        return analyst_run(ticker)
    except Exception as error:  # data or code errors: keep the report path alive
        emit("plan", "Agent analis tidak selesai", type(error).__name__, status="error")
        return {"ticker": ticker, "status": "error",
                "problems": [f"{type(error).__name__}: {str(error)[:200]}"]}


def run(ticker, outdir, want_pdf=False, as_of=None,
        illustrative_scenarios=False, analyst_target=False, refresh_assumptions=False):
    """Run the research agent and build a report from the same cached evidence."""
    from agents.research.run import run_live

    t = str(ticker).strip().upper()
    destination = Path(outdir)
    destination.mkdir(parents=True, exist_ok=True)
    print(f"{t}: analyst agent menyusun rencana dan membandingkan peer…", flush=True)
    intel = run_analyst(t)
    print(f"{t}: analyst agent {intel.get('status')}", flush=True)
    print(f"{t}: agent membaca data Sectors dan menyusun briefing…", flush=True)
    emit("research", "Agent riset membaca data dan menyusun brief bersitasi", status="run")
    try:
        research = run_live(t)
    except (OSError, TimeoutError, ValueError) as error:
        # Preserve a usable draft and an explicit failure in the trace when
        # an LLM request times out or the provider returns malformed data.
        research = {"ok": False, "status": "agent_error",
                    "error": f"{type(error).__name__}: {str(error)[:200]}"}
    if not isinstance(research, dict):
        raise TypeError("research agent must return an object")
    print(f"{t}: agent {research.get('status') or ('OK' if research.get('ok') else 'belum lengkap')}",
          flush=True)
    emit("research", "Brief riset tervalidasi" if research.get("ok") else "Brief riset parsial",
         research.get("status"), status="ok" if research.get("ok") else "warn")

    report_as_of = as_of or date.today().isoformat()
    from agents.forecast_assumptions.run import run_cached as forecast_agent
    forecast_intake, _ = intake.load(t, as_of=report_as_of)
    emit("forecast", "Agent asumsi forecast membaca berita dan rilis resmi", status="run")
    assumption_result = forecast_agent(forecast_intake, refresh=refresh_assumptions)
    reused = " (dipakai ulang untuk bukti yang sama)" if assumption_result.get("reused") else ""
    print(f"{t}: forecast agent {assumption_result['status']}{reused}", flush=True)
    emit("forecast", "Asumsi forecast selesai" + reused, assumption_result.get("status"))
    assumption_plan = assumption_result.get("plan")
    emit("report", "Menyusun company update dan memeriksa gate valuasi", status="run")
    report = build.build(t, destination, want_pdf=want_pdf, as_of=report_as_of,
                         illustrative_scenarios=illustrative_scenarios or analyst_target,
                         assumption_plan=assumption_plan,
                         analyst_target=analyst_target,
                         assumption_status=assumption_result.get(
                             "interim_status", assumption_result.get("status")))
    validated, validation_status = research_context.load_analysis(
        t, report["meta"].get("harga_tanggal"))
    safe_research = {
        "ok": bool(research.get("ok") and validated),
        "path": research.get("path"),
        "document": validated,
        "agent_trace": research.get("agent_trace") or {},
        "validation_status": validation_status,
    }
    emit("report", "Company update tersusun", report["meta"].get("status"))
    audit = {
        "ticker": t,
        "analyst": intel,
        "research": safe_research,
        "forecast_assumptions": assumption_result,
        "news_deepdive": forecast_intake.get("news_full") or [],
        "report": {"status": report["meta"].get("status"),
                   "as_of": report["meta"].get("tanggal"),
                   "market_price_date": report["meta"].get("harga_tanggal"),
                   "illustrative_scenarios": bool(report["meta"].get("illustrative_scenarios")),
                   "target_method": report.get("method"),
                   "target_price": report["meta"].get("tp"),
                   "rating": report["meta"].get("rating"),
                   "research_status": report["meta"].get("research_status")},
    }
    trace_json = destination / f"{t}-trace.json"
    trace_html = destination / f"{t}-trace.html"
    trace_json.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    trace_html.write_text(_trace_html(t, safe_research, f"{t}.html",
                                      assumption_result,
                                      forecast_intake.get("news_full"),
                                      analyst=intel), encoding="utf-8")
    emit("done", "Selesai")
    return {"ticker": t, "research_ok": safe_research["ok"], "intel": intel,
            "report_status": report["meta"].get("status"),
            "report_html": str(destination / f"{t}.html"),
            "report_pdf": str(destination / f"{t}.pdf") if want_pdf else None,
            "trace_html": str(trace_html), "trace_json": str(trace_json)}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Sektoral research agent + report")
    parser.add_argument("ticker")
    parser.add_argument("--out", default="out/demo")
    parser.add_argument("--pdf", action="store_true")
    parser.add_argument("--as-of", default=None,
                        help="tanggal laporan YYYY-MM-DD (default: hari ini)")
    parser.add_argument("--illustrative-scenarios", action="store_true",
                        help="tambahkan screen historis dan valuasi ilustratif ke draft")
    parser.add_argument("--analyst-target", action="store_true",
                        help="opt-in target FY26F EV/EBITDA dari rencana agent tervalidasi")
    parser.add_argument("--refresh-assumptions", action="store_true",
                        help="panggil ulang agent forecast walau bukti sama sudah punya rencana tersimpan")
    args = parser.parse_args(argv)
    result = run(args.ticker, args.out, want_pdf=args.pdf, as_of=args.as_of,
                 illustrative_scenarios=args.illustrative_scenarios,
                 analyst_target=args.analyst_target,
                 refresh_assumptions=args.refresh_assumptions)
    intel = result.pop("intel", None) or {}
    result["analyst"] = {"status": intel.get("status"),
                         "headline": (intel.get("synthesis") or {}).get("headline")}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
