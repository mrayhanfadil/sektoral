"""Local browser interface for the Sektoral research workflow.

Run with ``python -m app.web``. The HTTP server binds to loopback by default
and only exposes the report and HTML audit trace produced for a submitted job.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import html
import json
import logging
import re
import shutil
import threading
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
import uuid

from . import cache, gallery, gallery_page, landing, progress, research, ui
from agents.analyst import memory as agent_memory

LOG = logging.getLogger(__name__)
_TICKER = re.compile(r"^[A-Z0-9][A-Z0-9.-]{0,9}$")
_JOB_ID = re.compile(r"^[0-9a-f]{32}$")
_SAFE_STATUS = re.compile(r"^[A-Za-z0-9_.-]{1,48}$")


_PAGE_STYLE = """
body{display:flex;flex-direction:column;min-height:100vh;background:var(--canvas)}
.app{padding:40px 0 64px}
.app .wrap{display:grid;gap:24px}
.app .wrap>*,.run-grid>*,.intel-grid>*,#intel>*{min-width:0}
.card{background:var(--surface);border:1px solid var(--rule);border-radius:16px;padding:32px;
  box-shadow:0 1px 2px rgba(16,24,40,.04)}
.card h1,.card h2{font-size:26px;font-weight:900;letter-spacing:-.02em;margin:8px 0 8px}
.muted{color:var(--ink-soft)}
.run-grid{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(0,1fr);gap:24px;align-items:start}

/* form */
form{margin-top:24px}
label{display:block;font-size:14px;font-weight:700;margin-bottom:8px}
.field{display:flex;gap:10px;align-items:stretch}
input{flex:1;min-width:0;height:52px;padding:0 16px;border:1px solid var(--rule);border-radius:10px;
  font:inherit;font-size:20px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;
  color:var(--ink);background:var(--surface);transition:border-color .15s,box-shadow .15s}
input::placeholder{font-weight:400;letter-spacing:.02em;text-transform:none;color:#8A8F9A;font-size:16px}
input:hover{border-color:#A9AEB8}
input:focus{outline:none;border-color:var(--blue);box-shadow:0 0 0 4px var(--blue-100)}
.field .btn{height:52px;padding:0 24px;font-size:16px}
.hint{font-size:13px;color:var(--ink-soft);margin-top:8px}
.alert{display:flex;gap:10px;align-items:flex-start;margin-top:16px;padding:12px 14px;border-radius:10px;
  background:var(--err-bg);color:var(--err-ink);font-size:15px;font-weight:500}
.chips-head{display:flex;justify-content:space-between;align-items:baseline;gap:12px;margin-top:28px}
.chips-head h3{font-size:14px}
.chips-head span{font-size:13px;color:var(--ink-soft)}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}
.chip{border:1px solid var(--rule);background:var(--surface);color:var(--ink);border-radius:8px;
  padding:6px 11px;font:inherit;font-size:13px;font-weight:700;letter-spacing:.04em;cursor:pointer;
  transition:border-color .15s,color .15s,background-color .15s}
.chip:hover{border-color:var(--blue);color:var(--blue);background:var(--blue-50)}
.chip[aria-pressed="true"]{border-color:var(--blue);background:var(--blue);color:#fff}
.note{margin-top:28px;padding-top:18px;border-top:1px solid var(--rule-soft);font-size:13.5px;
  color:var(--ink-soft)}

/* side explainer */
.side h2{font-size:18px;margin:0 0 16px}
.side ol{list-style:none;margin:0;padding:0;counter-reset:s}
.side ol > li{position:relative;padding:0 0 18px 40px}
.side ol > li:last-child{padding-bottom:0}
.side ol > li::before{counter-increment:s;content:counter(s);position:absolute;left:0;top:0;width:26px;height:26px;
  border-radius:50%;display:grid;place-items:center;font-size:13px;font-weight:900;
  background:var(--blue-50);color:var(--blue)}
.side ol > li:not(:last-child)::after{content:"";position:absolute;left:12.5px;top:30px;bottom:4px;width:1px;
  background:var(--rule)}
.side ol strong{display:block;font-size:15px}
.history{margin-bottom:26px;padding-bottom:22px;border-bottom:1px solid var(--rule-soft)}
.history h3{font-size:16px}
.history ul{list-style:none;margin:12px 0 0;padding:0;display:grid;gap:8px}
.history li{display:grid;grid-template-columns:auto 1fr auto;gap:12px;align-items:center;
  padding:8px 10px;border:1px solid var(--rule-soft);border-radius:10px}
.history .chip{min-width:62px;white-space:nowrap;text-align:center;font-weight:900}
.history li span{font-size:13px;color:var(--ink-soft);line-height:1.4}
.history li a{font-size:13px;font-weight:700;text-decoration:none;white-space:nowrap}
.side ol span{font-size:14px;color:var(--ink-soft)}

/* job status */
.job-head{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;flex-wrap:wrap}
.job-head h2{margin:6px 0 0}
.job-pills{display:flex;gap:8px;flex-wrap:wrap}
.status{font-size:14px;padding:5px 12px}
.progress{list-style:none;display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px;margin:28px 0 0;padding:0}
.progress li{position:relative;padding-top:18px;font-size:14px;font-weight:700;color:#8A8F9A}
.progress li::before{content:"";position:absolute;left:0;right:0;top:0;height:6px;border-radius:6px;
  background:var(--rule-soft);overflow:hidden}
.progress li small{display:block;font-weight:400;font-size:13px}
.progress li.done{color:var(--ink)}
.progress li.done::before{background:var(--blue)}
.progress li.active{color:var(--blue)}
.progress li.active::before{background:linear-gradient(90deg,var(--blue) 0 35%,var(--blue-100) 35% 100%);
  background-size:200% 100%;animation:sweep 1.4s linear infinite}
.progress li.failed{color:var(--err-ink)}
.progress li.failed::before{background:#E5A3A3}
.progress.partial li.done:last-child::before{background:var(--warn-rule)}
@keyframes sweep{from{background-position:100% 0}to{background-position:-100% 0}}
#job-detail{margin-top:22px;font-size:16px}
.links{display:flex;gap:10px;margin-top:20px;flex-wrap:wrap}
.links:empty{display:none}

/* agent log */
.log{margin-top:22px;border-top:1px solid var(--rule-soft);padding-top:14px}
.log summary{cursor:pointer;font-weight:700;font-size:14px;color:var(--ink-soft)}
.events{list-style:none;margin:12px 0 0;padding:0;max-height:340px;overflow:auto}
.ev{display:grid;grid-template-columns:22px 1fr;gap:10px;padding:7px 0;border-bottom:1px dashed var(--rule-soft)}
.ev:last-child{border-bottom:0}
.ev-dot{display:grid;place-items:center;width:20px;height:20px;border-radius:50%;font-size:11px;font-weight:900;
  background:var(--ok-bg);color:var(--ok-ink);margin-top:2px}
.ev-warn .ev-dot{background:var(--warn-bg);color:var(--warn-ink)}
.ev-error .ev-dot{background:var(--err-bg);color:var(--err-ink)}
.ev-run .ev-dot{background:var(--blue-50);border:2px solid var(--blue-100);border-top-color:var(--blue);
  animation:spin .8s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.ev-head{display:flex;flex-wrap:wrap;align-items:baseline;gap:8px;font-size:14.5px}
.ev-tool{font:12px var(--mono);background:var(--blue-50);color:var(--blue);padding:1px 6px;border-radius:5px}
.ev-time{margin-left:auto;font-size:12px;color:#8A8F9A;font-variant-numeric:tabular-nums}
.ev-detail{font-size:13.5px;color:var(--ink-soft);margin-top:2px;overflow-wrap:anywhere}
.card p,.card li,.card h2,.card h3{overflow-wrap:anywhere}

/* market intelligence */
#intel{display:grid;gap:24px}
.intel-head h2{font-size:22px;line-height:1.35;margin:8px 0 14px;max-width:70ch}
.intel-grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.2fr);gap:24px;align-items:start}
.card-title{font-size:17px;margin-bottom:12px}
.sub-title{font-size:14px;margin:18px 0 6px}
.small{font-size:13.5px}
.num{font-variant-numeric:tabular-nums;white-space:nowrap}
.question{font-weight:700;margin-bottom:14px;max-width:880px}
.hyps{margin:0;padding-left:20px;display:grid;gap:16px;max-width:880px}
.hyp-top{display:flex;justify-content:space-between;align-items:flex-start;gap:10px}
.hyp-top .pill{flex:none}
.cite-row{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.cite-row:empty{display:none}
.cite{font-size:12.5px;background:var(--canvas);border:1px solid var(--rule-soft);border-radius:6px;padding:2px 8px}
.table-scroll{overflow-x:auto}
.peer-table{width:100%;border-collapse:collapse;font-size:14px}
.peer-table th,.peer-table td{text-align:left;padding:10px 8px;border-bottom:1px solid var(--rule-soft);vertical-align:middle}
.peer-table thead th{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--ink-soft);font-weight:700}
.peer-table thead small{text-transform:none;letter-spacing:0;font-weight:400}
.peer-table tbody th{font-weight:700;white-space:nowrap}
.strip{display:flex;gap:3px;margin-bottom:2px}
.strip span{width:10px;height:10px;border-radius:3px;background:var(--rule-soft)}
.strip span.me{background:var(--blue);transform:scale(1.25)}
.flags{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:12px}
.flags li{border:1px solid var(--rule);border-radius:10px;padding:12px 14px;display:grid;gap:6px;align-content:start}
.flag-top{display:flex;justify-content:space-between;gap:10px;font-size:14px}
.flags .pill{justify-self:start}
.findings{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}
.finding{border-left:3px solid var(--blue);padding:4px 0 4px 16px;display:grid;gap:8px;align-content:start}
.finding h3{font-size:16px}
.changes{margin:8px 0 0;padding-left:18px;display:grid;gap:4px;font-size:14.5px}
.chg-new_flag{color:var(--warn-ink)}
.plain{margin:0;padding-left:18px;font-size:14.5px}
.steps-list{margin:0;padding-left:20px;display:grid;gap:12px}
.steps-list .pill{font-size:12px;padding:1px 8px}
.cite-web{background:#FFFBF0;border-color:#F3E3B5}
.web-list{list-style:none;margin:0;padding:0;display:grid;gap:10px;font-size:14.5px}
.web-list a{font-weight:500}
.history{margin-bottom:22px;padding-bottom:18px;border-bottom:1px solid var(--rule-soft)}
.history h3{font-size:16px}
.history ul{list-style:none;margin:10px 0 0;padding:0;display:grid;gap:8px}
.history li{display:flex;align-items:center;gap:10px;font-size:13px;color:var(--ink-soft)}

@media (max-width:880px){.run-grid,.intel-grid{grid-template-columns:1fr}}
@media (max-width:720px){.progress{grid-template-columns:1fr;gap:12px}.progress li{padding-top:14px}}
@media (max-width:560px){
  .app{padding:20px 0 40px}
  .card{padding:22px 18px}
  .field{flex-direction:column}
  .field .btn{width:100%}
  .progress{grid-template-columns:1fr;gap:14px}
  .ev-time{margin-left:0}
  .links .btn{flex:1 1 100%}
}
"""

# Canonical Sectoral wordmark (E drawn as three bars), shared with the landing
# page header; the standalone accessible file lives at
# app/assets/brand/sectoral-logo.svg.
_LOGO_SVG = ui.LOGO_SVG


_MAX_EVENTS = 120


def _text(value, limit=400):
    return str(value)[:limit] if isinstance(value, (str, int, float)) and value is not None else None


def _http_url(value):
    parts = urlsplit(str(value or ""))
    return str(value)[:500] if parts.scheme in ("http", "https") and parts.netloc else None


def _public_intel(intel) -> dict | None:
    """Whitelist the analyst result fields the job page renders."""
    if not isinstance(intel, dict) or not isinstance(intel.get("plan"), dict):
        return None
    plan, synthesis = intel["plan"], intel.get("synthesis") or {}
    changes = intel.get("changes") or {}
    signals = []
    for signal in intel.get("signals") or []:
        if not isinstance(signal, dict):
            continue
        row = {key: _text(signal.get(key), 200) for key in
               ("id", "kind", "label", "display", "note", "flag", "period", "median_display")}
        for key in ("rank", "n"):
            row[key] = signal.get(key) if isinstance(signal.get(key), int) else None
        if signal.get("kind") == "web":
            row["url"] = _http_url(signal.get("url"))
        if signal.get("kind") == "peer":
            row["peers"] = [{"symbol": _text(p.get("symbol"), 12), "display": _text(p.get("display"), 40)}
                            for p in (signal.get("peers") or [])[:15] if isinstance(p, dict)]
        signals.append(row)
    def ids(values):
        return [_text(x, 60) for x in (values or []) if isinstance(x, str)][:8]
    return {
        "ticker": _text(intel.get("ticker"), 12), "name": _text(intel.get("name"), 120),
        "market_date": _text(intel.get("market_date"), 20), "status": _text(intel.get("status"), 20),
        "plan": {"question": _text(plan.get("question"), 300), "source": _text(plan.get("source"), 20),
                 "hypotheses": [_text(h, 240) for h in (plan.get("hypotheses") or [])[:4]]},
        "steps": [{key: _text(step.get(key), 240) for key in ("tool", "why", "summary", "status", "origin")}
                  for step in (intel.get("steps") or [])[:10] if isinstance(step, dict)],
        "signals": signals[:30],
        "peers": {key: _text((intel.get("peers") or {}).get(key), 160) for key in ("basis", "group")},
        "web_news": {"window": _text(((intel.get("web_news") or {}).get("window")), 40),
                     "items": [{"title": _text(i.get("title"), 200), "url": _http_url(i.get("url")),
                                "domain": _text(i.get("domain"), 80), "date": _text(i.get("date"), 12)}
                               for i in ((intel.get("web_news") or {}).get("items") or [])[:8]
                               if isinstance(i, dict) and _http_url(i.get("url"))]},
        "synthesis": {
            "headline": _text(synthesis.get("headline"), 400), "source": _text(synthesis.get("source"), 20),
            "findings": [{"title": _text(f.get("title"), 200), "interpretation": _text(f.get("interpretation"), 900),
                          "caveat": _text(f.get("caveat"), 400), "signal_ids": ids(f.get("signal_ids"))}
                         for f in (synthesis.get("findings") or [])[:4] if isinstance(f, dict)],
            "hypotheses": [{"index": h.get("index") if isinstance(h.get("index"), int) else None,
                            "verdict": _text(h.get("verdict"), 30), "reason": _text(h.get("reason"), 400),
                            "signal_ids": ids(h.get("signal_ids"))}
                           for h in (synthesis.get("hypotheses") or [])[:4] if isinstance(h, dict)],
            "next_checks": [_text(x, 200) for x in (synthesis.get("next_checks") or [])[:3]],
        },
        "changes": {"first_run": bool(changes.get("first_run")),
                    "same_market_date": bool(changes.get("same_market_date")),
                    "previous_run_at": _text(changes.get("previous_run_at"), 40),
                    "previous_market_date": _text(changes.get("previous_market_date"), 20),
                    "items": [{"kind": _text(i.get("kind"), 20), "text": _text(i.get("text"), 240)}
                              for i in (changes.get("items") or [])[:12] if isinstance(i, dict)]},
    }


def _available_tickers() -> list[str]:
    """Tickers with a company report in the local Sectors data, for suggestions."""
    try:
        endpoints = cache.endpoints()
    except Exception:  # the form still works without suggestions
        LOG.warning("Ticker suggestions unavailable", exc_info=True)
        return []
    tickers = {
        match.group(1)
        for endpoint in endpoints
        if (match := re.fullmatch(r"/company/report/([A-Z0-9.-]{1,10})/", endpoint))
    }
    return sorted(tickers)


_JOB_SCRIPT = r"""
const stateEl=document.getElementById('job-state');
const progressEl=document.getElementById('job-progress');
const STEP_OF={memory:0,plan:0,tool:1,signals:1,synthesis:2,research:3,forecast:3,report:3,done:4};
function el(tag,cls,text){const n=document.createElement(tag);if(cls)n.className=cls;if(text!=null)n.textContent=text;return n;}
function setProgress(job){
  const events=job.events||[];
  let at=0;
  events.forEach(e=>{if(STEP_OF[e.stage]!==undefined)at=Math.max(at,STEP_OF[e.stage]);});
  if(job.state==='completed')at=5;
  progressEl.classList.toggle('partial',job.state==='completed'&&job.quality==='partial');
  progressEl.querySelectorAll('li').forEach((li,i)=>{
    const waiting=job.state==='pending';
    li.className=waiting?'':i<at?'done':i===at?(job.state==='error'?'failed':'active'):'';
    if(!waiting&&i===at)li.setAttribute('aria-current','step');else li.removeAttribute('aria-current');
  });
}
const STATUS_ICON={ok:'✓',warn:'!',error:'×',run:''};
function renderEvents(job){
  const list=document.getElementById('job-events');
  const events=(job.events||[]);
  const shown=events.filter((e,i)=>e.status!=='run'||(i===events.length-1&&job.state==='running'));
  list.replaceChildren(...shown.map(e=>{
    const li=el('li','ev ev-'+e.status);
    const dot=el('span','ev-dot',STATUS_ICON[e.status]||'');dot.setAttribute('aria-hidden','true');
    const body=el('div','ev-body');
    const head=el('div','ev-head');
    head.append(el('strong',null,e.label));
    if(e.tool)head.append(el('code','ev-tool',e.tool));
    head.append(el('span','ev-time',e.t+' dtk'));
    body.append(head);
    if(e.detail)body.append(el('p','ev-detail',e.detail));
    li.append(dot,body);return li;
  }));
  document.getElementById('job-log').hidden=shown.length===0;
  if(job.state==='running')list.scrollTop=list.scrollHeight;
}
const VERDICT_CLS={'didukung':'ok','tidak didukung':'err','belum terjawab':''};
function renderIntel(intel){
  const root=document.getElementById('intel');
  if(!intel){root.hidden=true;return;}
  root.hidden=false;
  const sig={};(intel.signals||[]).forEach(s=>sig[s.id]=s);
  const syn=intel.synthesis||{};
  document.getElementById('intel-name').textContent=intel.name||intel.ticker;
  document.getElementById('intel-headline').textContent=syn.headline||'';
  const meta=document.getElementById('intel-meta');meta.replaceChildren();
  if(intel.peers&&intel.peers.group)meta.append(el('span','pill live','Grup: '+intel.peers.group));
  if(intel.market_date)meta.append(el('span','pill','Data pasar '+intel.market_date));
  meta.append(el('span','pill '+(syn.source==='agent'?'ok':'warn'),syn.source==='agent'?'Kesimpulan agent tervalidasi':'Ringkasan aturan host'));
  // plan + hypotheses
  document.getElementById('intel-question').textContent=(intel.plan||{}).question||'';
  const verdicts={};(syn.hypotheses||[]).forEach(h=>{if(h.index!=null)verdicts[h.index]=h;});
  const hyp=document.getElementById('intel-hypotheses');
  hyp.replaceChildren(...((intel.plan||{}).hypotheses||[]).map((h,i)=>{
    const v=verdicts[i]||{};const li=el('li');
    const top=el('div','hyp-top');top.append(el('span','hyp-text',h));
    top.append(el('span','pill '+(VERDICT_CLS[v.verdict]??''),v.verdict||'belum dinilai'));
    li.append(top);
    if(v.reason)li.append(el('p','muted small',v.reason));
    li.append(chipRow(v.signal_ids,sig));
    return li;
  }));
  // peers
  const peers=(intel.signals||[]).filter(s=>s.kind==='peer');
  document.getElementById('intel-peer-card').hidden=!peers.length;
  document.getElementById('intel-peer-basis').textContent=intel.peers&&intel.peers.basis?'Basis: '+intel.peers.basis:'';
  const tbody=document.getElementById('intel-peers');
  tbody.replaceChildren(...peers.map(s=>{
    const tr=el('tr');
    tr.append(el('th',null,s.label));
    const val=el('td','num',s.display);tr.append(val);
    const pos=el('td');
    if(s.rank&&s.n){
      const strip=el('div','strip');strip.setAttribute('role','img');
      strip.setAttribute('aria-label','peringkat '+s.rank+' dari '+s.n);
      for(let i=1;i<=s.n;i++){const d=el('span',i===s.rank?'me':'');strip.append(d);}
      pos.append(strip,el('small','muted',s.rank+' / '+s.n));
    }else pos.append(el('small','muted',s.note||'n.a.'));
    tr.append(pos);
    tr.append(el('td','num muted',s.median_display||'—'));
    const flag=el('td');if(s.flag)flag.append(el('span','pill warn',s.flag));tr.append(flag);
    return tr;
  }));
  // flagged signals (non-peer)
  const flagged=(intel.signals||[]).filter(s=>s.flag&&s.kind!=='peer');
  document.getElementById('intel-flag-card').hidden=!flagged.length;
  document.getElementById('intel-flags').replaceChildren(...flagged.map(s=>{
    const li=el('li');const top=el('div','flag-top');
    top.append(el('strong',null,s.label),el('span','num',s.display));
    li.append(top);li.append(el('span','pill warn',s.flag));
    const sub=[s.period,s.note].filter(Boolean).join(' · ');if(sub)li.append(el('p','muted small',sub));
    return li;
  }));
  // findings
  document.getElementById('intel-findings').replaceChildren(...(syn.findings||[]).map(f=>{
    const card=el('article','finding');
    card.append(el('h3',null,f.title),el('p',null,f.interpretation));
    const cav=el('p','muted small');cav.append(el('strong',null,'Batas bukti. '),document.createTextNode(f.caveat||''));
    card.append(cav,chipRow(f.signal_ids,sig));return card;
  }));
  // changes since last run
  const ch=intel.changes||{};const chEl=document.getElementById('intel-changes');chEl.replaceChildren();
  if(ch.first_run)chEl.append(el('p','muted','Riset pertama untuk emiten ini. Hasilnya disimpan sebagai memori untuk dibandingkan pada riset berikutnya.'));
  else{
    chEl.append(el('p','muted small','Dibanding riset '+String(ch.previous_run_at||'').slice(0,16).replace('T',' ')+' (data pasar '+(ch.previous_market_date||'—')+').'));
    if(!(ch.items||[]).length)chEl.append(el('p',null,ch.same_market_date?'Data pasar belum berubah sejak riset terakhir; tidak ada sinyal yang bergeser.':'Tidak ada sinyal yang bergeser.'));
    else{const ul=el('ul','changes');(ch.items||[]).forEach(i=>ul.append(el('li','chg chg-'+i.kind,i.text)));chEl.append(ul);}
  }
  const next=(syn.next_checks||[]).filter(Boolean);
  document.getElementById('intel-next-wrap').hidden=!next.length;
  document.getElementById('intel-next').replaceChildren(...next.map(t=>el('li',null,t)));
  renderWeb(intel.web_news);
  // steps
  document.getElementById('intel-steps').replaceChildren(...(intel.steps||[]).map(s=>{
    const li=el('li');const head=el('div','ev-head');
    head.append(el('code','ev-tool',s.tool));
    head.append(el('span','pill '+(s.origin==='agent_adaptive'?'live':''),s.origin==='agent'?'sesuai rencana':s.origin==='agent_adaptive'?'keputusan baru agent':'dilengkapi host'));
    li.append(head);
    if(s.why)li.append(el('p','small',s.why));
    if(s.summary)li.append(el('p','muted small','→ '+s.summary));
    return li;
  }));
}
function chipRow(ids,sig){
  const row=el('div','cite-row');
  (ids||[]).forEach(id=>{const s=sig[id];if(!s)return;
    if(s.kind==='web')row.append(el('span','cite cite-web','Web: '+(s.label||'').slice(0,70)));
    else row.append(el('span','cite',s.label+': '+s.display));});
  return row;
}
function renderWeb(web){
  const items=(web&&web.items)||[];
  document.getElementById('intel-web-card').hidden=!items.length;
  document.getElementById('intel-web-note').textContent='Berita '+(web&&web.window?web.window:'')+
    '. Hanya konteks naratif, bukan data Sectors; tidak ada angka sinyal yang berasal dari sini.';
  document.getElementById('intel-web').replaceChildren(...items.map(i=>{
    const li=el('li');const a=el('a',null,i.title);a.href=i.url;a.target='_blank';a.rel='noopener noreferrer';
    li.append(a,el('span','muted small',' '+i.date+' · '+i.domain));return li;
  }));
}
async function refreshJob(){
  try{
    const response=await fetch('/api/jobs/'+jobId,{cache:'no-store'});
    if(!response.ok) throw new Error('status');
    const job=await response.json();
    document.getElementById('job-title').textContent='Riset '+job.ticker;
    document.title='Riset '+job.ticker+' | Sectoral';
    const labels={pending:'Menunggu',running:'Sedang diproses',completed:'Selesai',error:'Tidak selesai'};
    stateEl.textContent=labels[job.state]||'Status';
    stateEl.className='pill status '+(job.state==='error'?'err':job.state==='completed'?'ok':'live');
    setProgress(job);renderEvents(job);
    const qualityEl=document.getElementById('job-quality');
    qualityEl.hidden=job.state!=='completed';
    qualityEl.textContent=job.quality==='partial'?'Parsial':'Lengkap';
    qualityEl.className='pill status '+(job.quality==='partial'?'warn':'ok');
    const last=(job.events||[]).slice(-1)[0];
    document.getElementById('job-detail').textContent=job.state==='error'
      ?'Proses riset mengalami kendala. Periksa log lokal untuk detail.'
      :job.state==='completed'
        ?(job.quality==='partial'?'Analisis parsial: bukti belum cukup untuk semua bagian. Batasnya dijelaskan di laporan dan jejak agent.':'Laporan dan jejak validasi siap ditinjau.')
        :job.state==='running'
          ?(last?last.label+'…':'Agent memulai riset…')
          :'Riset masuk antrean dan akan segera dimulai.';
    const links=document.getElementById('job-links');
    links.replaceChildren();
    if(job.report_url) addLink(links,job.report_url,'Buka company update','btn btn-primary');
    if(job.trace_url) addLink(links,job.trace_url,'Lihat jejak agent','btn btn-ghost');
    if(job.pdf_url) addLink(links,job.pdf_url,'Buka PDF','btn btn-ghost');
    if(job.gallery_url) addLink(links,job.gallery_url,'Lihat di galeri laporan','btn btn-ghost');
    if(job.state==='completed') renderIntel(job.intel);
    if(job.state==='pending'||job.state==='running') setTimeout(refreshJob,1000);
  }catch(_error){
    document.getElementById('job-detail').textContent='Status belum tersedia. Muat ulang halaman untuk mencoba lagi.';
  }
}
function addLink(parent,href,label,cls){const link=document.createElement('a');link.href=href;link.textContent=label;link.className=cls;parent.appendChild(link);}
refreshJob();
"""

_JOB_MARKUP = """<section class="card" aria-labelledby="job-title">
  <div class="job-head">
    <div><span class="eyebrow">Status riset</span><h2 id="job-title">Sedang menyiapkan riset</h2></div>
    <div class="job-pills"><span id="job-quality" class="pill status" hidden></span><span id="job-state" class="pill status live">Menunggu</span></div>
  </div>
  <ol id="job-progress" class="progress" aria-label="Tahap riset">
    <li>Rencana<small>Pertanyaan &amp; hipotesis</small></li>
    <li>Tool &amp; sinyal<small>Data Sectors, peer, anomali</small></li>
    <li>Uji hipotesis<small>Kesimpulan tervalidasi</small></li>
    <li>Skenario &amp; valuasi<small>Asumsi, rantai metode, harness</small></li>
    <li>Hasil siap<small>Laporan, PDF, dan jejak</small></li>
  </ol>
  <p id="job-detail" class="muted" aria-live="polite">Agent membaca data Sectors untuk emiten ini.</p>
  <div id="job-links" class="links"></div>
  <details id="job-log" class="log" open hidden><summary>Log kerja agent</summary><ol id="job-events" class="events"></ol></details>
</section>
<section id="intel" hidden aria-labelledby="intel-headline">
  <div class="card intel-head">
    <span class="eyebrow">Intelijen pasar · <span id="intel-name"></span></span>
    <h2 id="intel-headline"></h2>
    <div id="intel-meta" class="job-pills"></div>
  </div>
  <div class="card"><h3 class="card-title">Rencana &amp; hipotesis agent</h3>
      <p id="intel-question" class="question"></p><ol id="intel-hypotheses" class="hyps"></ol></div>
  <div class="card" id="intel-peer-card"><h3 class="card-title">Posisi terhadap peer</h3>
      <p id="intel-peer-basis" class="muted small"></p>
      <div class="table-scroll"><table class="peer-table"><thead><tr><th scope="col">Metrik</th><th scope="col">Emiten</th>
      <th scope="col">Peringkat <small>(kiri = tertinggi)</small></th><th scope="col">Median peer</th><th scope="col"><span class="sr-only">Tanda</span></th></tr></thead>
      <tbody id="intel-peers"></tbody></table></div></div>
  <div class="card" id="intel-flag-card"><h3 class="card-title">Sinyal yang perlu dicek</h3><ul id="intel-flags" class="flags"></ul></div>
  <div class="card"><h3 class="card-title">Temuan</h3><div id="intel-findings" class="findings"></div></div>
  <div class="card" id="intel-web-card" hidden><h3 class="card-title">Konteks berita web <span class="pill">Tavily</span></h3>
    <p class="muted small" id="intel-web-note"></p><ul id="intel-web" class="web-list"></ul></div>
  <div class="intel-grid">
    <div class="card"><h3 class="card-title">Sejak riset terakhir</h3><div id="intel-changes"></div>
      <div id="intel-next-wrap" hidden><h4 class="sub-title">Pemeriksaan lanjutan yang disarankan agent</h4><ul id="intel-next" class="plain"></ul></div></div>
    <div class="card"><h3 class="card-title">Keputusan tool agent</h3><ol id="intel-steps" class="steps-list"></ol></div>
  </div>
  <p class="note">Sinyal dihitung deterministik dari data Sectors; agent memilih pemeriksaan dan menafsirkan hasilnya.
  Informasi dan analisis, bukan rekomendasi investasi.</p>
</section>"""


def _history_markup(reports=None) -> str:
    try:
        rows = agent_memory.watchlist()[:6]
    except OSError:
        rows = []
    if not rows:
        return ""
    items = "".join(
        f'<li><button type="button" class="chip" data-ticker="{html.escape(r["ticker"])}" aria-pressed="false">'
        f'{html.escape(r["ticker"])}</button><span>{r["runs"]} kali · data {html.escape(str(r.get("market_date") or "—"))}'
        f' · {r["flags"]} sinyal bertanda</span>'
        + (f'<a href="/laporan/{html.escape(r["ticker"])}/pdf">PDF</a>'
           if reports and gallery.artifact(reports, r["ticker"], "pdf") else "<span></span>")
        + '</li>' for r in rows)
    return (f'<div class="history"><h3 id="history-title">Riwayat riset</h3>'
            f'<p class="muted small">Agent mengingat riset sebelumnya dan melaporkan apa yang berubah.</p>'
            f'<ul aria-labelledby="history-title">{items}</ul></div>')


def _page(job_id: str | None = None, error: str | None = None, reports=None) -> bytes:
    tickers = _available_tickers()
    job_markup = ""
    if job_id:
        job_markup = _JOB_MARKUP
    alert = (f'<div class="alert" role="alert"><span aria-hidden="true">!</span>'
             f'<span>{html.escape(error)}</span></div>') if error else ""
    chips = "".join(
        f'<button type="button" class="chip" data-ticker="{html.escape(t)}" aria-pressed="false">{html.escape(t)}</button>'
        for t in tickers
    )
    datalist = "".join(f'<option value="{html.escape(t)}">' for t in tickers)
    suggestions = (
        f"""<div class="chips-head"><h3 id="chips-title">Emiten dengan data tersedia</h3><span>{len(tickers)} emiten</span></div>
<div class="chips" role="group" aria-labelledby="chips-title">{chips}</div>"""
        if tickers else ""
    )
    form_heading = "Riset emiten lain" if job_id else "Buat company update"
    form_tag = "h2" if job_id else "h1"
    page_heading = "" if not job_id else '<h1 class="sr-only">Riset emiten</h1>'
    body = f"""<body>
{ui.site_header("research")}
<main id="konten" class="app"><div class="wrap">
{page_heading}{job_markup}
<div class="run-grid">
  <section class="card" aria-labelledby="form-title">
    <span class="eyebrow">Riset baru</span>
    <{form_tag} id="form-title">{form_heading}</{form_tag}>
    <p class="muted">Masukkan kode emiten untuk menjalankan agent, memeriksa bukti, dan menyusun ringkasan riset.</p>
    <form id="run-form" action="/run" method="post">
      <label for="ticker">Kode emiten IDX</label>
      <div class="field">
        <input id="ticker" name="ticker" maxlength="10" pattern="[A-Za-z0-9][A-Za-z0-9.\\-]{{0,9}}" placeholder="Contoh: AMMN" required autocomplete="off" list="ticker-list" aria-describedby="ticker-hint">
        <button type="submit" class="btn btn-primary">Mulai riset</button>
      </div>
      <datalist id="ticker-list">{datalist}</datalist>
      <p id="ticker-hint" class="hint">Kode saham BEI, misalnya AMMN atau BBRI.</p>
      {alert}
    </form>
    {suggestions}
    <p class="note">Hasil menyajikan informasi dan analisis, bukan rekomendasi investasi. Kesimpulan ditandai parsial jika bukti belum cukup.</p>
  </section>
  <aside class="card side" aria-labelledby="side-title">
    {_history_markup(reports)}
    <h2 id="side-title">Setelah Anda menekan Mulai riset</h2>
    <ol>
      <li><strong>Agent menyusun rencana</strong><span>Pertanyaan riset dan hipotesis yang bisa diuji, sesuai jenis usaha emiten.</span></li>
      <li><strong>Agent memilih tool</strong><span>Peer, kuartalan, harga, arus asing, valuasi, berita. Setiap hasil bisa mengubah langkah berikutnya.</span></li>
      <li><strong>Sinyal & hipotesis diuji</strong><span>Peringkat peer dan anomali dihitung deterministik; kesimpulan wajib mengutip sinyal.</span></li>
      <li><strong>Skenario, valuasi, pemeriksaan</strong><span>Agen asumsi menyusun skenario laba dan risiko; gerbang memilih rantai metode; harness memutuskan terbit atau tahan.</span></li>
    </ol>
  </aside>
</div>
</div></main>
{ui.site_footer()}
</body>"""
    script = """
<script>
const input=document.getElementById('ticker');
document.querySelectorAll('.chip').forEach(chip=>chip.addEventListener('click',()=>{
  input.value=chip.dataset.ticker;syncChips();input.focus();
}));
function syncChips(){const v=input.value.trim().toUpperCase();
  document.querySelectorAll('.chip').forEach(c=>c.setAttribute('aria-pressed',String(c.dataset.ticker===v)));}
input.addEventListener('input',syncChips);
document.getElementById('run-form').addEventListener('submit',event=>{
  const button=event.target.querySelector('button[type=submit]');
  button.disabled=true;button.textContent='Memulai…';
});
window.addEventListener('pageshow',()=>{const b=document.querySelector('#run-form button[type=submit]');
  b.disabled=false;b.textContent='Mulai riset';});
</script>"""
    if job_id:
        script += f"<script>const jobId={json.dumps(job_id)};\n{_JOB_SCRIPT}</script>"
    page = ui.document(
        "Sectoral | Company update",
        "Jalankan agen riset Sectoral untuk emiten BEI dan tinjau company update beserta jejak sitasinya.",
        _PAGE_STYLE,
        body,
        script,
    )
    return page.encode("utf-8")


class ResearchWeb:
    """Job registry and bounded artifact access for one local server instance."""

    def __init__(self, outdir: str | Path, reports: str | Path | None = None, want_pdf: bool = False):
        self.outdir = Path(outdir).resolve()
        self.outdir.mkdir(parents=True, exist_ok=True)
        # Finished reports shown on /laporan and the landing page.
        self.reports = Path(reports).resolve() if reports else self.outdir / "reports"
        self.want_pdf = want_pdf
        self._jobs: dict[str, dict] = {}
        self._lock = threading.Lock()
        # A single worker keeps generated output writes predictable. Each run
        # also receives its own directory so repeated ticker runs stay stable.
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="sektoral-research")

    def submit(self, ticker: str) -> str:
        ticker = ticker.strip().upper()
        if not _TICKER.fullmatch(ticker):
            raise ValueError("Kode emiten tidak valid.")
        job_id = uuid.uuid4().hex
        with self._lock:
            self._jobs[job_id] = {"ticker": ticker, "state": "pending"}
        self._executor.submit(self._run, job_id, ticker)
        return job_id

    def _run(self, job_id: str, ticker: str) -> None:
        with self._lock:
            self._jobs[job_id]["state"] = "running"
        try:
            job_outdir = self.outdir / job_id
            job_outdir.mkdir(parents=True, exist_ok=True)

            def record(event):
                with self._lock:
                    events = self._jobs[job_id].setdefault("events", [])
                    if len(events) < _MAX_EVENTS:
                        events.append(event)

            with progress.capture(record):
                result = research.run(ticker, job_outdir, want_pdf=self.want_pdf)
            report = self._safe_known_artifact(job_id, ticker, "report")
            trace = self._safe_known_artifact(job_id, ticker, "trace")
            if report is None or trace is None:
                raise FileNotFoundError("research run did not produce expected HTML artifacts")
            is_partial = not bool(result.get("research_ok")) or "draft" in str(
                result.get("report_status", "")
            ).lower()
            status = result.get("report_status")
            safe_status = status if isinstance(status, str) and _SAFE_STATUS.fullmatch(status) else None
            self._publish(job_outdir, ticker)
            with self._lock:
                self._jobs[job_id].update({
                    "state": "completed",
                    "quality": "partial" if is_partial else "complete",
                    "report_status": safe_status,
                    "intel": _public_intel(result.get("intel")),
                })
        except Exception:
            # Details may contain credentials or source data: keep them in
            # the local server log and return only a generic state to the page.
            LOG.exception("Local research job failed for %s", ticker)
            with self._lock:
                self._jobs[job_id].update({"state": "error", "quality": "partial"})

    def _publish(self, job_outdir: Path, ticker: str) -> None:
        """Copy a finished run into the reports folder so /laporan lists it."""
        try:
            self.reports.mkdir(parents=True, exist_ok=True)
            for name in (f"{ticker}.json", f"{ticker}.html", f"{ticker}.pdf", f"{ticker}-trace.html"):
                source = job_outdir / name
                if source.is_file():
                    shutil.copy2(source, self.reports / name)
        except OSError:
            LOG.exception("Could not publish %s to the reports folder", ticker)

    def snapshot(self, job_id: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            result = {"ticker": job["ticker"], "state": job["state"],
                      "events": list(job.get("events") or [])}
            if job["state"] in ("completed", "error"):
                result["quality"] = job.get("quality", "partial")
            if job["state"] == "completed":
                result["report_url"] = f"/artifact/{job_id}/report"
                result["trace_url"] = f"/artifact/{job_id}/trace"
                if gallery.artifact(self.reports, job["ticker"], "pdf"):
                    result["pdf_url"] = f"/laporan/{job['ticker']}/pdf"
                result["gallery_url"] = "/laporan"
                if job.get("report_status"):
                    result["report_status"] = job["report_status"]
                if job.get("intel"):
                    result["intel"] = job["intel"]
            return result

    def artifact(self, job_id: str, kind: str) -> Path | None:
        if not _JOB_ID.fullmatch(job_id):
            return None
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job.get("state") != "completed":
                return None
            ticker = job["ticker"]
        # The trace links to its report by filename ("TICKER.html"), which
        # resolves next to /artifact/<job>/trace.
        if kind == f"{ticker}.html":
            kind = "report"
        if kind not in ("report", "trace"):
            return None
        return self._safe_known_artifact(job_id, ticker, kind)

    def _safe_known_artifact(self, job_id: str, ticker: str, kind: str) -> Path | None:
        path = self._known_artifact(job_id, ticker, kind)
        try:
            resolved = path.resolve(strict=True)
        except FileNotFoundError:
            return None
        expected_dir = (self.outdir / job_id).resolve()
        if resolved.parent != expected_dir or not resolved.is_file():
            return None
        return resolved

    def _known_artifact(self, job_id: str, ticker: str, kind: str) -> Path:
        filename = f"{ticker}.html" if kind == "report" else f"{ticker}-trace.html"
        return self.outdir / job_id / filename

    def close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)


def make_handler(app: ResearchWeb):
    class Handler(BaseHTTPRequestHandler):
        server_version = "SektoralLocal/1.0"

        def log_message(self, format, *args):
            LOG.info("%s - %s", self.address_string(), format % args)

        def _send(self, status: int, body: bytes, content_type: str):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urlsplit(self.path)
            path = parsed.path
            if path == "/":
                page = landing.render_landing(gallery.load(app.reports))
                self._send(200, page.encode("utf-8"), "text/html; charset=utf-8")
                return
            if path == "/research":
                self._send(200, _page(reports=app.reports), "text/html; charset=utf-8")
                return
            if path in ("/laporan", "/laporan/"):
                page = gallery_page.render_gallery(gallery.load(app.reports))
                self._send(200, page.encode("utf-8"), "text/html; charset=utf-8")
                return
            if path.startswith("/laporan/"):
                pieces = path.split("/")
                if len(pieces) == 4 and pieces[3] == "cover.png":
                    try:
                        png = gallery.cover(app.reports, pieces[2])
                    except Exception:
                        LOG.exception("cover thumbnail failed")
                        png = None
                    if png is None:
                        self._send(404, b"Not found", "text/plain; charset=utf-8")
                    else:
                        self._send(200, png.read_bytes(), "image/png")
                    return
                found = gallery.artifact(app.reports, pieces[2], pieces[3]) if len(pieces) == 4 else None
                if found is None:
                    self._send(404, b"Not found", "text/plain; charset=utf-8")
                else:
                    self._send(200, found[0].read_bytes(), found[1])
                return
            if path in {"/assets/brand/sectoral-logo.svg", "/assets/brand/research-flow.svg"}:
                filename = "sectoral-logo.svg" if path.endswith("sectoral-logo.svg") else "research-flow.svg"
                asset = Path(__file__).resolve().parent / "assets" / "brand" / filename
                try:
                    body = asset.read_bytes()
                except OSError:
                    self._send(404, b"Not found", "text/plain; charset=utf-8")
                    return
                self._send(200, body, "image/svg+xml; charset=utf-8")
                return
            if path.startswith("/jobs/"):
                job_id = path.removeprefix("/jobs/")
                snapshot = app.snapshot(job_id) if _JOB_ID.fullmatch(job_id) else None
                if snapshot is None:
                    self._send(404, _page(error="Run tidak ditemukan."), "text/html; charset=utf-8")
                else:
                    self._send(200, _page(job_id, reports=app.reports), "text/html; charset=utf-8")
                return
            if path.startswith("/api/jobs/"):
                job_id = path.removeprefix("/api/jobs/")
                snapshot = app.snapshot(job_id) if _JOB_ID.fullmatch(job_id) else None
                if snapshot is None:
                    self._send(404, b'{"error":"not found"}', "application/json; charset=utf-8")
                else:
                    self._send(200, json.dumps(snapshot).encode(), "application/json; charset=utf-8")
                return
            if path.startswith("/artifact/"):
                pieces = path.split("/")
                artifact = app.artifact(pieces[2], pieces[3]) if len(pieces) == 4 else None
                if artifact is None:
                    self._send(404, b"Not found", "text/plain; charset=utf-8")
                else:
                    self._send(200, artifact.read_bytes(), "text/html; charset=utf-8")
                return
            self._send(404, b"Not found", "text/plain; charset=utf-8")

        def do_POST(self):
            if urlsplit(self.path).path != "/run":
                self._send(404, b"Not found", "text/plain; charset=utf-8")
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if length < 1 or length > 4096:
                self._send(400, _page(error="Form riset tidak valid."), "text/html; charset=utf-8")
                return
            body = self.rfile.read(length)
            if self.headers.get_content_type() != "application/x-www-form-urlencoded":
                self._send(400, _page(error="Form riset tidak valid."), "text/html; charset=utf-8")
                return
            fields = parse_qs(body.decode("utf-8", errors="replace"), keep_blank_values=True)
            values = fields.get("ticker", [])
            if len(values) != 1 or not _TICKER.fullmatch(values[0].strip().upper()):
                self._send(400, _page(error="Masukkan kode emiten yang valid."), "text/html; charset=utf-8")
                return
            job_id = app.submit(values[0])
            self.send_response(303)
            self.send_header("Location", f"/jobs/{job_id}")
            self.send_header("Content-Length", "0")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()

    return Handler


def create_server(outdir: str | Path = "out/demo", host: str = "127.0.0.1", port: int = 8765,
                  reports: str | Path | None = None, want_pdf: bool = False):
    app = ResearchWeb(outdir, reports, want_pdf)
    server = ThreadingHTTPServer((host, port), make_handler(app))
    server.research_app = app
    return server


def main(argv=None):
    parser = argparse.ArgumentParser(description="Local Sektoral research browser");
    parser.add_argument("--out", default="out/demo", help="generated research output directory")
    parser.add_argument("--host", default="127.0.0.1", help="bind address (default: localhost)")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--reports", default=None,
                        help="folder of finished reports for /laporan (default: <out>/reports)")
    parser.add_argument("--pdf", action="store_true", help="also render the PDF for browser runs")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    server = create_server(args.out, args.host, args.port, args.reports, args.pdf)
    print(f"Sektoral local research UI: http://{args.host}:{server.server_address[1]}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.research_app.close()
        server.server_close()


if __name__ == "__main__":
    main()
