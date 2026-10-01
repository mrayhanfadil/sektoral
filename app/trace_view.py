"""Public view of an audit trace (``<T>-trace.json``) for the web app.

The trace on disk keeps everything the run saw. The browser gets the same
fields the standalone trace HTML shows (see ``research._trace_html``), each
typed and length-bounded; nothing else leaves the server.

Indonesian text the host wrote gets an English twin, ``<field>_en`` (#34),
also for traces stored before twins existed (``app.host_lang``), and so does
curated source text with its English in ``data/source_text_en``
(``prose_lang.known``); source data (news titles, search queries, article
text) and agent prose without its own twin stay Indonesian.

Given the report document the trace belongs to, the view also says what the
model ran where it is not the agents' proposal (the curated bank driver
file, a LoM or Operating Model out-year schedule) and which peer group the
report compares against when the research run used another one; all of it
is read from the report as built, never from a pack that may have changed.
"""
from __future__ import annotations

import re

from . import host_lang, prose_lang, report_lang
from .jobs import http_url, public_intel, text


def _list(value):
    return [x for x in value if isinstance(x, dict)] if isinstance(value, list) else []


# The analyst validator's "...; hapus kata: a, b" / "...; hapus: 12, 3,5%" and
# "token non-Indonesia dihapus: x, y": what the model had to drop, as a list.
_REMOVED = re.compile(r"(?:; hapus(?: kata)?|(?<= dihapus)): ([^;]*)")


def problem_notes(problems) -> list[dict]:
    """Analyst validator notes as {message, removed}: the note without its
    word lists, and the words it names to remove (stored notes are strings)."""
    notes = []
    for problem in (problems if isinstance(problems, list) else [])[:6]:
        if not isinstance(problem, str):
            continue
        removed = [word.strip() for found in _REMOVED.findall(problem)
                   for word in found.split(", ") if word.strip()]
        message = _REMOVED.sub("", problem).strip() or problem
        notes.append({"message": text(message, 300),
                      "removed": [text(word, 60) for word in removed[:12]]})
    return notes


def _english_list(values, limit, count) -> list:
    """The English of each host-written string, parallel to the Indonesian list
    (``text(value, limit)`` of its first `count` strings); None where there is none."""
    return [text(host_lang.english(v), limit)
            for v in (values if isinstance(values, list) else [])[:count] if isinstance(v, str)]


def _english_notes(notes) -> list:
    """Problem notes with the English of each message (``message_en``)."""
    return [{**note, "message_en": text(note.get("message_en")
                                        or host_lang.english(note.get("message")), 300)}
            if isinstance(note, dict) else note for note in notes]


def _status(report: dict) -> dict:
    published = str(report.get("status") or "").startswith("distributable")
    return {
        "release_status": text(report.get("status"), 48),
        "published": published,
        "rating": text(report.get("rating"), 30) if published else None,
        "target_price": report.get("target_price") if published and isinstance(
            report.get("target_price"), (int, float)) else None,
        "method": text(str(report.get("target_method") or "").split(" [")[0], 200) if published else None,
        "method_en": text(host_lang.english(str(report.get("target_method") or "").split(" [")[0]), 200)
        if published else None,
        "as_of": text(report.get("as_of"), 20),
        "market_price_date": text(report.get("market_price_date"), 20),
    }


def _research(research: dict) -> dict:
    brief = research.get("document") if isinstance(research.get("document"), dict) else {}
    agent = brief.get("agent_trace") or research.get("agent_trace") or {}
    limitations = [x for x in (brief.get("limitations") or [])[:10] if isinstance(x, str)]
    return {
        "summary": text(brief.get("summary"), 1200),
        # Host sentences of the brief: English in data/source_text_en/research.json.
        "summary_en": text(host_lang.english(brief.get("summary")), 1200),
        "endpoints": [text(e, 120) for e in (agent.get("selected_cache_endpoints") or [])[:40]
                      if isinstance(e, str)],
        "insights": [{
            "title": text(i.get("title"), 200),
            "observation": text(i.get("observation"), 900),
            "implication": text(i.get("implication"), 900),
            "caveat": text(i.get("caveat"), 600),
            # English twins the agent wrote beside each field; None when absent.
            "title_en": text(i.get("title_en"), 200),
            "observation_en": text(i.get("observation_en"), 900),
            "implication_en": text(i.get("implication_en"), 900),
            "caveat_en": text(i.get("caveat_en"), 600),
            "citations": [{"endpoint": text(c.get("endpoint"), 120), "field_path": text(c.get("field_path"), 160),
                           "value": text(c.get("value"), 180)} for c in _list(i.get("citations"))[:12]],
        } for i in _list(brief.get("insights"))[:8]],
        "limitations": [text(x, 400) for x in limitations],
        "limitations_en": ([text(host_lang.english(x), 400) for x in limitations]
                           if any(host_lang.english(x) for x in limitations) else None),
    }


def _news(sources: dict) -> dict:
    search = sources.get("search") if isinstance(sources.get("search"), dict) else {}
    queries = search.get("queries") or ([search.get("query")] if search.get("query") else [])
    rejected = _list(sources.get("rejected"))
    return {
        "search": {"status": text(search.get("status"), 40), "as_of": text(search.get("as_of"), 20),
                   "queries": [text(q.get("query") if isinstance(q, dict) else q, 120)
                               for q in queries[:6] if q]},
        "articles": [{"id": text(a.get("register_id"), 40), "date": text(a.get("timestamp"), 30),
                      "origins": [text(o, 30) for o in (a.get("origins") or [])[:4]],
                      "title": text(a.get("title"), 200), "url": http_url(a.get("source"))}
                     for a in _list(sources.get("articles"))[:30]],
        "rejected": [{"title": text(r.get("title"), 160), "reason": text(r.get("reason"), 200)}
                     for r in rejected[:10]],
        "rejected_total": len(rejected),
    }


def _category_en(category) -> str | None:
    """A key risk's category in English ("Pendanaan" -> "Funding"), as the
    English report tags it; None when the word has none."""
    if not isinstance(category, str) or not category.strip():
        return None
    word = category.strip()
    english = host_lang.english(word) or report_lang.label(word.lower(), "en")
    return english[:1].upper() + english[1:] if english and english.lower() != word.lower() else None


def _plan_en(value, limit):
    """An agent's English twin with its figures in English format, as the
    English report prints them; agents write the Indonesian figures as they
    stand ("12,4%", "Rp1.234,5 miliar"). Curated source English is not passed
    here: it may already write English figures."""
    return text(report_lang.plain(value), limit) if isinstance(value, str) and value.strip() else None


def _number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


# A plan row whose rationale says it is the analyst's own scenario or
# assumption ("Skenario analis: ...", "... Asumsi analis.").
_ANALYST = re.compile(r"\b(?:skenario|asumsi) analis\b", re.IGNORECASE)


def _sources(row: dict) -> dict:
    """``source_ids`` of a plan row and whether it is an analyst assumption.

    The agent cites ``official`` for the filing its anchor comes from; on a
    row whose rationale is the analyst's own scenario that tag would read as
    an official figure, so it is left out (``analyst_assumption``)."""
    ids = [text(s, 40) for s in (row.get("source_ids") or [])[:8]]
    assumed = bool(_ANALYST.search(str(row.get("rationale") or "")))
    return {"source_ids": [s for s in ids if s != "official"] if assumed else ids,
            "analyst_assumption": assumed}


# The bank model's drivers (app.bank_drivers.DRIVER_KEYS, plus deposit growth)
# with the short labels the trace table uses.
BANK_KEYS = ("loan_growth_pct", "nim_pct", "non_ii_to_nii_pct", "cost_to_income_pct",
             "cost_of_credit_pct", "deposit_growth_pct")
_BANK_LABELS = {"loan_growth_pct": ("Kredit", "Loans"), "nim_pct": ("NIM", "NIM"),
                "non_ii_to_nii_pct": ("Non-bunga/NII", "Non-interest/NII"),
                "cost_to_income_pct": ("CIR", "CIR"),
                "cost_of_credit_pct": ("Biaya kredit", "Cost of credit"),
                "deposit_growth_pct": ("DPK", "Deposits")}


def _curated_bank_rows(data: dict, source: str) -> list[dict]:
    """The driver rows of a bank driver file as the model ran them: each
    driver's value, ``kinds`` (company_guidance, sourced, analyst_assumption),
    the payout on that year's profit and the rationales, joined by driver."""
    payout = (data.get("payout_path") or {}).get("values") if isinstance(
        data.get("payout_path"), dict) else None
    payout = payout if isinstance(payout, list) else []
    rows = []
    for i, row in enumerate(_list(data.get("drivers"))[:6]):
        cells = {key: row.get(key) for key in BANK_KEYS if isinstance(row.get(key), dict)}
        parts = [(key, str(cell.get("rationale") or "").strip()) for key, cell in cells.items()]
        parts = [(key, why) for key, why in parts if why]
        english = [prose_lang.known(why) for _key, why in parts]
        refs = sorted({str(ref) for cell in cells.values() for ref in cell.get("source_refs") or []
                       if isinstance(ref, str)})
        share = _number(payout[i]) if i < len(payout) else None
        rows.append({
            "year": text(row.get("year"), 8),
            **{key: _number((cells.get(key) or {}).get("value")) for key in BANK_KEYS},
            "payout_pct": round(share * 100, 2) if share is not None else None,
            "kinds": {key: text(cell.get("kind"), 30) for key, cell in cells.items()},
            "rationale": text("; ".join(f"{_BANK_LABELS[key][0]}: {why}" for key, why in parts), 1500),
            "rationale_en": (text("; ".join(f"{_BANK_LABELS[key][1]}: {en}"
                                            for (key, _why), en in zip(parts, english)), 1500)
                             if parts and all(english) else None),
            "source_ids": [text(ref, 40) for ref in refs[:8]],
            "source": text(source, 80),
        })
    return rows


def _differ(model: list[dict], agent: list[dict]) -> bool:
    """Whether the model's driver values differ from the agent's in any year
    both tables have (or the tables cover different years)."""
    proposed = {str(r.get("year")): r for r in agent}
    shared = [r for r in model if str(r.get("year")) in proposed]
    if not shared or len(shared) != len(model):
        return True
    return any(row.get(key) is not None and proposed[str(row["year"])].get(key) != row.get(key)
               for row in shared for key in BANK_KEYS)


def _bank_model(doc: dict, agent: list[dict]) -> dict:
    """What the bank model ran, read from the report document it built.

    A sourced driver file (``data/bank_drivers/<T>.json``) replaces the
    agent's drivers in the model (``forecast._bank_scenario``); the report
    keeps the file it ran in ``model_inputs``, so the file on disk (which may
    have changed since) is never read here. Without it, the report's validated
    bank scenario rows are the model's out-years."""
    fields = {"bank_drivers_model": None, "bank_drivers_used": None, "bank_drivers_note": None,
              "bank_drivers_note_en": None, "bank_payout_rationale": None,
              "bank_payout_rationale_en": None}
    if not agent or not isinstance(doc, dict):
        return fields
    inputs = doc.get("model_inputs") if isinstance(doc.get("model_inputs"), dict) else {}
    outyears = (doc.get("forecast_assumptions") or {}).get("outyear_scenario") if isinstance(
        doc.get("forecast_assumptions"), dict) else None
    data = inputs.get("drivers") if inputs.get("kind") == "bank" else None
    if isinstance(data, dict):
        ticker = str(data.get("ticker") or (doc.get("meta") or {}).get("ticker") or "").upper()
        source = f"data/bank_drivers/{ticker}.json"
        model = _curated_bank_rows(data, source)
        reviewed = text(data.get("reviewed_at"), 20)
        where = (f"berkas driver kurasi {source}" + (f" (ditinjau {reviewed})" if reviewed else ""),
                 f"the curated driver file {source}" + (f" (reviewed {reviewed})" if reviewed else ""))
        payout = data.get("payout_path") if isinstance(data.get("payout_path"), dict) else {}
        why = str(payout.get("rationale") or "").strip()
        fields.update(bank_payout_rationale=text(why, 600) or None,
                      bank_payout_rationale_en=text(prose_lang.known(why), 600))
    elif isinstance(outyears, dict) and outyears.get("status") == "validated_bank_driver_scenario":
        model = [{"year": text(r.get("year"), 8), **{key: _number(r.get(key)) for key in BANK_KEYS},
                  "payout_pct": None, "kinds": {},
                  "rationale": text(r.get("rationale"), 1500),
                  "rationale_en": text(prose_lang.known(r.get("rationale")), 1500),
                  "source_ids": [], "source": "model"}
                 for r in _list(outyears.get("rows"))[:6]]
        where = ("driver yang tercatat di laporan", "the drivers the report records")
    else:
        return fields
    used = not _differ(model, agent)
    fields["bank_drivers_used"] = used
    if not used:
        fields.update(
            bank_drivers_model=model,
            bank_drivers_note=("Model bank tidak memakai driver usulan agent ini: neraca, laba dan "
                               f"dividen dihitung dari {where[0]}."),
            bank_drivers_note_en=("The bank model did not use the agent's proposed drivers: the "
                                  "balance sheet, earnings and dividends are computed from "
                                  f"{where[1]}."))
    else:
        fields.update(bank_payout_rationale=None, bank_payout_rationale_en=None)
    return fields


# Report out-year schedules the model builds itself, not from the agent's table
# (``valuation`` for the LoM, ``forecast`` for the Operating Model).
_SCHEDULES = {"lom_schedule": ("jadwal Life-of-Mine (LoM) tambang", "the mine's Life-of-Mine (LoM) schedule"),
              "operating_driver_model": ("Operating Model {source}", "the Operating Model {source}")}


def _outyears_model(doc: dict, agent: list[dict]) -> dict:
    """Whether the model's FY+1..FY+4 forecast is the agent's out-year table.

    A miner's forecast follows its Life-of-Mine schedule and an Operating
    Model issuer's its driver file; the agent's table then stays as proposed
    and the model's own rows (``outyears_model``) are what the report uses."""
    fields = {"outyears_used": None, "outyears_note": None, "outyears_note_en": None,
              "outyears_model": None}
    forecast = doc.get("forecast_assumptions") if isinstance(doc, dict) else None
    schedule = (forecast or {}).get("outyear_scenario") if isinstance(forecast, dict) else None
    if not agent or not isinstance(schedule, dict):
        return fields
    status = schedule.get("status")
    if status == "validated_analyst_scenario":
        fields["outyears_used"] = True
        return fields
    if status not in _SCHEDULES:
        return fields
    rows = _list(schedule.get("rows"))[:6]
    years = [r["year"] for r in rows if isinstance(r.get("year"), int)]
    span = f"FY{min(years) % 100:02d}F-FY{max(years) % 100:02d}F" if years else "tahun lanjutan"
    span_en = span if years else "out-year"
    ticker = str((doc.get("meta") or {}).get("ticker") or "").upper()
    source = f"(data/operating_drivers/{ticker}.json)" if ticker else ""
    name_id, name_en = (part.format(source=source).strip() for part in _SCHEDULES[status])
    fields.update(
        outyears_used=False,
        outyears_note=(f"Model tidak memakai tabel tahun lanjutan agent ini: forecast {span} "
                       f"mengikuti {name_id}."),
        outyears_note_en=(f"The model did not use the agent's out-year table: the {span_en} "
                          f"forecast follows {name_en}."),
        outyears_model=[{
            "year": text(r.get("year"), 8),
            **{key: _number(r.get(key)) for key in (
                "revenue_growth_pct", "ebitda_margin_pct", "net_income_margin_pct",
                "capex_to_revenue_pct")},
            "rationale": text(r.get("rationale"), 600),
            "rationale_en": text(prose_lang.known(r.get("rationale")), 600),
            "source_ids": [text(s, 40) for s in (r.get("source_ids") or [])[:8]],
        } for r in rows])
    return fields


def _forecast(result: dict, doc: dict | None = None) -> dict:
    plan = result.get("plan") if isinstance(result.get("plan"), dict) else {}
    interim = plan.get("interim_scenario") if isinstance(plan.get("interim_scenario"), dict) else {}
    scenario = plan.get("earnings_scenario") if isinstance(plan.get("earnings_scenario"), dict) else {}
    number = _number
    outyears = [{
        "year": text(r.get("year"), 8),
        "revenue_growth_pct": number(r.get("revenue_growth_pct")),
        "ebitda_margin_pct": number(r.get("ebitda_margin_pct")),
        "net_income_margin_pct": number(r.get("net_income_margin_pct")),
        "capex_to_revenue_pct": number(r.get("capex_to_revenue_pct")),
        "rationale": text(r.get("rationale"), 600),
        "rationale_en": _plan_en(r.get("rationale_en"), 600),
        **_sources(r),
    } for r in _list(plan.get("outyear_scenario"))[:6]]
    # Bank Driver Scenario (financial_ddm): the interim-year H2 drivers and
    # the four out-years the agent proposed, in percent.
    bank = [{
        "year": text(r.get("year"), 8),
        **{key: number(r.get(key)) for key in BANK_KEYS},
        "rationale": text(r.get("rationale"), 600),
        "rationale_en": _plan_en(r.get("rationale_en"), 600),
        **_sources(r),
    } for r in [scenario.get("bank_drivers")]
        + _list(plan.get("bank_outyear_scenario"))[:4] if isinstance(r, dict)]

    return {
        "status": text(result.get("status"), 60),
        "problems": [text(p, 300) for p in (result.get("problems") or [])[:8] if isinstance(p, str)],
        "problems_en": _english_list(result.get("problems"), 300, 8),
        "news_effects": [{
            "driver": text(e.get("driver"), 80), "change": text(e.get("change"), 80),
            "years": [text(y, 8) for y in (e.get("years") or [])[:6]],
            "rationale": text(e.get("rationale"), 600), "date": text(e.get("timestamp"), 30),
            "url": http_url(e.get("source_url")), "factual_basis": text(e.get("factual_basis"), 400),
            "mechanism": text(e.get("mechanism"), 400), "uncertainty": text(e.get("uncertainty"), 300),
            # English twins (#34); None for plans written before them.
            "rationale_en": _plan_en(e.get("rationale_en"), 600),
            "factual_basis_en": _plan_en(e.get("factual_basis_en"), 400),
            "mechanism_en": _plan_en(e.get("mechanism_en"), 400),
            "uncertainty_en": _plan_en(e.get("uncertainty_en"), 300),
        } for e in _list(plan.get("news_effects"))[:12]],
        # A curated rationale (data/analyst_scenarios) replaces the agent's and
        # its twin; its English, when there is one, is in data/source_text_en.
        # Curated text runs past the agent's 1400 characters: it is shown whole.
        "interim": {"rationale": text(interim.get("rationale"), 2400),
                    "rationale_en": (_plan_en(interim.get("rationale_en"), 2400)
                                     or text(prose_lang.known(interim.get("rationale")), 2400)),
                    "published_at": text(interim.get("published_at"), 30),
                    "url": http_url(interim.get("source_url"))} if interim else None,
        "outyears": outyears,
        **_outyears_model(doc, outyears),
        # Spec §5.4 key risks and the catalyst table of the earnings scenario,
        # with the agent's English twins; the category and the direction are
        # codes whose English is the report's own label.
        "key_risks": [{
            "category": text(r.get("category"), 40),
            "category_en": text(_category_en(r.get("category")), 40),
            "headline": text(r.get("headline"), 120),
            "headline_en": _plan_en(r.get("headline_en"), 120),
            "explanation": text(r.get("explanation"), 600),
            "explanation_en": _plan_en(r.get("explanation_en"), 600),
            "source_ids": [text(s, 40) for s in (r.get("source_ids") or [])[:8]],
        } for r in _list(scenario.get("key_risks"))[:8]],
        "catalysts": [{
            "item": text(c.get("item"), 160), "item_en": _plan_en(c.get("item_en"), 160),
            "timing": text(c.get("timing"), 160), "timing_en": _plan_en(c.get("timing_en"), 160),
            "driver_path": text(c.get("driver_path"), 400),
            "driver_path_en": _plan_en(c.get("driver_path_en"), 400),
            "direction": text(c.get("direction"), 20),
            "direction_en": text(host_lang.english(c.get("direction")), 20),
            "source_ids": [text(s, 40) for s in (c.get("source_ids") or [])[:8]],
        } for c in _list(scenario.get("catalysts_risks"))[:10]],
        "bank_drivers": bank,
        # What the bank model ran when it was not the agent's table.
        **_bank_model(doc, bank),
    }


_PEER_TABLE = "Perbandingan peer"
_PEER_PACK = "Grup peer: alasan pemilihan"
_PEER_SYMBOL = re.compile(r"\(([A-Z0-9.]{2,12})\)$")


def _report_peers(doc: dict) -> dict | None:
    """The peer group the report compares against, from its own exhibits:
    {group, basis, as_of, source, members}, or None when it has no peer table.

    The comparison table names each member "Name (CODE)", the issuer's row
    ends "(emiten)", and its source note reads "Sumber: <source> (<basis>);
    per <date>; ...". A curated pack also has its selection table, whose note
    reads "Sumber: data/peer_groups/<T>.json (kurasi Sektoral, <as_of>). <basis>"."""
    exhibits = _list(doc.get("exhibits")) if isinstance(doc, dict) else []
    table = next((e for e in exhibits if str(e.get("judul") or "").startswith(_PEER_TABLE)), None)
    if table is None:
        return None
    rows = ((table.get("data") or {}).get("rows") or []) if isinstance(table.get("data"), dict) else []
    members = []
    for row in rows:
        name = str(row[0]).strip() if isinstance(row, list) and row else ""
        found = _PEER_SYMBOL.search(name)
        if found and not name.endswith("(emiten)"):
            members.append(found.group(1).replace(".JK", ""))
    note = str(table.get("catatan_sumber") or "")
    listed = re.match(r"Sumber: (.+?) \((.+?)\); per (\d{4}-\d{2}-\d{2})", note)
    out = {"group": str(table["judul"])[len(_PEER_TABLE):].strip() or None,
           "source": listed.group(1) if listed else None,
           "basis": listed.group(2) if listed else None,
           "as_of": listed.group(3) if listed else None, "members": members}
    pack = next((e for e in exhibits if e.get("judul") == _PEER_PACK), None)
    curated = re.match(r"Sumber: (data/peer_groups/\S+\.json) \(kurasi Sektoral, ([^)]+)\)\. (.+)",
                       str((pack or {}).get("catatan_sumber") or ""), re.DOTALL)
    if curated:
        out.update(source=curated.group(1), as_of=curated.group(2), basis=curated.group(3).strip())
    return out


def _peer_context(intel: dict, raw: dict, doc: dict | None) -> dict:
    """The research run's peer group dated where its source has a date, and
    the report's own group when the research run used another one.

    A research run keeps the peer group it ranked against; the report is
    rebuilt later and may compare against a newer group (GMFI and POWR moved
    to IDX-only packs). ``peers_stale`` is None when the report has no peer
    table to compare."""
    raw_peers = raw.get("peers") if isinstance(raw.get("peers"), dict) else {}
    as_of = text(raw_peers.get("as_of"), 20)
    market = text(raw.get("market_date"), 20)
    peers = {**(intel.get("peers") or {}), "as_of": as_of,
             "as_of_note": None if as_of else (
                 "Sumber tabel peer riset ini tidak mencantumkan tanggal snapshot"
                 + (f"; data pasar riset per {market}." if market else ".")),
             "as_of_note_en": None if as_of else (
                 "The research run's peer table source states no snapshot date"
                 + (f"; the run's market data are as of {market}." if market else "."))}
    report = _report_peers(doc) if isinstance(doc, dict) else None
    ran = {str(m.get("symbol") or "").replace(".JK", "") for m in _list(raw_peers.get("members"))
           if not m.get("is_self")}
    stale = None if report is None or not ran else ran != set(report["members"])
    current = None
    if stale:
        group, basis = report["group"], report["basis"]
        current = {"group": text(group, 160),
                   "group_en": text(prose_lang.known(group) or host_lang.english(group), 160),
                   "basis": text(basis, 1500),
                   "basis_en": text(prose_lang.known(basis) or host_lang.english(basis), 1500),
                   "as_of": text(report["as_of"], 20), "source": text(report["source"], 200),
                   "members": [text(m, 12) for m in report["members"][:20]]}
    return {"peers": peers, "peers_stale": stale, "peers_current": current}


def _deepdive(items) -> list[dict]:
    out = []
    for item in _list(items)[:20]:
        fetched = str(item.get("fetch_status") or "") == "fetched"
        out.append({"title": text(item.get("title"), 200), "date": text(item.get("timestamp"), 30),
                    "url": http_url(item.get("source_url")), "status": text(item.get("fetch_status"), 30),
                    "length": item.get("full_length") if isinstance(item.get("full_length"), int) else 0,
                    "preview": text(item.get("full_text"), 400) if fetched else None})
    return out


def _manifest(value: object) -> dict | None:
    """Whitelisted identity for the source and rendered artifact bundle."""
    if not isinstance(value, dict):
        return None
    working = value.get("working_tree") if isinstance(value.get("working_tree"), dict) else {}
    model = value.get("model") if isinstance(value.get("model"), dict) else {}
    artifact_hashes = value.get("artifacts") if isinstance(value.get("artifacts"), dict) else {}
    source_packs = value.get("source_pack_sha256") if isinstance(
        value.get("source_pack_sha256"), dict) else {}
    cache_hashes = value.get("cache_snapshot_sha256") if isinstance(
        value.get("cache_snapshot_sha256"), dict) else {}
    policy_snapshot = value.get("release_policy") if isinstance(value.get("release_policy"), dict) else {}
    policy_body = policy_snapshot.get("policy") if isinstance(policy_snapshot.get("policy"), dict) else {}
    house_snapshot = (value.get("house_assumptions")
                      if isinstance(value.get("house_assumptions"), dict) else {})
    house_body = (house_snapshot.get("policy")
                  if isinstance(house_snapshot.get("policy"), dict) else {})
    house_rates = (house_body.get("discount_rates")
                   if isinstance(house_body.get("discount_rates"), dict) else {})

    def house_currency(code):
        source = house_rates.get(code) if isinstance(house_rates.get(code), dict) else {}
        return {key: source.get(key) for key in (
            "risk_free", "risk_free_basis", "country_risk_premium", "beta",
            "equity_risk_premium", "cost_of_debt_pretax", "cost_of_debt_basis",
            "terminal_growth", "growth_sensitivity", "rate_sensitivity")}

    artifacts = {text(kind, 20): {
        "file": text(row.get("file"), 80), "sha256": text(row.get("sha256"), 64),
    } for kind, row in artifact_hashes.items() if isinstance(row, dict)}
    return {
        "publication_id": text(value.get("publication_id"), 64),
        "code_revision": text(value.get("code_revision"), 40),
        "source_tree_sha256": text(value.get("source_tree_sha256"), 64),
        "working_tree": {"dirty": working.get("dirty") if isinstance(
            working.get("dirty"), bool) else None,
            "sha256": text(working.get("sha256"), 64)},
        "as_of": text(value.get("as_of"), 20),
        "profile": text(value.get("profile"), 40),
        "forecast_basis": text(value.get("forecast_basis"), 50),
        "production_ready": value.get("production_ready") if isinstance(
            value.get("production_ready"), bool) else None,
        "model": {"forecast_agent": text(model.get("forecast_agent"), 100),
                  "agent_effort": text(model.get("agent_effort"), 40),
                  "schema_version": model.get("schema_version") if isinstance(
                      model.get("schema_version"), int) else None},
        "spec_sha256": text(value.get("spec_sha256"), 64),
        "evidence_register_sha256": text(value.get("evidence_register_sha256"), 64),
        "source_text_en_sha256": text(value.get("source_text_en_sha256"), 64),
        "release_policy": {
            "version": text(policy_body.get("version"), 24),
            "effective_date": text(policy_body.get("effective_date"), 20),
            "status": text(policy_body.get("status"), 40),
            "sha256": text(policy_snapshot.get("sha256"), 64),
            "ambiguities": [text(item.get("id"), 80) for item in
                            (policy_body.get("ambiguities") or [])[:16]
                            if isinstance(item, dict)],
        } if policy_body else None,
        "house_assumptions": {
            "version": text(house_body.get("version"), 24),
            "documented_as_of": text(house_body.get("documented_as_of"), 20),
            "effective_from": text(house_body.get("effective_from"), 20),
            "status": text(house_body.get("status"), 40),
            "sha256": text(house_snapshot.get("sha256"), 64),
            "idr": house_currency("IDR"),
            "usd": house_currency("USD"),
            "unresolved": [text(item, 240) for item in (house_body.get("unresolved") or [])[:8]
                           if isinstance(item, str)],
        } if house_body else None,
        "source_pack_sha256": {text(path, 120): text(digest, 64) for path, digest
                                in source_packs.items()
                                if isinstance(path, str) and isinstance(digest, str)},
        "cache_snapshot_sha256": {text(endpoint, 180): {
            "cache_key": text(row.get("cache_key"), 180),
            "content_sha256": text(row.get("content_sha256"), 64),
        } for endpoint, row in cache_hashes.items()
                                  if isinstance(row, dict)},
        "artifacts": artifacts,
        "missing_artifacts": [text(kind, 20) for kind in
                              (value.get("missing_artifacts") or [])[:4]],
    }


def build(audit: dict | None, doc: dict | None = None) -> dict | None:
    """The browser-safe trace, or None when ``audit`` is not a trace.

    ``doc``, the report document the trace belongs to, says what the model
    ran where it differs from the agents' proposals (bank drivers, out-year
    schedules) and which peer group the report compares against."""
    if not isinstance(audit, dict) or not audit.get("ticker"):
        return None
    analyst = audit.get("analyst") if isinstance(audit.get("analyst"), dict) else {}
    intel = public_intel(analyst)
    if intel is not None:
        intel.update(_peer_context(intel, analyst, doc))
    return {
        "ticker": text(audit.get("ticker"), 12),
        "report": _status(audit.get("report") if isinstance(audit.get("report"), dict) else {}),
        "analyst": intel,
        "analyst_problems": [text(p, 300) for p in (analyst.get("problems") or [])[:6] if isinstance(p, str)],
        "analyst_problems_en": _english_list(analyst.get("problems"), 300, 6),
        # The analyst records structured notes since #34; older runs are parsed.
        "analyst_problem_notes": _english_notes(
            analyst["problem_notes"] if isinstance(analyst.get("problem_notes"), list)
            and len(analyst["problem_notes"])
            == sum(isinstance(p, str) for p in analyst.get("problems") or [])
            else problem_notes(analyst.get("problems"))),
        "research": _research(audit.get("research") if isinstance(audit.get("research"), dict) else {}),
        "news": _news(audit.get("news_sources") if isinstance(audit.get("news_sources"), dict) else {}),
        "forecast": _forecast(audit.get("forecast_assumptions")
                              if isinstance(audit.get("forecast_assumptions"), dict) else {},
                              doc if isinstance(doc, dict) else None),
        "run_manifest": _manifest(audit.get("run_manifest")),
        "deepdive": _deepdive(audit.get("news_deepdive")),
    }
