"""One-command Sectors-cache research run: agent, validation, report, audit trace."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from . import build, research_context


def _trace_html(ticker, research, report_name):
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
        "<style>body{font:16px/1.55 system-ui,sans-serif;background:#f4f7fb;color:#13233d;"
        "margin:0}main{max-width:920px;margin:auto;padding:34px 20px}header{background:#102a50;"
        "color:white;padding:22px;border-radius:15px}h1{margin:0;font-size:30px}h2{margin-top:30px}"
        ".card{background:white;border:1px solid #d7e0eb;border-radius:12px;padding:18px;"
        "margin:12px 0}.muted{color:#52647e}.chip{display:inline-block;background:#eaf1fb;"
        "padding:4px 9px;margin:3px;border-radius:7px;font:13px ui-monospace,monospace}"
        "a{color:#1657a8}small{color:#52647e}ul{padding-left:20px}</style><main>",
        f"<header><h1>Jejak riset {esc(ticker)}</h1><div>Data: sectors cache · "
        f"as-of {esc(brief.get('as_of'))} · status {esc(brief.get('status'))}</div></header>",
        f"<p><a href='{esc(report_name)}'>Buka company update</a></p>",
        "<h2>Ringkasan agent</h2>",
        f"<div class='card'>{esc(brief.get('summary') or research.get('error') or 'Belum ada briefing tervalidasi.')}</div>",
        "<h2>Endpoint cache yang dipilih</h2><div class='card'>",
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
        parts.append("<div class='card muted'>Belum ada temuan yang lolos validasi cache.</div>")
    limitations = brief.get("limitations") or []
    if limitations:
        parts.append("<h2>Bukti yang masih kurang</h2><div class='card'><ul>")
        parts.extend(f"<li>{esc(item)}</li>" for item in limitations)
        parts.append("</ul></div>")
    parts.append("<p><small>Materi informasi dan analisis; bukan rekomendasi investasi.</small></p>")
    parts.append("</main></html>")
    return "\n".join(parts)


def run(ticker, outdir, want_pdf=False):
    """Run the research agent and build a report from the same cached evidence."""
    from agents.research.run import run_live

    t = str(ticker).strip().upper()
    destination = Path(outdir)
    destination.mkdir(parents=True, exist_ok=True)
    print(f"{t}: agent membaca sectors cache dan menyusun briefing…", flush=True)
    research = run_live(t)
    if not isinstance(research, dict):
        raise TypeError("research agent must return an object")
    print(f"{t}: agent {research.get('status') or ('OK' if research.get('ok') else 'belum lengkap')}",
          flush=True)

    report = build.build(t, destination, want_pdf=want_pdf)
    validated, validation_status = research_context.load_analysis(
        t, report["meta"].get("tanggal"))
    safe_research = {
        "ok": bool(research.get("ok") and validated),
        "path": research.get("path"),
        "document": validated,
        "agent_trace": research.get("agent_trace") or {},
        "validation_status": validation_status,
    }
    audit = {
        "ticker": t,
        "research": safe_research,
        "report": {"status": report["meta"].get("status"),
                   "as_of": report["meta"].get("tanggal"),
                   "research_status": report["meta"].get("research_status")},
    }
    trace_json = destination / f"{t}-trace.json"
    trace_html = destination / f"{t}-trace.html"
    trace_json.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    trace_html.write_text(_trace_html(t, safe_research, f"{t}.html"), encoding="utf-8")
    return {"ticker": t, "research_ok": safe_research["ok"],
            "report_status": report["meta"].get("status"),
            "report_html": str(destination / f"{t}.html"),
            "report_pdf": str(destination / f"{t}.pdf") if want_pdf else None,
            "trace_html": str(trace_html), "trace_json": str(trace_json)}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Sektoral research agent + report")
    parser.add_argument("ticker")
    parser.add_argument("--out", default="out/demo")
    parser.add_argument("--pdf", action="store_true")
    args = parser.parse_args(argv)
    print(json.dumps(run(args.ticker, args.out, want_pdf=args.pdf),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
