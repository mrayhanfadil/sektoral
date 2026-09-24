"""Planning analyst agent: plan → choose tools → rank against peers → conclude.

The model writes a research plan with hypotheses, then decides tool calls turn
by turn after seeing each result (it may deviate from its plan). Tools read the
local Sectors data and return deterministic signals. The model's conclusions
must cite signal ids; numbers are shown from the signals, never from prose.
Every stage has a labelled host fallback so a run always finishes honestly.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from agents.estimator.run import _chat, _parse_json, _response_text
from app.progress import emit

from . import memory, signals as S, tools

MAX_TOOL_CALLS = 7
MAX_TURNS = 4
MAX_CALLS_PER_TURN = 3
VERDICTS = ("didukung", "tidak didukung", "belum terjawab")
_ADVICE = re.compile(r"\b(beli|jual|buy|sell|hold|akumulasi|target harga|rekomendasi|"
                     r"undervalued|overvalued|saran investasi)\b", re.I)
# Market-flow descriptions ("jual bersih asing", "aksi beli") describe what
# investors did; they are not advice and are removed before the advice check.
_FLOW_PHRASES = re.compile(
    r"\b(?:(?:aksi|tekanan|net|posisi)\s+(?:beli|jual|buy|sell)|"
    r"(?:beli|jual|buy|sell)(?:\s+bersih|\s+asing|\s+neto|ing))\b", re.I)
_DIGIT = re.compile(r"\S*\d\S*")
# Valuation verdicts that read as a call to act rather than a comparison.
_JUDGEMENT = re.compile(r"\b(?:valuasi\s+(?:\w+\s+){0,2}menarik|layak\s+(?:dibeli|dikoleksi|dimiliki)|"
                        r"peluang\s+(?:beli|masuk)|titik\s+masuk|entry\s+point)\b", re.I)


# Reasoning models occasionally leak CJK tokens into Indonesian prose.
_FOREIGN_SCRIPT = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af\uff00-\uffef]+")


def _clean(text, limit=200):
    return re.sub(r"\s{2,}", " ", _FOREIGN_SCRIPT.sub(" ", str(text or ""))).strip()[:limit]


def _advice_terms(text):
    cleaned = _FLOW_PHRASES.sub(" ", text)
    return sorted({m.group(0).lower() for m in _ADVICE.finditer(cleaned)} |
                  {m.group(0).lower() for m in _JUDGEMENT.finditer(cleaned)})

SYSTEM = (
    "Kamu analis riset ekuitas Indonesia yang bekerja dengan tool milik host. "
    "Tool Sectors membaca data Sectors lokal untuk satu emiten; web_news (jika tersedia) hanya memberi judul berita web bertanggal sebagai konteks, bukan sumber angka. "
    "Tugasmu: merencanakan pemeriksaan, memilih tool, lalu menyimpulkan posisi emiten "
    "terhadap peer dan perubahan terbarunya. Ini materi informasi, bukan saran investasi: "
    "jangan pernah menulis beli, jual, tahan, akumulasi, target harga, rekomendasi, "
    "undervalued atau overvalued. Selalu balas dengan satu object JSON saja."
)


def _tool_menu(available):
    lines = []
    for name, (description, args) in tools.TOOLS.items():
        state = "tersedia" if available.get(name) else "TIDAK tersedia untuk emiten ini"
        lines.append(f"- {name} args {args}: {description} ({state})")
    return "\n".join(lines)


def _memory_brief(previous):
    if not previous:
        return "Belum ada riset sebelumnya untuk emiten ini."
    flagged = [f"{v.get('label')}: {v.get('flag')}"
               for v in (previous.get("signals") or {}).values() if v.get("flag")]
    return ("Riset sebelumnya " + str(previous.get("run_at") or "")[:10] +
            f" (data pasar {previous.get('market_date')}). Pertanyaan: {previous.get('question')}. "
            "Temuan: " + "; ".join(previous.get("findings") or ["-"]) +
            ". Sinyal bertanda: " + ("; ".join(flagged) or "-") +
            ". Periksa apakah temuan itu masih berlaku.")


def _call(chat, messages):
    raw, _ = _response_text(chat(messages))
    return raw, _parse_json(raw)


# ------------------------------------------------------------------ plan

def _plan_problems(plan, available):
    problems = []
    if not isinstance(plan, dict):
        return ["plan harus object"]
    if not isinstance(plan.get("question"), str) or not plan["question"].strip():
        problems.append("question wajib berupa teks")
    hypotheses = plan.get("hypotheses")
    if not isinstance(hypotheses, list) or not 1 <= len(hypotheses) <= 4 or \
            not all(isinstance(h, str) and h.strip() for h in hypotheses):
        problems.append("hypotheses harus 1-4 teks")
    steps = plan.get("steps")
    if not isinstance(steps, list) or not 2 <= len(steps) <= MAX_TOOL_CALLS:
        problems.append(f"steps harus 2-{MAX_TOOL_CALLS} langkah")
        steps = []
    for index, step in enumerate(steps):
        name = step.get("tool") if isinstance(step, dict) else None
        args = step.get("args", {}) if isinstance(step, dict) else None
        if not isinstance(name, str) or name not in tools.TOOLS:
            problems.append(f"steps[{index}]: tool {name!r} tidak dikenal")
        elif not isinstance(args, dict):
            problems.append(f"steps[{index}]: args harus object")
        elif not available.get(name):
            problems.append(f"steps[{index}]: {name} tidak tersedia untuk emiten ini")
        elif name == "rank_peers":
            metrics = args.get("metrics")
            if not isinstance(metrics, list) or not metrics or any(
                    not isinstance(m, str) or m not in S.PEER_METRICS for m in metrics):
                problems.append(f"steps[{index}]: metrics harus list dari {list(S.PEER_METRICS)}")
    text = " ".join([str(plan.get("question") or "")] + [str(h) for h in hypotheses or []])
    if _advice_terms(text):
        problems.append("plan memuat bahasa rekomendasi investasi: " + ", ".join(_advice_terms(text)))
    if _FOREIGN_SCRIPT.search(text):
        problems.append("tulis rencana dalam bahasa Indonesia saja; hapus: " +
                        ", ".join(_FOREIGN_SCRIPT.findall(text)[:5]))
    return problems


def _fallback_plan(available):
    steps = [{"tool": name, "args": {"metrics": list(S.DEFAULT_PEER_METRICS)}
              if name == "rank_peers" else {}, "why": "langkah standar host"}
             for name in tools.TOOLS if available.get(name)]
    return {"question": "Bagaimana posisi emiten terhadap peer dan apa yang berubah belakangan ini?",
            "hypotheses": ["Profitabilitas emiten berbeda dari median peer.",
                           "Pergerakan harga terbaru sejalan dengan arus investor asing."],
            "steps": steps[:MAX_TOOL_CALLS], "source": "host_fallback"}


def _make_plan(chat, ticker, info, previous, problems):
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": (
        f"Emiten: {ticker} — {info['name']}. Sektor: {info.get('sector')}; sub-sektor: "
        f"{info.get('sub_sector')}; sub-industri: {info.get('sub_industry')}. "
        f"Tanggal data pasar: {info.get('market_date')}.\n"
        f"Memori: {_memory_brief(previous)}\n\nTool:\n{_tool_menu(info['available'])}\n\n"
        "Susun rencana riset yang spesifik untuk jenis usaha emiten ini (misalnya bank dinilai "
        "lewat ROE dan P/B, penambang lewat margin dan leverage). Balas JSON: "
        '{"question": "pertanyaan riset utama", "hypotheses": ["hipotesis yang bisa diuji", ...], '
        '"steps": [{"tool": "nama", "args": {...}, "why": "alasan singkat"}, ...]}. '
        f"Dua sampai empat hipotesis. Gunakan hanya tool yang tersedia; maksimal "
        f"{MAX_TOOL_CALLS} langkah.")}]
    for attempt in range(2):
        try:
            raw, plan = _call(chat, messages)
        except Exception as error:  # provider/network/JSON failure
            problems.append(f"plan: {type(error).__name__}: {str(error)[:160]}")
            break
        found = _plan_problems(plan, info["available"])
        if not found:
            plan = {"question": plan["question"].strip()[:300],
                    "hypotheses": [h.strip()[:240] for h in plan["hypotheses"]],
                    "steps": [{"tool": s["tool"], "args": s.get("args") or {},
                               "why": _clean(s.get("why"))} for s in plan["steps"]],
                    "source": "agent"}
            return plan, messages + [{"role": "assistant", "content": raw[:6000]}]
        problems.append("plan ditolak: " + "; ".join(found[:4]))
        messages = messages + [{"role": "assistant", "content": raw[:6000]}, {
            "role": "user", "content": "Perbaiki rencana. Masalah: " + json.dumps(found) +
            ". Kembalikan object rencana lengkap."}]
    return _fallback_plan(info["available"]), None


# --------------------------------------------------------------- execute

def _run_tool(ticker, name, args, why, origin, state, steps, all_signals):
    step = {"n": len(steps) + 1, "tool": name, "args": args, "why": why, "origin": origin}
    emit("tool", f"Menjalankan {name}", why, status="run", tool=name)
    try:
        result, found = tools.execute(name, ticker, args, state)
    except tools.ToolError as error:
        step.update(status="error", summary=str(error))
        steps.append(step)
        emit("tool", f"{name}: data tidak tersedia", str(error), status="warn", tool=name)
        return {"tool": name, "error": str(error)}
    known = {s["id"] for s in all_signals}
    fresh = [s for s in found if s["id"] not in known]
    all_signals.extend(fresh)
    flagged = [s for s in found if s.get("flag")]
    summary = f"{len(found)} sinyal" + (f", {len(flagged)} bertanda: " +
                                        ", ".join(s["flag"] for s in flagged[:3]) if flagged else "")
    if name == "find_peers":
        summary = f"{len(state['peers']['rows'])} emiten · {state['peers']['basis']}"
    elif name == "news":
        summary = f"{len(state.get('news') or [])} berita bertanggal"
    step.update(status="ok", summary=summary)
    steps.append(step)
    emit("tool", f"{name} selesai", summary, tool=name)
    return {"tool": name, "result": result}


def _execute(chat, ticker, plan, messages, available, problems):
    state, steps, all_signals = {}, [], []
    done = set()

    def key(name, args):
        return name + json.dumps(args or {}, sort_keys=True)

    def run_step(name, args, why, origin):
        done.add(key(name, args))
        return _run_tool(ticker, name, args, why, origin, state, steps, all_signals)

    turns = 0
    if messages is not None:
        messages = messages + [{"role": "user", "content": (
            "Jalankan riset. Setiap giliran balas {\"calls\": [{\"tool\": ..., \"args\": {...}, "
            f"\"why\": ...}}]}} (maksimal {MAX_CALLS_PER_TURN} panggilan) atau "
            "{\"done\": true, \"why\": \"...\"} bila bukti sudah cukup. Kamu boleh menyimpang "
            "dari rencana jika hasil sebelumnya menunjukkan hal lain yang perlu dicek.")}]
    while messages is not None and turns < MAX_TURNS and len(steps) < MAX_TOOL_CALLS:
        turns += 1
        try:
            raw, action = _call(chat, messages)
        except Exception as error:
            problems.append(f"eksekusi: {type(error).__name__}: {str(error)[:160]}")
            break
        messages.append({"role": "assistant", "content": raw[:4000]})
        if action.get("done"):
            emit("tool", "Agent menilai bukti sudah cukup", _clean(action.get("why")))
            break
        calls = action.get("calls") if isinstance(action.get("calls"), list) else []
        if not calls:
            problems.append("eksekusi: respons tanpa calls atau done")
            break
        results = []
        for call in calls[:MAX_CALLS_PER_TURN]:
            if len(steps) >= MAX_TOOL_CALLS:
                break
            if not isinstance(call, dict):
                results.append({"error": "setiap panggilan harus object {tool, args, why}"})
                continue
            name = call.get("tool")
            args = call.get("args") if isinstance(call.get("args"), dict) else {}
            why = _clean(call.get("why"))
            if not isinstance(name, str) or name not in tools.TOOLS or not available.get(name):
                results.append({"tool": name, "error": "tool tidak dikenal atau tidak tersedia"})
                continue
            if key(name, args) in done:
                results.append({"tool": name, "error": "sudah dijalankan dengan argumen sama"})
                continue
            planned = any(s["tool"] == name for s in plan["steps"])
            results.append(run_step(name, args, why, "agent" if planned else "agent_adaptive"))
        remaining = MAX_TOOL_CALLS - len(steps)
        messages.append({"role": "user", "content": json.dumps(
            {"tool_results": results, "remaining_calls": remaining}, ensure_ascii=False)[:12000]})
    # Planned steps the agent never reached still run, marked as host-executed,
    # so the peer view and signals are complete even when the loop stops early.
    for step in plan["steps"]:
        if len(steps) >= MAX_TOOL_CALLS + 2:
            break
        if key(step["tool"], step.get("args")) not in done and not any(
                s["tool"] == step["tool"] for s in steps):
            run_step(step["tool"], step.get("args") or {}, step.get("why") or "", "host")
    all_signals.extend(s for s in S.cross_signals(all_signals)
                       if s["id"] not in {x["id"] for x in all_signals})
    return state, steps, all_signals


# ------------------------------------------------------------ synthesize

def _known_ids(ids, signal_ids):
    """A non-empty list of signal id strings that all exist."""
    return (isinstance(ids, list) and bool(ids) and
            all(isinstance(x, str) and x in signal_ids for x in ids))


def _synthesis_problems(doc, signal_ids, n_hypotheses):
    problems = []
    if not isinstance(doc, dict):
        return ["synthesis harus object"]
    findings = doc.get("findings")
    if not isinstance(findings, list) or not 1 <= len(findings) <= 4:
        problems.append("findings harus 1-4 item")
        findings = []
    prose = [doc.get("headline")]
    for i, item in enumerate(findings):
        if not isinstance(item, dict):
            problems.append(f"findings[{i}] harus object")
            continue
        ids = item.get("signal_ids") or []
        if not _known_ids(ids, signal_ids):
            problems.append(f"findings[{i}].signal_ids harus list id sinyal yang ada")
        elif all(str(x).startswith("web.") for x in ids):
            problems.append(f"findings[{i}] wajib mengutip minimal satu sinyal Sectors; "
                            "berita web hanya konteks")
        prose += [item.get("title"), item.get("interpretation"), item.get("caveat")]
    verdicts = doc.get("hypotheses") or []
    if not isinstance(verdicts, list):
        problems.append("hypotheses harus list")
        verdicts = []
    for i, item in enumerate(verdicts):
        if not isinstance(item, dict) or not isinstance(item.get("index"), int) or \
                not 0 <= item["index"] < n_hypotheses:
            problems.append(f"hypotheses[{i}].index tidak valid")
            continue
        if item.get("verdict") not in VERDICTS:
            problems.append(f"hypotheses[{i}].verdict harus salah satu {VERDICTS}")
        ids = item.get("signal_ids") or []
        if ids and not _known_ids(ids, signal_ids):
            problems.append(f"hypotheses[{i}].signal_ids harus list id sinyal yang ada")
        elif item.get("verdict") != "belum terjawab" and not ids:
            problems.append(f"hypotheses[{i}] perlu signal_ids yang ada untuk verdict ini")
        elif item.get("verdict") != "belum terjawab" and all(str(x).startswith("web.") for x in ids):
            problems.append(f"hypotheses[{i}] wajib didukung sinyal Sectors, bukan hanya berita web")
        prose.append(item.get("reason"))
    for text in prose:
        if not isinstance(text, str) or not text.strip():
            problems.append("headline, title, interpretation, caveat dan reason wajib diisi")
            break
    joined = " ".join(t for t in prose if isinstance(t, str))
    numbers = sorted(set(_DIGIT.findall(joined)))
    if numbers:
        problems.append("prosa tidak boleh memuat angka (angka ditampilkan dari sinyal yang "
                        "dicite); hapus: " + ", ".join(numbers[:8]))
    if _advice_terms(joined):
        problems.append("prosa memuat bahasa rekomendasi investasi; hapus kata: " +
                        ", ".join(_advice_terms(joined)))
    if _FOREIGN_SCRIPT.search(joined):
        problems.append("tulis dalam bahasa Indonesia saja; hapus: " +
                        ", ".join(_FOREIGN_SCRIPT.findall(joined)[:5]))
    return problems


def _fallback_synthesis(all_signals, hypotheses):
    flagged = [s for s in all_signals if s.get("flag")][:3]
    findings = [{"title": f"{s['label']}: {s['flag']}", "signal_ids": [s["id"]],
                 "interpretation": "Sinyal ini ditandai aturan host; belum ada tafsir agent.",
                 "caveat": "Perlu dibaca bersama konteks usaha emiten."} for s in flagged]
    return {"headline": "Ringkasan sinyal yang ditandai host",
            "findings": findings,
            "hypotheses": [{"index": i, "verdict": "belum terjawab", "signal_ids": [],
                            "reason": "Agent tidak menyelesaikan penilaian hipotesis."}
                           for i in range(len(hypotheses))],
            "next_checks": [], "source": "host_fallback"}


def _synthesize(chat, ticker, plan, all_signals, headlines, changes, problems):
    briefs = [tools._brief(s) for s in all_signals]
    if not briefs:
        return _fallback_synthesis(all_signals, plan["hypotheses"])
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": (
        f"Emiten {ticker}. Pertanyaan: {plan['question']}\nHipotesis (index mulai 0): " +
        json.dumps(plan["hypotheses"], ensure_ascii=False) +
        "\nSinyal hasil tool: " + json.dumps(briefs, ensure_ascii=False) +
        "\nJudul berita: " + json.dumps([h["title"] for h in headlines], ensure_ascii=False) +
        "\nPerubahan sejak riset terakhir: " + json.dumps(changes.get("items") or [], ensure_ascii=False) +
        "\n\nSimpulkan. Aturan: prosa TANPA angka (angka ditampilkan host dari sinyal yang kamu "
        "cite); cite id sinyal persis; bedakan fakta dari tafsir; tanpa bahasa rekomendasi. "
        "Sinyal web.* adalah berita web: boleh dikutip sebagai konteks penjelas, tetapi setiap "
        "temuan dan verdict wajib juga mengutip sinyal Sectors. "
        "Balas JSON: {\"headline\": \"satu kalimat\", \"findings\": [{\"title\": ..., "
        "\"signal_ids\": [...], \"interpretation\": ..., \"caveat\": \"batas bukti\"}], "
        "\"hypotheses\": [{\"index\": 0, \"verdict\": \"didukung|tidak didukung|belum terjawab\", "
        "\"signal_ids\": [...], \"reason\": ...}], \"next_checks\": [\"pemeriksaan lanjutan\"]}. "
        "Maksimal empat findings.")}]
    ids = {s["id"] for s in all_signals}
    for attempt in range(2):
        try:
            raw, doc = _call(chat, messages)
        except Exception as error:
            problems.append(f"sintesis: {type(error).__name__}: {str(error)[:160]}")
            break
        found = _synthesis_problems(doc, ids, len(plan["hypotheses"]))
        if not found:
            doc["next_checks"] = [str(x)[:200] for x in (doc.get("next_checks") or [])
                                  if isinstance(x, str) and not _advice_terms(x)][:3]
            doc["source"] = "agent"
            return doc
        problems.append("sintesis ditolak: " + "; ".join(found[:4]))
        emit("synthesis", "Validator menolak draf kesimpulan", "; ".join(found[:2]), status="warn")
        messages = messages + [{"role": "assistant", "content": raw[:6000]}, {
            "role": "user", "content": "Perbaiki. Masalah: " + json.dumps(found) +
            ". Kembalikan object lengkap."}]
    return _fallback_synthesis(all_signals, plan["hypotheses"])


# -------------------------------------------------------------------- run

def run(ticker, *, chat=None, memory_dir=None, persist=True):
    """Run the analyst agent for one ticker. Never raises on LLM failure."""
    ticker = str(ticker).strip().upper()
    chat = chat or _chat
    problems = []
    info = tools.overview(ticker)
    previous = memory.latest(ticker, memory_dir)
    emit("memory", "Membaca memori riset",
         f"riset terakhir {str(previous.get('run_at'))[:10]}" if previous else "belum ada riset sebelumnya")

    emit("plan", "Agent menyusun rencana riset", status="run")
    plan, messages = _make_plan(chat, ticker, info, previous, problems)
    emit("plan", "Rencana siap" if plan["source"] == "agent" else "Rencana standar host dipakai",
         plan["question"], status="ok" if plan["source"] == "agent" else "warn")

    state, steps, all_signals = _execute(chat, ticker, plan, messages, info["available"], problems)
    flagged = sum(1 for s in all_signals if s.get("flag"))
    emit("signals", f"{len(all_signals)} sinyal dihitung, {flagged} bertanda")

    headlines = state.get("news") or []
    web_news = state.get("web_news") or []
    run_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    draft = {"run_at": run_at, "market_date": info.get("market_date"), "plan": plan,
             "signals": all_signals, "headlines": headlines + web_news, "synthesis": {}}
    changes = memory.diff(previous, memory.snapshot(draft))

    emit("synthesis", "Agent menguji hipotesis dan menulis temuan", status="run")
    synthesis = _synthesize(chat, ticker, plan, all_signals, headlines, changes, problems)
    emit("synthesis", "Temuan tervalidasi" if synthesis["source"] == "agent"
         else "Ringkasan host dipakai", synthesis.get("headline"),
         status="ok" if synthesis["source"] == "agent" else "warn")

    peers = state.get("peers") or {}
    result = {
        "ticker": ticker, "name": info["name"], "market_date": info.get("market_date"),
        "run_at": run_at, "plan": plan, "steps": steps, "signals": all_signals,
        "peers": {"basis": peers.get("basis"), "group": peers.get("group"),
                  "source": peers.get("source"),
                  "members": [{"symbol": r["symbol"], "name": r["name"], "is_self": r["is_self"]}
                              for r in peers.get("rows") or []]},
        "headlines": headlines, "synthesis": synthesis, "changes": changes,
        "web_news": {"window": state.get("web_window"), "items": web_news},
        "status": "ok" if plan["source"] == "agent" and synthesis["source"] == "agent" else "partial",
        "problems": problems,
    }
    if persist:
        memory.save(ticker, result, memory_dir)
    emit("memory", "Memori riset diperbarui" if persist else "Memori tidak disimpan")
    return result
