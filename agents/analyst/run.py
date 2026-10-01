"""Planning analyst agent: plan → choose tools → rank against peers → conclude.

The model writes a research plan with hypotheses, then decides tool calls turn
by turn after seeing each result (it may deviate from its plan). Tools read the
local Sectors data and return deterministic signals. The model's conclusions
must cite signal ids; numbers are shown from the signals, never from prose.
Every stage has a labelled host fallback so a run always finishes honestly.

The model writes each prose field in Indonesian and, in the same reply, an
English twin beside it (``question_en``, ``hypotheses_en``, ``why_en``,
``headline_en``, ``title_en``, ``interpretation_en``, ``caveat_en``,
``reason_en``, ``next_checks_en``). The twin cites the same signals and passes
the same rules, and must read English. A twin that is still missing or invalid
after the repair attempt is dropped, never failing the run: readers then see
the Indonesian for that field.

A result stored before the agent wrote twins gets them afterwards from
``translate_intel`` (``app.rebuild --translate-analyst``), in calls of their
own checked by the same rules; no Indonesian value changes.
"""
from __future__ import annotations

import copy
import json
import re
from datetime import datetime, timezone

from agents.estimator.run import _chat, _parse_json, _response_text
from app import prose_lang
from app.progress import emit

from . import memory, signals as S, tools

MAX_TOOL_CALLS = 7
MAX_TURNS = 4
MAX_CALLS_PER_TURN = 3
VERDICTS = ("didukung", "tidak didukung", "belum terjawab")
# Stable codes for the verdicts, for readers that do not match Indonesian words.
VERDICT_CODES = {"didukung": "supported", "tidak didukung": "not_supported",
                 "belum terjawab": "unanswered"}
# Advice means telling the reader to act, not describing what investors did:
# "asing mencatat beli bersih" is a market fact, "layak dibeli" is advice.
_ADVICE = re.compile(
    r"\b(?:target\s+harga|rekomendasi|undervalued|overvalued|saran\s+investasi|akumulasi|"
    r"buy|sell|hold|accumulate|trading\s+buy|"
    r"(?:rating|peringkat)\s+(?:beli|jual|tahan)|"
    r"(?:sebaiknya|disarankan|direkomendasikan|layak|patut|saatnya|waktunya|segera|silakan)\s+"
    r"(?:di)?(?:beli|jual|tahan|lepas|koleksi|akumulasi|masuk|keluar))\b", re.I)
# Market-flow descriptions ("net sell", "aksi beli") are removed before the check.
_FLOW_PHRASES = re.compile(
    r"\b(?:(?:aksi|tekanan|net|posisi)\s+(?:beli|jual|buy|sell)|"
    r"(?:buy|sell)(?:\s+bersih|\s+asing|\s+neto|ing|-off|back)|"
    # "akumulasi asing", "pola akumulasi": what investors did, not a call to act.
    r"(?:akumulasi|distribusi)\s+(?:oleh\s+)?(?:asing|investor|institusi|domestik|lokal|"
    r"bersih|dana|bandar)|"
    r"(?:aksi|pola|fase|tren|tanda|sinyal|periode)\s+(?:akumulasi|distribusi))\b", re.I)
_DIGIT = re.compile(r"\S*\d\S*")
# Dates, years and period labels are references, not figures: "2026",
# "2026-09-22", "1H26", "FY2025", "Q2".
_DATE_TOKEN = re.compile(
    r"^(?:(?:19|20)\d{2}(?:-\d{2}(?:-\d{2})?)?|\d{1,2}[HQ]\d{2,4}|[HQ][1-4](?:\d{2,4})?|"
    r"FY\d{2,4}[AF]?|\d[HQ])$", re.I)
# Verdict spellings the model uses for the three the host accepts.
_VERDICT_ALIASES = {
    "didukung": "didukung", "terdukung": "didukung", "terkonfirmasi": "didukung",
    "tidak didukung": "tidak didukung", "tidak terdukung": "tidak didukung",
    "ditolak": "tidak didukung", "terbantah": "tidak didukung",
    "belum terjawab": "belum terjawab", "belum dapat disimpulkan": "belum terjawab",
    "inkonklusif": "belum terjawab", "tidak dapat disimpulkan": "belum terjawab"}
_PARTIAL = re.compile(r"^(?:sebagian\s+didukung|didukung\s+sebagian|didukung\s+parsial)$", re.I)
# Valuation verdicts that read as a call to act rather than a comparison.
_JUDGEMENT = re.compile(r"\b(?:valuasi\s+(?:\w+\s+){0,2}menarik|layak\s+(?:dibeli|dikoleksi|dimiliki)|"
                        r"peluang\s+(?:beli|masuk)|titik\s+masuk|entry\s+point)\b", re.I)
# The same calls to act as English phrases, checked on the English twins only.
_ADVICE_EN = re.compile(
    r"\b(?:price\s+target|target\s+price|recommend\w*|investment\s+advice|buying\s+opportunity|"
    r"(?:should|worth|time\s+to)\s+(?:buy|sell|hold|accumulate|exit)|"
    r"attractive(?:ly)?\s+valu\w*|valuation\s+(?:\w+\s+){0,2}attractive)\b", re.I)


# Reasoning models occasionally leak CJK tokens into Indonesian prose.
_FOREIGN_SCRIPT = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af\uff00-\uffef]+")


def _clean(text, limit=200):
    text = re.sub(r"\s{2,}", " ", _FOREIGN_SCRIPT.sub(" ", str(text or ""))).strip()
    if len(text) <= limit:
        return text
    # Shown to readers: end on a whole word, never mid-word.
    return text[:limit - 1].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"


def _advice_terms(text):
    cleaned = _FLOW_PHRASES.sub(" ", text)
    return sorted({m.group(0).lower() for m in _ADVICE.finditer(cleaned)} |
                  {m.group(0).lower() for m in _JUDGEMENT.finditer(cleaned)})


def _advice_terms_en(text):
    cleaned = _FLOW_PHRASES.sub(" ", text)
    return sorted(set(_advice_terms(text)) | {m.group(0).lower() for m in _ADVICE_EN.finditer(cleaned)})


class _Note(str):
    """A validator note as today's text, keeping its parts for ``problem_notes``:
    ``message`` without the list of words to remove, and that list as ``removed``."""

    def __new__(cls, text, message=None, removed=()):
        note = super().__new__(cls, text)
        note.message = text if message is None else message
        note.removed = list(dict.fromkeys(removed))
        return note


def _removal(message, marker, removed):
    """``"<message>; <marker>: a, b"``, the wording the model is repaired with."""
    return _Note(f"{message}; {marker}: " + ", ".join(removed), message, removed)


def _joined(prefix, found):
    """One problem line from a prefix and validator notes, as ``prefix + "; ".join(found)``."""
    return _Note(prefix + "; ".join(found),
                 prefix + "; ".join(getattr(f, "message", f) for f in found),
                 [word for f in found for word in getattr(f, "removed", ())])


def problem_notes(problems):
    """``[{message, removed}]`` for each problem line, in the same order."""
    return [{"message": str(getattr(p, "message", p)), "removed": list(getattr(p, "removed", []))}
            for p in problems]


def _invented_numbers(text, signal_ids, label_numbers):
    """Figures in prose that are not a signal id, a date or part of a signal label."""
    # Signal ids ("flow.net_20d") and numbers that are part of a signal's
    # label ("20 sesi") are references, not figures the model invented.
    for signal_id in sorted(signal_ids, key=len, reverse=True):
        text = text.replace(signal_id, " ")
    tokens = {re.sub(r"^[^\w+−-]+|[^\w%]+$", "", token) for token in _DIGIT.findall(text)}
    return sorted(token for token in tokens
                  if token and not _DATE_TOKEN.match(token)
                  and re.sub(r"\D", "", token) not in label_numbers)


def _english_note(text, id_text=None, *, signal_ids=None, label_numbers=frozenset()):
    """Why `text` cannot stand as the English twin of `id_text`, or None.

    With `signal_ids` the prose may hold no numbers at all (conclusions);
    otherwise it states exactly the figures of its Indonesian twin."""
    if not isinstance(text, str) or not text.strip():
        return "teks bahasa Inggris wajib diisi"
    if signal_ids is not None:
        numbers = _invented_numbers(text, signal_ids, label_numbers)
        if numbers:
            return _removal("prosa tidak boleh memuat angka (angka ditampilkan dari sinyal yang "
                            "dicite)", "hapus", numbers[:8])
    elif prose_lang.figures(id_text) != prose_lang.figures(text):
        return "angka harus sama persis dengan teks Indonesia"
    if _advice_terms_en(text):
        return _removal("prosa memuat bahasa rekomendasi investasi", "hapus kata",
                        _advice_terms_en(text))
    if _FOREIGN_SCRIPT.search(text):
        return _removal("tulis dalam bahasa Inggris saja", "hapus",
                        _FOREIGN_SCRIPT.findall(text)[:5])
    if not prose_lang.reads_english(text):
        return "teks bahasa Inggris masih memuat kalimat bahasa Indonesia"
    return None


def _drop_english(stage, found, problems):
    """Remove the English twins that failed and note it; the Indonesian stays."""
    for holder, key, _path, _note in found:
        holder.pop(key, None)
    if found:
        problems.append(_joined(f"{stage}: teks Inggris dibuang, bahasa Indonesia dipakai: ",
                                [_path_note(path, note) for _h, _k, path, note in found[:4]]))


def _path_note(path, note):
    return _Note(f"{path}: {note}", f"{path}: {getattr(note, 'message', note)}",
                 getattr(note, "removed", ()))

SYSTEM = (
    "Kamu analis riset ekuitas Indonesia yang bekerja dengan tool milik host. "
    "Tool Sectors membaca data Sectors lokal untuk satu emiten; web_news (jika tersedia) hanya memberi judul berita web bertanggal sebagai konteks, bukan sumber angka. "
    "Tugasmu: merencanakan pemeriksaan, memilih tool, lalu menyimpulkan posisi emiten "
    "terhadap peer dan perubahan terbarunya. Ini materi informasi, bukan saran investasi: "
    "jangan menyuruh pembaca membeli, menjual atau menahan saham, dan jangan menulis target "
    "harga, rekomendasi, undervalued atau overvalued. Menjelaskan aksi investor (misalnya "
    "asing mencatat beli bersih) boleh. Selalu balas dengan satu object JSON saja."
)
_ENGLISH_RULE = (
    "Setiap field *_en adalah versi bahasa Inggris dari field Indonesia di sebelahnya, ditulis "
    "dalam balasan yang sama: bahasa Inggris saja, isi dan aturannya sama, tanpa bahasa "
    "rekomendasi (jangan memakai kata buy, sell, hold, accumulate, price target atau recommend)."
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
    return problems


def _plan_english(plan):
    """(holder, key, path, note) for each English twin of a cleaned plan that
    cannot stand beside its Indonesian."""
    found = []

    def check(holder, key, path, id_text):
        note = _english_note(holder.get(key), id_text)
        if note:
            found.append((holder, key, path, note))
    check(plan, "question_en", "question_en", plan["question"])
    english = plan.get("hypotheses_en")
    if not isinstance(english, list) or len(english) != len(plan["hypotheses"]):
        found.append((plan, "hypotheses_en", "hypotheses_en",
                      "hypotheses_en harus list terjemahan hypotheses dengan urutan yang sama"))
    else:
        notes = [n for n in map(_english_note, english, plan["hypotheses"]) if n]
        if notes:
            found.append((plan, "hypotheses_en", "hypotheses_en", notes[0]))
    for i, step in enumerate(plan["steps"]):
        check(step, "why_en", f"steps[{i}].why_en", step["why"])
    return found


def _fallback_plan(available):
    steps = [{"tool": name, "args": {"metrics": list(S.DEFAULT_PEER_METRICS)}
              if name == "rank_peers" else {}, "why": "langkah standar host",
              "why_en": "standard host step"}
             for name in tools.TOOLS if available.get(name)]
    return {"question": "Bagaimana posisi emiten terhadap peer dan apa yang berubah belakangan ini?",
            "question_en": "How does the issuer compare with its peers, and what has changed recently?",
            "hypotheses": ["Profitabilitas emiten berbeda dari median peer.",
                           "Pergerakan harga terbaru sejalan dengan arus investor asing."],
            "hypotheses_en": ["The issuer's profitability differs from the peer median.",
                              "Recent price moves follow foreign investor flows."],
            "steps": steps[:MAX_TOOL_CALLS], "source": "host_fallback"}


def _cleaned_plan(plan):
    """A valid plan as stored. Stray CJK tokens are stripped here rather than
    failing the plan (synthesis prose is stripped the same way, see _strip_foreign)."""
    def english(value, limit):
        return _clean(value, limit) if isinstance(value, str) else value
    hypotheses_en = plan.get("hypotheses_en")
    return {"question": _clean(plan["question"], 300),
            "question_en": english(plan.get("question_en"), 300),
            "hypotheses": [_clean(h, 240) for h in plan["hypotheses"]],
            "hypotheses_en": ([english(h, 240) for h in hypotheses_en]
                              if isinstance(hypotheses_en, list) else hypotheses_en),
            "steps": [{"tool": s["tool"], "args": s.get("args") or {}, "why": _clean(s.get("why")),
                       "why_en": english(s.get("why_en"), 200)} for s in plan["steps"]],
            "source": "agent"}


def _make_plan(chat, ticker, info, previous, problems):
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": (
        f"Emiten: {ticker} — {info['name']}. Sektor: {info.get('sector')}; sub-sektor: "
        f"{info.get('sub_sector')}; sub-industri: {info.get('sub_industry')}. "
        f"Tanggal data pasar: {info.get('market_date')}.\n"
        f"Memori: {_memory_brief(previous)}\n\nTool:\n{_tool_menu(info['available'])}\n\n"
        "Susun rencana riset yang spesifik untuk jenis usaha emiten ini (misalnya bank dinilai "
        "lewat ROE dan P/B, penambang lewat margin dan leverage). Balas JSON: "
        '{"question": "pertanyaan riset utama", "question_en": "the same question in English", '
        '"hypotheses": ["hipotesis yang bisa diuji", ...], '
        '"hypotheses_en": ["the same hypotheses in English, in the same order", ...], '
        '"steps": [{"tool": "nama", "args": {...}, "why": "alasan singkat", '
        '"why_en": "the same reason in English"}, ...]}. '
        f"Dua sampai empat hipotesis. Gunakan hanya tool yang tersedia; maksimal "
        f"{MAX_TOOL_CALLS} langkah. " + _ENGLISH_RULE + " Angka di field *_en sama persis dan "
        "ditulis persis seperti di teks Indonesianya.")}]
    kept = None  # a plan whose Indonesian passed while its English is repaired
    for attempt in range(2):
        try:
            raw, plan = _call(chat, messages)
        except Exception as error:  # provider/network/JSON failure
            problems.append(f"plan: {type(error).__name__}: {str(error)[:160]}")
            break
        found = _plan_problems(plan, info["available"])
        english = []
        if not found:
            plan = _cleaned_plan(plan)
            english = _plan_english(plan)
            answered = messages + [{"role": "assistant", "content": raw[:6000]}]
            if not english or attempt == 1:
                _drop_english("plan", english, problems)
                return plan, answered
            kept = (plan, english, answered)
        else:
            problems.append("plan ditolak: " + "; ".join(found[:4]))
        repair = found + [_path_note(path, note) for _h, _k, path, note in english]
        messages = messages + [{"role": "assistant", "content": raw[:6000]}, {
            "role": "user", "content": "Perbaiki rencana. Masalah: " + json.dumps(repair) +
            ". Kembalikan object rencana lengkap."}]
    if kept:
        # The repair did not produce a better plan: keep the Indonesian that passed.
        plan, english, answered = kept
        _drop_english("plan", english, problems)
        return plan, answered
    return _fallback_plan(info["available"]), None


# --------------------------------------------------------------- execute

def _run_tool(ticker, name, args, why, origin, state, steps, all_signals, why_en=None):
    step = {"n": len(steps) + 1, "tool": name, "args": args, "why": why, "origin": origin}
    if why_en:
        step["why_en"] = why_en
    emit("tool", f"Menjalankan {name}", why, status="run", tool=name, data={"kind": "tool_start"},
         detail_en=why_en)
    try:
        result, found = tools.execute(name, ticker, args, state)
    except tools.ToolError as error:
        step.update(status="error", summary=str(error))
        steps.append(step)
        emit("tool", f"{name}: data tidak tersedia", str(error), status="warn", tool=name,
             data={"kind": "tool_empty"})
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
    emit("tool", f"{name} selesai", summary, tool=name, data={"kind": "tool_done"})
    return {"tool": name, "result": result}


def _execute(chat, ticker, plan, messages, available, problems):
    state, steps, all_signals = {}, [], []
    done = set()

    def key(name, args):
        return name + json.dumps(args or {}, sort_keys=True)

    def run_step(name, args, why, origin, why_en=None):
        done.add(key(name, args))
        return _run_tool(ticker, name, args, why, origin, state, steps, all_signals, why_en)

    turns = 0
    if messages is not None:
        messages = messages + [{"role": "user", "content": (
            "Jalankan riset. Setiap giliran balas {\"calls\": [{\"tool\": ..., \"args\": {...}, "
            f"\"why\": ..., \"why_en\": \"the same reason in English\"}}]}} (maksimal "
            f"{MAX_CALLS_PER_TURN} panggilan) atau "
            "{\"done\": true, \"why\": \"...\", \"why_en\": \"the same reason in English\"} bila "
            "bukti sudah cukup. Kamu boleh menyimpang "
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
            why = _clean(action.get("why"))
            why_en = _clean(action.get("why_en")) if isinstance(action.get("why_en"), str) else None
            why_en = why_en if why_en and _english_note(why_en, why) is None else None
            emit("tool", "Agent menilai bukti sudah cukup", why, detail_en=why_en)
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
            # The reason is shown beside the step, so its English twin is kept
            # only when it passes; there is no repair turn for it.
            why_en = _clean(call.get("why_en")) if isinstance(call.get("why_en"), str) else None
            why_en = why_en if why_en and _english_note(why_en, why) is None else None
            results.append(run_step(name, args, why, "agent" if planned else "agent_adaptive", why_en))
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
            run_step(step["tool"], step.get("args") or {}, step.get("why") or "", "host",
                     step.get("why_en"))
    all_signals.extend(s for s in S.cross_signals(all_signals)
                       if s["id"] not in {x["id"] for x in all_signals})
    for signal in all_signals:
        for key, english in (("label_en", S.label_en(signal)), ("flag_en", S.flag_en(signal.get("flag")))):
            if english:
                signal[key] = english
    return state, steps, all_signals


# ------------------------------------------------------------ synthesize

def _lower_first(label):
    """An English label mid-sentence: "net foreign flow", while "ROE" and "P/E" stay."""
    return label[:1].lower() + label[1:] if label[1:2].islower() else label


def _replace_ids(doc, labels, labels_en=None):
    """Readers see signal labels, not internal ids, in accepted prose: the
    English label in an English twin."""
    def swapper(names, case):
        def swap(text):
            if not isinstance(text, str):
                return text
            for signal_id in sorted(names, key=len, reverse=True):
                text = text.replace(signal_id, case(names[signal_id]))
            return text
        return swap
    swap, swap_en = swapper(labels, str.lower), swapper(labels_en or {}, _lower_first)

    def english(holder, key):
        if isinstance(holder.get(key), str):
            holder[key] = swap_en(holder[key])
    doc["headline"] = swap(doc.get("headline"))
    english(doc, "headline_en")
    for item in doc.get("findings") or []:
        for key in ("title", "interpretation", "caveat"):
            item[key] = swap(item.get(key))
            english(item, key + "_en")
    for item in doc.get("hypotheses") or []:
        item["reason"] = swap(item.get("reason"))
        english(item, "reason_en")


def _known_ids(ids, signal_ids):
    """A non-empty list of signal id strings that all exist."""
    return (isinstance(ids, list) and bool(ids) and
            all(isinstance(x, str) and x in signal_ids for x in ids))


def _synthesis_problems(doc, signal_ids, n_hypotheses, label_numbers=frozenset()):
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
    for signal_id in sorted(signal_ids, key=len, reverse=True):
        joined = joined.replace(signal_id, " ")
    numbers = _invented_numbers(joined, signal_ids, label_numbers)
    if numbers:
        problems.append(_removal("prosa tidak boleh memuat angka (angka ditampilkan dari sinyal "
                                 "yang dicite)", "hapus", numbers[:8]))
    if _advice_terms(joined):
        problems.append(_removal("prosa memuat bahasa rekomendasi investasi", "hapus kata",
                                 _advice_terms(joined)))
    if _FOREIGN_SCRIPT.search(joined):
        problems.append(_removal("tulis dalam bahasa Indonesia saja", "hapus",
                                 _FOREIGN_SCRIPT.findall(joined)[:5]))
    return problems


def _synthesis_english(doc, signal_ids, label_numbers, labels_en):
    """(holder, key, path, note) for each English twin of a synthesis whose
    Indonesian passed that cannot stand beside it. The twins hold no numbers
    either, and cite through the Indonesian item's signal_ids."""
    found = []

    def check(holder, key, path, id_text=None):
        text = holder.get(key)
        if id_text is None:
            note = _english_note(text, signal_ids=signal_ids, label_numbers=label_numbers)
            if note is None and any(i in text for i in signal_ids if i not in labels_en):
                note = "id sinyal tanpa label bahasa Inggris; tulis tanpa id itu"
        else:
            note = _english_note(text, id_text)
        if note:
            found.append((holder, key, path, note))
    check(doc, "headline_en", "headline_en")
    for i, item in enumerate(doc["findings"]):
        for key in _PROSE_FIELDS:
            check(item, f"{key}_en", f"findings[{i}].{key}_en")
    for i, item in enumerate(doc.get("hypotheses") or []):
        check(item, "reason_en", f"hypotheses[{i}].reason_en")
    checks, english = doc.get("next_checks"), doc.get("next_checks_en")
    if isinstance(checks, list) and any(isinstance(x, str) for x in checks):
        if not isinstance(english, list) or len(english) != len(checks):
            found.append((doc, "next_checks_en", "next_checks_en",
                          "next_checks_en harus list terjemahan next_checks dengan urutan yang sama"))
        else:
            # Checks the host drops for advice wording drop with their twin.
            notes = [n for x, en in zip(checks, english)
                     if isinstance(x, str) and not _advice_terms(x) and (n := _english_note(en, x))]
            if notes:
                found.append((doc, "next_checks_en", "next_checks_en", notes[0]))
    return found


_PROSE_FIELDS = ("title", "interpretation", "caveat")


def _strip_foreign(doc):
    """Remove stray CJK tokens from the synthesis prose; returns what was removed.

    Reasoning models occasionally drop a Chinese or Japanese word into
    Indonesian prose (BBCA: "優位", "投资者"). The sentence around it is still
    Indonesian, so the token is removed and noted rather than the whole draft
    rejected; prose left empty still fails the validator.
    """
    removed = []

    def clean(text):
        if not isinstance(text, str):
            return text
        removed.extend(_FOREIGN_SCRIPT.findall(text))
        out = re.sub(r"\s{2,}", " ", _FOREIGN_SCRIPT.sub(" ", text))
        return re.sub(r"\s+([,.;:)])", r"\1", out).strip()
    if not isinstance(doc, dict):
        return removed
    doc["headline"] = clean(doc.get("headline"))
    for item in doc.get("findings") or []:
        if isinstance(item, dict):
            for key in _PROSE_FIELDS:
                item[key] = clean(item.get(key))
    for item in doc.get("hypotheses") or []:
        if isinstance(item, dict):
            item["reason"] = clean(item.get("reason"))
    if isinstance(doc.get("next_checks"), list):
        doc["next_checks"] = [clean(x) for x in doc["next_checks"]]
    return list(dict.fromkeys(removed))


def _normalize_verdicts(doc):
    """Map the model's verdict spellings onto the three the host accepts. A
    partial verdict is kept as "belum terjawab" with the reason marked (in both
    languages), so the draft is not rejected for wording alone."""
    for item in (doc or {}).get("hypotheses") or []:
        if not isinstance(item, dict) or not isinstance(item.get("verdict"), str):
            continue
        said = re.sub(r"\s+", " ", item["verdict"]).strip().strip(".").lower()
        if said in _VERDICT_ALIASES:
            item["verdict"] = _VERDICT_ALIASES[said]
        elif _PARTIAL.match(said):
            item["verdict"] = "belum terjawab"
            reason = str(item.get("reason") or "").strip()
            if reason and not reason.lower().startswith("sebagian didukung"):
                item["reason"] = f"Sebagian didukung: {reason[0].lower()}{reason[1:]}"
            reason = item.get("reason_en").strip() if isinstance(item.get("reason_en"), str) else ""
            if reason and not reason.lower().startswith("partly supported"):
                item["reason_en"] = f"Partly supported: {reason[0].lower()}{reason[1:]}"
    return doc


def verdict_code(item):
    """The stable code of a hypothesis verdict: a partial verdict is stored as
    "belum terjawab" with its reason marked "Sebagian didukung"."""
    verdict, reason = item.get("verdict"), str(item.get("reason") or "").lower()
    if verdict == "belum terjawab" and reason.startswith("sebagian didukung"):
        return "partly_supported"
    return VERDICT_CODES.get(verdict) if isinstance(verdict, str) else None


def _accepted(doc, english, labels, labels_en, problems):
    """A synthesis whose Indonesian passed, as stored: failed English twins
    dropped, ids read as labels, verdict codes set."""
    _drop_english("sintesis", english, problems)
    for item in (doc.get("findings") or []) + (doc.get("hypotheses") or []):
        item.pop("signal_ids_en", None)  # a twin cites through the Indonesian item
    _replace_ids(doc, labels, labels_en)
    checks, checks_en = doc.get("next_checks"), doc.pop("next_checks_en", None)
    doc["next_checks"] = [str(x)[:200] for x in (doc.get("next_checks") or [])
                          if isinstance(x, str) and not _advice_terms(x)][:3]
    if isinstance(checks, list) and isinstance(checks_en, list) and len(checks_en) == len(checks):
        doc["next_checks_en"] = [str(en)[:200] for x, en in zip(checks, checks_en)
                                 if isinstance(x, str) and not _advice_terms(x)][:3]
    for item in doc.get("hypotheses") or []:
        item["verdict_code"] = verdict_code(item)
    doc["source"] = "agent"
    return doc


def _fallback_synthesis(all_signals, hypotheses):
    flagged = [s for s in all_signals if s.get("flag")][:3]
    findings = []
    for s in flagged:
        finding = {"title": f"{s['label']}: {s['flag']}", "signal_ids": [s["id"]],
                   "interpretation": "Sinyal ini ditandai aturan host; belum ada tafsir agent.",
                   "caveat": "Perlu dibaca bersama konteks usaha emiten.",
                   "interpretation_en": "The host rules flagged this signal; there is no agent "
                                        "interpretation yet.",
                   "caveat_en": "Read it together with the issuer's business context."}
        label, flag = S.label_en(s), S.flag_en(s.get("flag"))
        if label and flag:
            finding["title_en"] = f"{label}: {flag}"
        findings.append(finding)
    return {"headline": "Ringkasan sinyal yang ditandai host",
            "headline_en": "Summary of the signals the host flagged",
            "findings": findings,
            "hypotheses": [{"index": i, "verdict": "belum terjawab", "signal_ids": [],
                            "reason": "Agent tidak menyelesaikan penilaian hipotesis.",
                            "reason_en": "The agent did not finish assessing the hypothesis.",
                            "verdict_code": "unanswered"}
                           for i in range(len(hypotheses))],
            "next_checks": [], "next_checks_en": [], "source": "host_fallback"}


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
        "Balas JSON: {\"headline\": \"satu kalimat\", \"headline_en\": \"the same sentence in "
        "English\", \"findings\": [{\"title\": ..., \"title_en\": ..., "
        "\"signal_ids\": [...], \"interpretation\": ..., \"interpretation_en\": ..., "
        "\"caveat\": \"batas bukti\", \"caveat_en\": ...}], "
        "\"hypotheses\": [{\"index\": 0, \"verdict\": \"didukung|tidak didukung|belum terjawab\", "
        "\"signal_ids\": [...], \"reason\": ..., \"reason_en\": ...}], "
        "\"next_checks\": [\"pemeriksaan lanjutan\"], "
        "\"next_checks_en\": [\"the same checks in English, in the same order\"]}. "
        "Maksimal empat findings. " + _ENGLISH_RULE + " Field *_en juga TANPA angka dan tidak "
        "punya signal_ids sendiri: ia mengutip sinyal yang sama dengan field Indonesianya "
        "(label_en adalah nama sinyal dalam bahasa Inggris).")}]
    ids = {s["id"] for s in all_signals}
    label_numbers = frozenset(n for s in all_signals if s.get("kind") != "web"
                              for n in re.findall(r"\d+", str(s.get("label") or "")))
    labels = {s["id"]: s["label"] for s in all_signals}
    labels_en = {s["id"]: s["label_en"] for s in all_signals if s.get("label_en")}
    label_numbers_en = label_numbers | frozenset(
        n for s in all_signals if s.get("kind") != "web"
        for n in re.findall(r"\d+", str(s.get("label_en") or "")))
    kept = None  # a draft whose Indonesian passed while its English is repaired
    for attempt in range(2):
        try:
            raw, doc = _call(chat, messages)
        except Exception as error:
            problems.append(f"sintesis: {type(error).__name__}: {str(error)[:160]}")
            break
        stripped = _strip_foreign(doc)
        if stripped:
            problems.append(_Note("sintesis: token non-Indonesia dihapus: " + ", ".join(stripped[:5]),
                                  "sintesis: token non-Indonesia dihapus", stripped[:5]))
        found = _synthesis_problems(_normalize_verdicts(doc), ids, len(plan["hypotheses"]),
                                    label_numbers)
        english = [] if found else _synthesis_english(doc, ids, label_numbers_en, labels_en)
        if not found:
            if not english or attempt == 1:
                return _accepted(doc, english, labels, labels_en, problems)
            kept = (doc, english)
        else:
            problems.append(_joined("sintesis ditolak: ", found[:4]))
            emit("synthesis", "Validator menolak draf kesimpulan", "; ".join(found[:2]), status="warn")
        repair = found + [_path_note(path, note) for _h, _k, path, note in english]
        messages = messages + [{"role": "assistant", "content": raw[:6000]}, {
            "role": "user", "content": "Perbaiki. Masalah: " + json.dumps(repair) +
            ". Kembalikan object lengkap."}]
    if kept:
        # The repair did not produce a better draft: keep the Indonesian that passed.
        return _accepted(*kept, labels, labels_en, problems)
    return _fallback_synthesis(all_signals, plan["hypotheses"])


# ------------------------------------------------- translate a stored result
#
# Results stored before the agent wrote its own English (#39) have no twins.
# ``translate_intel`` asks for them afterwards, in calls of their own, and
# checks each one with the rules a twin from the run itself passes.


class _Prose:
    """One Indonesian prose value of a stored result: ``host[key]``, or item
    ``index`` of the list ``host[key]``. ``cited`` marks conclusion prose, whose
    twin holds no numbers (it cites signals); other twins state exactly the
    figures of their Indonesian. ``limit`` is the length the run keeps."""

    def __init__(self, path, host, key, index=None, cited=False, limit=400):
        self.path, self.host, self.key, self.index = path, host, key, index
        self.cited, self.limit = cited, limit

    @property
    def text(self):
        value = self.host[self.key]
        return value[self.index] if self.index is not None else value


def _host_text(text):
    """The host's own English of host-written text (``app.host_lang``), or None."""
    from app import host_lang  # imports this package's signal tables
    return host_lang.english(text)


def _has_twin(holder, key, count=None):
    twin = holder.get(f"{key}_en")
    if count is None:
        return isinstance(twin, str) and bool(twin.strip())
    return (isinstance(twin, list) and len(twin) == count and
            all(isinstance(x, str) and x.strip() for x in twin))


def _intel_prose(intel):
    """Every analyst prose field of a stored result that has no English twin
    yet and is not host-written text, in result order."""
    fields = []

    def add(host, key, path, cited=False, limit=400):
        if (isinstance(host, dict) and isinstance(host.get(key), str) and host[key].strip()
                and not _has_twin(host, key) and not _host_text(host[key])):
            fields.append(_Prose(f"{path}.{key}" if path else key, host, key, cited=cited,
                                 limit=limit))

    def add_list(host, key, path, cited=False, limit=240):
        items = host.get(key) if isinstance(host, dict) else None
        if (isinstance(items, list) and items and
                all(isinstance(x, str) and x.strip() for x in items) and
                not _has_twin(host, key, len(items))):
            fields.extend(_Prose(f"{path}.{key}[{i}]", host, key, index=i, cited=cited,
                                 limit=limit)
                          for i, x in enumerate(items) if not _host_text(x))

    if not isinstance(intel, dict):
        return fields
    plan = intel.get("plan") if isinstance(intel.get("plan"), dict) else {}
    add(plan, "question", "plan", limit=300)
    add_list(plan, "hypotheses", "plan", limit=240)
    for i, step in enumerate(plan.get("steps") or []):
        add(step, "why", f"plan.steps[{i}]", limit=200)
    for i, step in enumerate(intel.get("steps") or []):
        add(step, "why", f"steps[{i}]", limit=200)
    synthesis = intel.get("synthesis") if isinstance(intel.get("synthesis"), dict) else {}
    add(synthesis, "headline", "synthesis", cited=True, limit=400)
    for i, item in enumerate(synthesis.get("findings") or []):
        for key, limit in (("title", 200), ("interpretation", 900), ("caveat", 400)):
            add(item, key, f"synthesis.findings[{i}]", cited=True, limit=limit)
    for i, item in enumerate(synthesis.get("hypotheses") or []):
        add(item, "reason", f"synthesis.hypotheses[{i}]", cited=True, limit=400)
    add_list(synthesis, "next_checks", "synthesis", limit=200)
    return fields


_TRANSLATOR = (
    "Role: ANALYST TRANSLATOR. You translate the Indonesian prose of a validated equity "
    "research analysis (plan, tool-step reasons, findings, hypothesis verdicts, next checks) "
    "into English for the English edition of the same page. This is information, not "
    "investment advice. The user message is one JSON object {path: Indonesian text}. Return "
    "ONE JSON object {path: English text} with exactly the same paths and nothing else: no "
    "reasoning text, no other keys. Every English text says the same thing in plain English, "
    "with no Indonesian word or clause and no Chinese, Japanese or Korean characters. It "
    "states exactly the figures of its Indonesian, adding none, written exactly as in the "
    "Indonesian (12,4%, 1H26, 20 sesi becomes 20 sessions); findings, headlines and verdict "
    "reasons hold no figures at all beyond those of a signal name or a date. Never write buy, "
    "sell, hold, accumulate, price target, target price, recommend, 'attractive valuation' "
    "or 'buying opportunity', even in another sense (write 'keep' or 'maintain', not 'hold'). "
    "A reason starting 'Sebagian didukung:' starts 'Partly supported:'. Codes and names (ROE, "
    "P/B, IHSG, FY2025) stay as written. Name the signals with these English names "
    "{Indonesian name: English name}: ")
# Indonesian characters per translation call, as for the Forecast Plan.
TRANSLATE_BATCH_CHARS = 6000


def _batches(fields):
    batch, size = [], 0
    for field in fields:
        if batch and size + len(field.text) > TRANSLATE_BATCH_CHARS:
            yield batch
            batch, size = [], 0
        batch.append(field)
        size += len(field.text)
    if batch:
        yield batch


class _CutOff(ValueError):
    """A translation reply cut off at the completion budget."""


def _ask(chat, glossary, fields, follow_up=()):
    """One translation call for ``fields``: ``{path: English}``, or it raises."""
    messages = [{"role": "system", "content": _TRANSLATOR + json.dumps(glossary, ensure_ascii=False)},
                {"role": "user", "content": json.dumps({f.path: f.text for f in fields},
                                                       ensure_ascii=False)},
                *follow_up]
    raw, finish_reason = _response_text(chat(messages, max_tokens=16384, reasoning_effort="low"))
    if finish_reason == "length":
        raise _CutOff("translation cut off (finish_reason=length)")
    answer = _parse_json(raw)
    if not isinstance(answer, dict):
        raise ValueError("translation is not an object")
    return answer


def translate_intel(intel, chat=None):
    """The English twins of a stored analyst result, from calls of their own.

    Returns ``(intel_with_twins, notes)``. Every analyst prose field without a
    twin (``_intel_prose``: plan question, hypotheses and step reasons, the
    executed steps' reasons, headline, findings, verdict reasons and next
    checks) goes out as ``{path: Indonesian}`` in as few calls as fit
    ``TRANSLATE_BATCH_CHARS`` (the same text once) and comes back as ``{path:
    English}``. Each answer passes the checks a twin from the run itself
    passes (``_english_note``): the figures of its Indonesian, or none beyond
    signal names and dates for conclusion prose; no advice wording; English
    only. Signal ids in a conclusion twin read as their English labels, as in
    a new run. The failing paths get one repair call; a twin still wrong after
    it is left out. A parallel list (``hypotheses``, ``next_checks``) gets its
    twin whole or not at all; its host-written items take the host's English.
    Host-written text (``app.host_lang``) and twins the result already has are
    left as they are.

    No Indonesian value changes. A failed call (an exception, a reply that is
    not a JSON object, one cut off at ``finish_reason == "length"``, which is
    first asked again in halves) leaves its fields without twins, and when
    nothing could be attached the result comes back unchanged. ``notes``:
    ``status`` (``translated``, ``partial``, ``failed`` or
    ``nothing_to_translate``), ``fields``, ``attached``, ``calls``,
    ``dropped`` (twins that failed their checks) and ``problems`` (failed
    calls)."""
    chat = chat or _chat
    out = copy.deepcopy(intel)
    fields = _intel_prose(out)
    notes = {"status": "nothing_to_translate", "fields": len(fields), "attached": 0,
             "calls": 0, "dropped": [], "problems": []}
    if not fields:
        return intel, notes
    signals = [s for s in out.get("signals") or [] if isinstance(s, dict) and s.get("id")]
    signal_ids = {s["id"] for s in signals}
    labels_en = {s["id"]: s.get("label_en") or S.label_en(s) for s in signals}
    labels_en = {k: v for k, v in labels_en.items() if v}
    label_numbers = frozenset(n for s in signals if s.get("kind") != "web"
                              for n in re.findall(r"\d+", f"{s.get('label') or ''} "
                                                          f"{labels_en.get(s['id']) or ''}"))
    glossary = {str(s.get("label")).lower(): labels_en[s["id"]] for s in signals
                if s.get("label") and s["id"] in labels_en and s.get("kind") != "web"}
    swap_en = {k: _lower_first(v) for k, v in labels_en.items()}

    def note(field, twin):
        if not field.cited:
            return _english_note(twin, field.text)
        # What the Indonesian itself states (a signal name's number, a date) is allowed.
        allowed = label_numbers | {re.sub(r"\D", "", t) for t in _DIGIT.findall(field.text)}
        found = _english_note(twin, signal_ids=signal_ids, label_numbers=allowed)
        if found is None and any(i in twin for i in signal_ids if i not in labels_en):
            found = "id sinyal tanpa label bahasa Inggris; tulis tanpa id itu"
        return found

    def finish(field, twin):
        if field.cited:
            for signal_id in sorted(swap_en, key=len, reverse=True):
                twin = twin.replace(signal_id, swap_en[signal_id])
        return _clean(twin, field.limit)

    # The same text is asked once (a plan step's reason is the executed step's).
    first = {}
    for field in fields:
        first.setdefault((field.text, field.cited), field)
    unique = list(first.values())
    english, reasons = {}, {}

    def ask(batch, follow_up=(), label="", retried=False):
        notes["calls"] += 1
        try:
            answer = _ask(chat, glossary, batch, follow_up)
        except _CutOff:
            # The model's thinking shares the budget: a reply cut off is asked
            # again in halves, down to one field, before its fields go without.
            if len(batch) > 1 and not follow_up:
                half = len(batch) // 2
                ask(batch[:half], label=label)
                ask(batch[half:], label=label)
                return
            notes["problems"].append(f"{label}{batch[0].path} .. {batch[-1].path}: "
                                     "ValueError: translation cut off (finish_reason=length)")
            return
        except OSError as error:
            # A provider timeout or dropped connection is asked once more before
            # its fields go without English (TimeoutError is an OSError).
            if not retried:
                ask(batch, follow_up, label, retried=True)
                return
            notes["problems"].append(f"{label}{batch[0].path} .. {batch[-1].path}: "
                                     f"{type(error).__name__}: {str(error)[:180]} (after a retry)")
            return
        except Exception as error:  # noqa: BLE001 — the result stands without these twins
            notes["problems"].append(f"{label}{batch[0].path} .. {batch[-1].path}: "
                                     f"{type(error).__name__}: {str(error)[:180]}")
            return
        for field in batch:
            twin = answer.get(field.path)
            found = note(field, twin)
            if found:
                reasons[field.path] = found
            else:
                english[field.path] = finish(field, twin)
                reasons.pop(field.path, None)

    for batch in _batches(unique):
        ask(batch)
    for batch in _batches([f for f in unique if f.path in reasons]):
        errors = json.dumps({f.path: str(reasons[f.path]) for f in batch}, ensure_ascii=False)
        previous = json.dumps({f.path: english.get(f.path) for f in batch}, ensure_ascii=False)
        ask(batch, ({"role": "assistant", "content": previous},
                    {"role": "user", "content":
                     "These English texts failed the checks. Return ONE JSON object {path: "
                     "English text} for exactly these paths, fixing every error: " + errors}),
            label="repair ")
    notes["dropped"] = [f"{path}: {found}" for path, found in reasons.items()]

    def twin_of(field):
        return english.get(first[(field.text, field.cited)].path)
    lists = {}
    for field in fields:
        if field.index is not None:
            lists.setdefault((id(field.host), field.key), []).append(field)
        elif twin_of(field) is not None:
            field.host[f"{field.key}_en"] = twin_of(field)
            notes["attached"] += 1
    for items in lists.values():
        host, key = items[0].host, items[0].key
        asked = {f.index: twin_of(f) for f in items}
        whole = [asked[i] if i in asked else _host_text(x) for i, x in enumerate(host[key])]
        if all(whole):
            host[f"{key}_en"] = whole
            notes["attached"] += len(items)
        elif any(first[(f.text, f.cited)].path in reasons for f in items):
            notes["dropped"].append(f"{items[0].path.rsplit('[', 1)[0]}: every item needs its "
                                    "English, so the list stays Indonesian")
    if not notes["attached"]:
        notes["status"] = "failed"
        return intel, notes
    notes["status"] = "translated" if notes["attached"] == len(fields) else "partial"
    return out, notes


# -------------------------------------------------------------------- run

def run(ticker, *, chat=None, db=None, persist=True):
    """Run the analyst agent for one ticker. Never raises on LLM failure."""
    ticker = str(ticker).strip().upper()
    chat = chat or _chat
    problems = []
    info = tools.overview(ticker)
    previous = memory.latest(ticker, db)
    emit("memory", "Membaca memori riset",
         f"riset terakhir {str(previous.get('run_at'))[:10]}" if previous else "belum ada riset sebelumnya")

    emit("plan", "Agent menyusun rencana riset", status="run")
    plan, messages = _make_plan(chat, ticker, info, previous, problems)
    emit("plan", "Rencana siap" if plan["source"] == "agent" else "Rencana standar host dipakai",
         plan["question"], status="ok" if plan["source"] == "agent" else "warn",
         detail_en=plan.get("question_en"))
    hypotheses_en = plan.get("hypotheses_en") if isinstance(plan.get("hypotheses_en"), list) else []
    for i, hypothesis in enumerate(plan["hypotheses"], 1):
        emit("plan", f"Hipotesis {i}", hypothesis, tool="hypothesis",
             data={"index": i, "kind": "hypothesis"},
             detail_en=hypotheses_en[i - 1] if i <= len(hypotheses_en) else None)

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
         status="ok" if synthesis["source"] == "agent" else "warn",
         detail_en=synthesis.get("headline_en"))
    for verdict in synthesis.get("hypotheses") or []:
        if isinstance(verdict, dict) and isinstance(verdict.get("index"), int) and verdict.get("verdict"):
            # Synthesis indexes hypotheses from 0; the plan events number them from 1.
            number = verdict["index"] + 1
            emit("synthesis", f"H{number} {verdict['verdict']}", verdict.get("reason"),
                 tool="verdict", data={"index": number, "verdict": verdict["verdict"],
                                       "kind": "hypothesis", "verdict_code": verdict_code(verdict)},
                 detail_en=verdict.get("reason_en"))

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
        "problems": [str(p) for p in problems],
        # The same notes with the words the validator asked to remove as a list.
        "problem_notes": problem_notes(problems),
    }
    if persist:
        memory.save(ticker, result, db)
    emit("memory", "Memori riset diperbarui" if persist else "Memori tidak disimpan")
    return result
