"""English for the Indonesian text the host itself writes for the web app.

The web app shows ``<field>_en`` beside an Indonesian field wherever it exists
(#34). Agents write their own twins; the fixed words the host writes get theirs
here: run-event labels and details, Method Gate rows, the analyst's tool
summaries, signal notes, change items and host fallback sentences, the report
list's labels and the release limitations quoted in the Method Chain.

``english(text)`` is the English of one such string, or None when it is not
known host text (source data, agent prose, a template that changed): the web
then shows the Indonesian. As in ``app.source_patterns``, each entry is the
whole Indonesian string or a pattern over it, written out here rather than
imported from its producer, so a changed wording falls back instead of stating
something the Indonesian does not. Text the host tables do not know is looked
up in the report's own English (``report_lang`` labels and notes,
``prose_lang.known``). Figures come out in English format, as the English
Company Update prints them.
"""
from __future__ import annotations

import functools
import re

from agents.analyst import signals as analyst_signals

from . import prose_lang, report_lang


class _Call:
    """A template whose English is built by `fn` from the match groups; None
    when a nested part has no English."""

    def __init__(self, fn):
        self.fn = fn

    def format(self, *groups):
        return self.fn(*groups)


def _nested(text):
    """English of a group that holds host text itself, or None."""
    return _english(text) if text else None


def _all(parts, sep):
    found = [_nested(p) for p in parts]
    return sep.join(found) if found and all(found) else None


def _plural(n, word, words=None):
    return f"{n} {word if n == '1' else words or word + 's'}"


# --- Run events: the pipeline (app.research), the analyst (agents.analyst.run),
# the research agent (agents.research.run), the forecast agent
# (agents.forecast_assumptions.run) and the valuation decisions (app.run_events).
_EVENTS = {
    "Membaca memori riset": "Reading the research memory",
    "belum ada riset sebelumnya": "no earlier research",
    "Agent menyusun rencana riset": "Agent drafts the research plan",
    "Rencana siap": "Plan ready",
    "Rencana standar host dipakai": "Standard host plan used",
    "Agent menilai bukti sudah cukup": "Agent judged the evidence sufficient",
    "Agent menguji hipotesis dan menulis temuan": "Agent tests the hypotheses and writes findings",
    "Validator menolak draf kesimpulan": "Validator rejected the draft conclusion",
    "Temuan tervalidasi": "Findings validated",
    "Ringkasan host dipakai": "Host summary used",
    "Memori riset diperbarui": "Research memory updated",
    "Memori tidak disimpan": "Memory not saved",
    "Agent analis tidak selesai": "Analyst agent did not finish",
    "Agent riset membaca data dan menyusun brief bersitasi":
        "Research agent reads the data and writes a cited brief",
    "Brief riset tervalidasi": "Research brief validated",
    "Brief riset parsial": "Partial research brief",
    "tanpa insight yang lolos validasi": "no insight passed validation",
    "baseline dibaca host sebelum agent memilih": "baseline read by the host before the agent chooses",
    "host memeriksa berita untuk kuartal yang dibaca": "the host checks the news for the quarter read",
    "Mencari berita bertanggal": "Searching dated news",
    "Pencarian berita gagal": "News search failed",
    "Agent asumsi forecast dilewati karena register bukti gagal":
        "Forecast assumption agent skipped: the evidence register failed",
    "Agent asumsi forecast membaca berita dan rilis resmi":
        "Forecast assumption agent reads the news and official releases",
    "Rencana forecast dipakai ulang": "Forecast plan reused",
    "bukti sama dengan run sebelumnya": "same evidence as the previous run",
    "dipakai ulang untuk bukti yang sama": "reused for the same evidence",
    "Asumsi forecast selesai": "Forecast assumptions done",
    "Asumsi forecast selesai (dipakai ulang untuk bukti yang sama)":
        "Forecast assumptions done (reused for the same evidence)",
    "Terjemahan Inggris rencana forecast": "English translation of the Forecast Plan",
    "Menyusun company update dan memeriksa gate valuasi":
        "Building the Company Update and checking the valuation gates",
    "Company update tersusun": "Company Update built",
    "Selesai": "Done",
    "Gerbang metode menilai emiten": "Method Gates assess the issuer",
    "Method Gates 0-5 memilih metode sebelum nilai dihitung":
        "Method Gates 0-5 choose the method before any value is computed",
    "Rantai metode selesai": "Method Chain done",
    "rating dan target harga diterbitkan": "rating and Target Price published",
    "tanggal laporan": "the Report Date",
}

# Method Gates (run_events.GATES, CHECKS, RELEASE) and hypothesis verdicts.
GATES = {"Model bisnis": "Business model", "Kelayakan data": "Data eligibility",
         "Struktur kepemilikan": "Ownership structure",
         "Siklus & tahap operasi": "Cyclicality & operating stage",
         "Tahap siklus hidup": "Life-cycle stage", "Kewajaran hasil": "Output sanity"}
CHECKS = {
    "model bisnis menentukan metode utama": "the business model sets the Primary Method",
    "riwayat laporan keuangan": "financial-statement history",
    "profitabilitas operasi": "operating profitability",
    "struktur modal": "capital structure",
    "ekuitas positif": "positive equity",
    "porsi kepentingan nonpengendali": "non-controlling interest share",
    "siklus dan tahap operasi": "cycle and operating stage",
    "tahap siklus hidup": "life-cycle stage",
    "upside dalam rentang wajar": "upside within a reasonable range",
    "upside ekstrem": "extreme upside",
    "downside ekstrem": "extreme downside",
    "multiple keluar dalam rentang peer": "exit multiple within the peer range",
    "multiple keluar di luar rentang peer": "exit multiple outside the peer range",
    "porsi nilai terminal wajar": "reasonable terminal-value share",
    "porsi nilai terminal tinggi": "high terminal-value share",
    "lembaga keuangan dinilai dari ekuitas; gerbang ini dilewati":
        "a financial institution is valued on equity; this gate is skipped",
    "tidak dinilai untuk profil ini": "not assessed for this profile",
}
RELEASE = {"siap produksi": "Production-Ready",
           "dapat didistribusikan, berbasis asumsi analis": "distributable, Assumption-Led",
           "draf, belum didistribusikan": "draft, not distributed",
           "tidak diketahui": "unknown"}
VERDICTS = {"didukung": "supported", "tidak didukung": "not supported",
            "belum terjawab": "unanswered"}
SUBAGENTS = {"Dampak berita": "News impact", "Skenario interim": "Interim scenario",
             "Skenario laba FY": "FY earnings scenario", "Tahap bisnis": "Business stage",
             "Tahun lanjutan": "Out-years"}
_SUB = "(" + "|".join(re.escape(s) for s in SUBAGENTS) + ")"
_VERDICT = "(" + "|".join(sorted(VERDICTS, key=len, reverse=True)) + ")"

# --- The analyst: signal labels and flags (agents.analyst.signals), peer bases
# (agents.analyst.tools.find_peers, app.peer_groups.unusable_note), tool errors
# and the host fallback plan and synthesis (agents.analyst.run).
SIGNAL_LABELS = {
    **{label: analyst_signals.LABELS_EN[f"peer.{key}"]
       for key, (label, _unit, _higher) in analyst_signals.PEER_METRICS.items()},
    "Pendapatan kuartal terakhir, yoy": "Latest quarter revenue, yoy",
    "Laba bersih kuartal terakhir, yoy": "Latest quarter net profit, yoy",
    "Return harga pada jendela data": "Share price return over the data window",
    "Selisih return vs IHSG": "Return gap vs IHSG",
    "Volume 10 hari terakhir vs rata-rata sebelumnya":
        "Volume over the last 10 days vs the earlier average",
    "Arus bersih asing, 20 sesi terakhir": "Net foreign flow, last 20 sessions",
    "Arus bersih asing, seluruh jendela data": "Net foreign flow, whole data window",
    "Sesi berturut-turut dengan arah asing yang sama":
        "Consecutive sessions with the same foreign direction",
    "P/E saat ini vs rata-rata tahun sebelumnya": "Current P/E vs the average of earlier years",
    "P/E vs rata-rata P/E peer (Sectors)": "P/E vs the peer average P/E (Sectors)",
    "Arah arus asing vs arah harga": "Foreign flow direction vs price direction",
    "Berita bertanggal yang menyebut emiten": "Dated news mentioning the issuer",
}
FLAGS = analyst_signals.FLAGS_EN
_HIGHER = {"lebih besar": "larger", "lebih tinggi": "higher", "lebih mahal": "more expensive"}
_ANALYST = {
    "tidak bermakna atau tidak tersedia untuk emiten ini":
        "not meaningful or not available for this issuer",
    "berbalik dari rugi ke laba": "from a loss to a profit",
    "masih rugi pada kedua periode": "loss-making in both periods",
    "basis pembanding tahun lalu sangat kecil; persentase tidak informatif":
        "the year-earlier base is very small; the percentage is not informative",
    "tidak ada kuartal yang sama tahun sebelumnya di data":
        "no same quarter of the previous year in the data",
    "berlawanan": "opposite", "searah": "same direction",
    "tabel peer Sectors": "Sectors peer table",
    "peer dipilih menurut model bisnis; alasan tiap peer dan yang dikeluarkan ada di paket grup":
        "peers chosen by business model; the reason for each peer, and for those left out, is "
        "in the group pack",
    "tidak ada grup peer": "no peer group",
    # Tool errors (agents.analyst.tools.ToolError).
    "tidak ada grup peer di data lokal untuk emiten ini":
        "no peer group in the local data for this issuer",
    "tidak ada grup peer untuk diperingkat": "no peer group to rank",
    "data kuartalan tidak tersedia": "quarterly data not available",
    "harga harian tidak tersedia": "daily prices not available",
    "data arus asing tidak tersedia": "foreign flow data not available",
    "riwayat valuasi tidak cukup": "valuation history too short",
    "tidak ada berita yang menyebut emiten ini": "no news mentions this issuer",
    "konteks berita web tidak dikonfigurasi": "web news context not configured",
    # Host fallback plan and synthesis.
    "langkah standar host": "standard host step",
    "Bagaimana posisi emiten terhadap peer dan apa yang berubah belakangan ini?":
        "How does the issuer compare with its peers, and what has changed recently?",
    "Profitabilitas emiten berbeda dari median peer.":
        "The issuer's profitability differs from the peer median.",
    "Pergerakan harga terbaru sejalan dengan arus investor asing.":
        "Recent price moves follow foreign investor flows.",
    "Ringkasan sinyal yang ditandai host": "Summary of the signals the host flagged",
    "Sinyal ini ditandai aturan host; belum ada tafsir agent.":
        "The host rules flagged this signal; there is no agent interpretation yet.",
    "Perlu dibaca bersama konteks usaha emiten.":
        "Read it together with the issuer's business context.",
    "Agent tidak menyelesaikan penilaian hipotesis.":
        "The agent did not finish assessing the hypothesis.",
}
_LABEL = "(" + "|".join(re.escape(s) for s in sorted(SIGNAL_LABELS, key=len, reverse=True)) + ")"
_FLAG = "(" + "|".join(re.escape(s) for s in sorted(FLAGS, key=len, reverse=True)) + ")"

# Analyst validator notes (agents.analyst.run), shown on the Audit Trace.
_VALIDATOR = {
    "prosa tidak boleh memuat angka (angka ditampilkan dari sinyal yang dicite)":
        "prose may not contain figures (figures are shown from the cited signals)",
    "prosa memuat bahasa rekomendasi investasi": "prose contains investment-advice wording",
    "tulis dalam bahasa Indonesia saja": "write in Indonesian only",
    "tulis dalam bahasa Inggris saja": "write in English only",
    "teks bahasa Inggris wajib diisi": "English text is required",
    "angka harus sama persis dengan teks Indonesia": "figures must match the Indonesian text exactly",
    "teks bahasa Inggris masih memuat kalimat bahasa Indonesia":
        "the English text still contains Indonesian sentences",
    "id sinyal tanpa label bahasa Inggris; tulis tanpa id itu":
        "a signal id without an English label; write without that id",
    "findings harus 1-4 item": "findings must have 1-4 items",
    "berita web hanya konteks": "web news is context only",
    "headline, title, interpretation, caveat dan reason wajib diisi":
        "headline, title, interpretation, caveat and reason are required",
    "synthesis harus object": "synthesis must be an object",
    "hypotheses harus list": "hypotheses must be a list",
    "plan harus object": "plan must be an object",
    "question wajib berupa teks": "question must be text",
    "hypotheses harus 1-4 teks": "hypotheses must be 1-4 texts",
    "hypotheses_en harus list terjemahan hypotheses dengan urutan yang sama":
        "hypotheses_en must list the translations of hypotheses in the same order",
    "next_checks_en harus list terjemahan next_checks dengan urutan yang sama":
        "next_checks_en must list the translations of next_checks in the same order",
    "sintesis: token non-Indonesia dihapus": "synthesis: non-Indonesian tokens removed",
}
_STAGES = {"plan": "plan", "rencana": "plan", "sintesis": "synthesis", "eksekusi": "execution"}

# --- Release limitations (app.release) and Method Chain reasons
# (app.report_extras.method_chain_exhibit), joined with "; " in a chain row.
_LIMITS = {
    "input lengkap": "inputs complete",
    "cross-check wajib framework": "framework-required cross-check",
    "EPS FY adalah skenario analis dari aktual 1H + asumsi H2, bukan forecast driver "
    "terekonsiliasi":
        "FY EPS is an Analyst Scenario from 1H actuals + H2 assumptions, not a reconciled "
        "driver forecast",
    "peer dianggap sebanding": "peers taken as comparable",
    "arus kas, capex dan neraca setelah periode interim belum dimodelkan":
        "cash flow, capex and the balance sheet after the interim period are not yet modelled",
    "arus kas dan neraca setelahnya belum dimodelkan":
        "later cash flow and balance sheet are not yet modelled",
    "ROE FY dari skenario laba analis (aktual 1H + asumsi H2) atas ekuitas pemilik induk "
    "terakhir, bukan forecast driver terekonsiliasi":
        "FY ROE from the analyst earnings scenario (1H actuals + H2 assumptions) over the latest "
        "parent equity, not a reconciled driver forecast",
    "CoE CAPM dan pertumbuhan jangka panjang adalah parameter kebijakan analis yang diuji di "
    "tabel sensitivitas":
        "CAPM CoE and long-term growth are analyst policy parameters tested in the sensitivity "
        "table",
    "CoE CAPM dan pertumbuhan jangka panjang adalah parameter kebijakan analis":
        "CAPM CoE and long-term growth are analyst policy parameters",
    "laba dari model driver bank: aktual 1H resmi + H2 dan empat tahun lanjutan dari driver "
    "asumsi analis (pertumbuhan kredit, NIM, pendapatan non-bunga, rasio biaya, biaya kredit), "
    "bukan forecast driver terekonsiliasi":
        "earnings from the bank driver model: official 1H actuals + H2 and four out-years from "
        "analyst-assumption drivers (loan growth, NIM, non-interest income, cost ratio, cost of "
        "credit), not a reconciled driver forecast",
    "cakupan cadangan, LDR, komposisi dana, porsi aset non-produktif, tarif pajak, biaya dana "
    "dan rasio modal dijaga pada nilai historis data Sectors (screening)":
        "allowance coverage, LDR, funding mix, non-earning asset share, tax rate, cost of funds "
        "and capital ratio held at their historical Sectors values (screening)",
    "penempatan dan surat berharga menyeimbangkan neraca":
        "placements and securities balance the balance sheet",
    "CAR adalah proksi": "CAR is a proxy",
    "payout historis data Sectors dianggap berlanjut":
        "the historical Sectors payout is assumed to continue",
    "laba FY dan empat tahun lanjutan adalah skenario analis (aktual 1H resmi + asumsi H2 + "
    "asumsi tahunan), bukan forecast driver terekonsiliasi":
        "FY and four out-year earnings are an Analyst Scenario (official 1H actuals + H2 "
        "assumptions + annual assumptions), not a reconciled driver forecast",
    "driver ke depan (pertumbuhan kredit, NIM, pendapatan non-bunga, CIR, biaya kredit) adalah "
    "panduan manajemen untuk tahun pertama dan asumsi analis berlabel sesudahnya":
        "forward drivers (loan growth, NIM, non-interest income, CIR, cost of credit) are "
        "management guidance for the first year and labelled Analyst Assumptions after it",
    "driver ke depan (volume, harga, biaya per unit, capex) adalah asumsi analis berlabel dengan "
    "dasar bersumber":
        "forward drivers (volume, price, unit cost, capex) are labelled Analyst Assumptions on a "
        "sourced basis",
    "lihat daftar driver": "see the driver list",
    "pendapatan, margin EBITDA dan capex adalah skenario analis (aktual 1H resmi + asumsi H2 + "
    "asumsi tahunan), bukan forecast driver terekonsiliasi":
        "revenue, EBITDA margin and capex are an Analyst Scenario (official 1H actuals + H2 "
        "assumptions + annual assumptions), not a reconciled driver forecast",
    "D&A, tarif pajak efektif dan intensitas modal kerja dari sejarah":
        "D&A, effective tax rate and working-capital intensity from history",
    "WACC dan pertumbuhan terminal adalah parameter kebijakan analis":
        "WACC and terminal growth are analyst policy parameters",
    "exit EV/EBITDA historis hanya cross-check": "historical exit EV/EBITDA is a cross-check only",
    "selisihnya diungkapkan, tidak dirata-rata": "the gap is disclosed, not averaged",
    "tanah untuk pengembangan dinilai dengan RNAV landbank":
        "development land is valued with a landbank RNAV",
    "porsi dapat dijual dan laju penjualan adalah asumsi analis, hotel dan utilitas pada nilai "
    "buku":
        "the saleable share and sales pace are Analyst Assumptions; hotels and utilities at book "
        "value",
    "segmen tanpa harga pasar dinilai pada nilai buku (lahan industri pada biaya perolehan)":
        "segments without a market price are valued at book (industrial land at cost)",
    "DCF konsolidasi atas skenario analis hanya referensi":
        "the consolidated DCF on the Analyst Scenario is a reference only",
    "nilai SOTP pada tanggal laporan tidak bergantung padanya":
        "the SOTP value at the Report Date does not depend on it",
    "EBITDA FY adalah skenario analis (aktual 1H resmi + margin EBITDA asumsi agen), bukan "
    "forecast driver terekonsiliasi":
        "FY EBITDA is an Analyst Scenario (official 1H actuals + the agent's assumed EBITDA "
        "margin), not a reconciled driver forecast",
    "kas, utang dan minoritas dari satu neraca": "cash, debt and minorities from one balance sheet",
    "LoM/SOTP per aset serta pergerakan kas dan utang sesudahnya belum dimodelkan":
        "per-asset LoM/SOTP and later cash and debt movements are not yet modelled",
    "cadangan Elang sesudah batas izin tidak dinilai":
        "Elang reserves beyond the licence limit are not valued",
    "nilai buku terlapor pada neraca interim resmi, tanpa revaluasi aset":
        "reported book value on the official interim balance sheet, without asset revaluation",
    "skenario laba FY adalah konteks tesis, bukan dasar target":
        "the FY earnings scenario is thesis context, not the basis of the target",
}

# --- Report list (app.gallery) and freshness (app.release_policy,
# app.publication_monitor, app.forecast_ledger).
PROFILES = {"Bank": "Bank", "Tambang": "Mining", "Korporasi": "Corporate", "Emiten": "Issuer"}
_GALLERY = {
    "publikasi ini ditarik": "this publication was withdrawn",
    "riwayat publikasi tidak valid": "the publication history is not valid",
    "publikasi ini telah digantikan": "this publication has been superseded",
    "menunggu review publikasi oleh reviewer": "awaiting publication review by a reviewer",
    "laporan belum tersedia untuk umum": "the report is not yet public",
    "Tidak ada Company Update yang disetujui.": "There is no approved Company Update.",
}

FIXED = {**_EVENTS, **GATES, **CHECKS, **RELEASE, **SUBAGENTS, **SIGNAL_LABELS, **FLAGS,
         **_ANALYST, **_VALIDATOR, **_LIMITS, **_GALLERY, **PROFILES}

_PATTERNS = [
    # Events.
    (r"riset terakhir (\S+)", "last research {0}"),
    (r"Hipotesis (\d+)", "Hypothesis {0}"),
    (r"(\d+) sinyal dihitung, (\d+) bertanda", _Call(lambda n, m: f"{_plural(n, 'signal')} computed, "
                                                                 f"{m} flagged")),
    (r"H(\d+) " + _VERDICT, _Call(lambda n, verdict: f"H{n} {VERDICTS[verdict]}")),
    (r"Menjalankan (\w+)", "Running {0}"),
    (r"(\w+) selesai", "{0} done"),
    (r"(\w+): data tidak tersedia", "{0}: data not available"),
    (r"Membaca (/\S*)", "Reading {0}"),
    (r"(/\S*) terbaca", "{0} read"),
    (r"(/\S*) kosong", "{0} empty"),
    (r"(\d+) insight bersitasi", _Call(lambda n: _plural(n, "cited insight"))),
    (r"(\d+) kueri pencarian sampai (.+)",
     _Call(lambda n, day: f"{_plural(n, 'search query', 'search queries')} up to "
                          f"{_EVENTS.get(day, day)}")),
    (r"(\d+) artikel relevan, (\d+) ditolak",
     _Call(lambda n, m: f"{_plural(n, 'relevant article')}, {m} rejected")),
    (r"Tavily (\w+)", "Tavily {0}"),
    (r"(.+) sampai (\d{4}-\d{2}-\d{2})", "{0} up to {1}"),
    (r"Subagent " + _SUB, _Call(lambda name: f"Subagent {SUBAGENTS[name]}")),
    (_SUB + r" tervalidasi", _Call(lambda name: f"{SUBAGENTS[name]} validated")),
    (_SUB + r" ditolak validator", _Call(lambda name: f"{SUBAGENTS[name]} rejected by the validator")),
    (_SUB + r" gagal", _Call(lambda name: f"{SUBAGENTS[name]} failed")),
    (r"(\d+)/(\d+) teks(; sisanya tetap berbahasa Indonesia)?",
     _Call(lambda n, m, rest: f"{n}/{m} texts" + ("; the rest stays in Indonesian" if rest else ""))),
    (r"Metode utama (.+)", _Call(lambda method: (lambda en: en and f"Primary method {en}")(
        _method(method)))),
    (r"Status rilis: (.+)", _Call(lambda status: f"Release status: {RELEASE.get(status, status)}")),
    (r"(\d+) pemeriksaan menahan rating dan target harga",
     _Call(lambda n: f"{_plural(n, 'check')} hold back the rating and Target Price"
           if n != "1" else "1 check holds back the rating and Target Price")),
    (r"metode utama (.+?)(?:, pembanding (.+))?",
     _Call(lambda primary, secondary: f"primary method {primary}"
                                      + (f", comparison {secondary}" if secondary else ""))),
    (r"data belum cukup untuk (.+)",
     _Call(lambda checks: (lambda en: en and f"not enough data for {en}")(_all(checks.split("; "), "; ")))),
    (r"(.+) \(cross-check\)", _Call(lambda name: (lambda en: en and f"{en} (cross-check)")(_method(name)))),
    (r"(.+) \(override analis\)",
     _Call(lambda name: (lambda en: en and f"{en} (analyst override)")(_method(name)))),
    # Analyst tool summaries, signals and change items.
    (r"(\d+) sinyal", _Call(lambda n: _plural(n, "signal"))),
    (r"(\d+) sinyal, (\d+) bertanda: (.+)",
     _Call(lambda n, m, flags: (lambda en: en and f"{_plural(n, 'signal')}, {m} flagged: {en}")(
         _all(flags.split(", "), ", ")))),
    (r"(\d+) emiten · (.+)",
     _Call(lambda n, basis: (lambda en: en and f"{_plural(n, 'issuer')} · {en}")(_nested(basis)))),
    (r"(\d+) berita bertanggal", _Call(lambda n: _plural(n, "dated news item"))),
    (r"peringkat (\d+) dari (\d+) \(1 = (lebih besar|lebih tinggi|lebih mahal)\)",
     _Call(lambda rank, n, higher: f"rank {rank} of {n} (1 = {_HIGHER[higher]})")),
    (r"(\d+) sesi (beli|jual) bersih",
     _Call(lambda n, side: f"{_plural(n, 'session')} of net {'buying' if side == 'beli' else 'selling'}")),
    (r"(\S+) s\.d\. (\S+)", "{0} to {1}"),
    (r"tabel peer Sectors; (.+)",
     _Call(lambda note: (lambda en: en and f"Sectors peer table; {en}")(_nested(note)))),
    (r"tabel peer Sectors milik (\S+) yang memuat (\S+)",
     "the Sectors peer table of {0}, which includes {1}"),
    (r"(peer dipilih menurut model bisnis; .+); tanpa data: (.+)",
     _Call(lambda basis, missing: (lambda en: en and f"{en}; no data: {missing}")(_nested(basis)))),
    (r"emiten data lokal dengan (\S+) sama", "local-data issuers with the same {0}"),
    (r"grup peer kurasi (\S+) tidak menemukan emiten BEI yang sebanding, sehingga tabel peer "
     r"Sectors dipakai",
     "the curated Peer Group of {0} found no comparable IDX issuer, so the Sectors peer table is "
     "used"),
    (r"grup peer kurasi (\S+) hanya menemukan (\d+) emiten BEI yang sebanding \((.+); minimal "
     r"(\d+)\), sehingga tabel peer Sectors dipakai",
     "the curated Peer Group of {0} found only {1} comparable IDX issuers ({2}; at least {3}), so "
     "the Sectors peer table is used"),
    (r"tidak ada berita web bertanggal dalam jendela (.+)", "no dated web news in the {0} window"),
    (r"sebutkan minimal satu metrik valid: (.+)", "name at least one valid metric: {0}"),
    (r"tool (.+) tidak dikenal", "unknown tool {0}"),
    (r"tool (.+) belum diimplementasikan", "tool {0} not yet implemented"),
    (_LABEL + r": peringkat (\d+) → (\d+) dari (\S+)",
     _Call(lambda label, a, b, n: f"{SIGNAL_LABELS[label]}: rank {a} → {b} of {n}")),
    (_LABEL + r": (.+) → (.+)",
     _Call(lambda label, a, b: f"{SIGNAL_LABELS[label]}: {_display(a)} → {_display(b)}")),
    (r"Sinyal baru pada " + _LABEL + ": " + _FLAG,
     _Call(lambda label, flag: f"New signal on {SIGNAL_LABELS[label]}: {FLAGS[flag]}")),
    (r"Sinyal " + _LABEL + r" \(" + _FLAG + r"\) tidak lagi muncul",
     _Call(lambda label, flag: f"The {SIGNAL_LABELS[label]} signal ({FLAGS[flag]}) no longer "
                               "appears")),
    (r"Berita baru: (.+)", "New article: {0}"),
    (_LABEL + ": " + _FLAG, _Call(lambda label, flag: f"{SIGNAL_LABELS[label]}: {FLAGS[flag]}")),
    # Validator notes: a prefix, then notes joined with "; ".
    (r"(sintesis|plan|rencana) ditolak: (.+)",
     _Call(lambda stage, notes: (lambda en: en and f"{_STAGES.get(stage, 'plan')} rejected: {en}")(
         _all(notes.split("; "), "; ")))),
    (r"(sintesis|plan): teks Inggris dibuang, bahasa Indonesia dipakai: (.+)",
     _Call(lambda stage, notes: (lambda en: en and f"{_STAGES[stage]}: English text dropped, "
                                                   f"Indonesian kept: {en}")(
         _all(notes.split("; "), "; ")))),
    (r"sintesis: token non-Indonesia dihapus: (.+)", "synthesis: non-Indonesian tokens removed: {0}"),
    (r"(sintesis|plan): teks Inggris dibuang, bahasa Indonesia dipakai",
     _Call(lambda stage: f"{_STAGES[stage]}: English text dropped, Indonesian kept")),
    (r"(sintesis|plan|eksekusi): ([A-Z]\w*(?:Error|Exception)\b.*)",
     _Call(lambda stage, error: f"{_STAGES[stage]}: {error}")),
    (r"([\w\[\].]+): (.+)", _Call(lambda path, note: (lambda en: en and f"{path}: {en}")(
        _VALIDATOR.get(note) if path.split("[")[0] in _FIELDS else None))),
    (r"(hypotheses|findings)\[(\d+)\]\.verdict harus salah satu (\(.+\))",
     "{0}[{1}].verdict must be one of {2}"),
    (r"(hypotheses|findings)\[(\d+)\]\.signal_ids harus list id sinyal yang ada",
     "{0}[{1}].signal_ids must list existing signal ids"),
    (r"findings\[(\d+)\] harus object", "findings[{0}] must be an object"),
    (r"findings\[(\d+)\] wajib mengutip minimal satu sinyal Sectors",
     "findings[{0}] must cite at least one Sectors signal"),
    (r"hypotheses\[(\d+)\]\.index tidak valid", "hypotheses[{0}].index is not valid"),
    (r"hypotheses\[(\d+)\] perlu signal_ids yang ada untuk verdict ini",
     "hypotheses[{0}] needs existing signal_ids for this verdict"),
    (r"hypotheses\[(\d+)\] wajib didukung sinyal Sectors, bukan hanya berita web",
     "hypotheses[{0}] must be supported by Sectors signals, not by web news alone"),
    (r"steps harus 2-(\d+) langkah", "steps must be 2-{0} steps"),
    (r"steps\[(\d+)\]: tool (.+) tidak dikenal", "steps[{0}]: unknown tool {1}"),
    (r"steps\[(\d+)\]: args harus object", "steps[{0}]: args must be an object"),
    (r"steps\[(\d+)\]: (\w+) tidak tersedia untuk emiten ini",
     "steps[{0}]: {1} is not available for this issuer"),
    (r"steps\[(\d+)\]: metrics harus list dari (.+)", "steps[{0}]: metrics must be a list from {1}"),
    (r"plan memuat bahasa rekomendasi investasi: (.+)", "plan contains investment-advice wording: {0}"),
    # The words a note asks to remove, as the "Validator menolak" event quotes it.
    (r"hapus kata: (.+)", "remove the words: {0}"),
    (r"hapus: (.+)", "remove: {0}"),
    # Release limitations with figures or sources.
    (r"PER peer TTM dari (.+)", _Call(lambda source: (lambda en: en and f"TTM peer PER from {en}")(
        _source(source)))),
    (r"P/B peer TTM dari (.+)", _Call(lambda source: (lambda en: en and f"TTM peer P/B from {en}")(
        _source(source)))),
    (r"EV/EBITDA peer terakhir \(12 bulan terakhir bila tersedia\) dari (.+) \(kapitalisasi pasar "
     r"\+ utang - kas laporan peer\) diterapkan ke EBITDA forward",
     _Call(lambda source: (lambda en: en and "latest peer EV/EBITDA (last 12 months where "
                                            f"available) from {en} (market cap + debt - cash from "
                                            "peer reports) applied to forward EBITDA")(
         _source(source)))),
    (r"belum Production-Ready: (.+)", _Call(lambda why: (lambda en: en and f"not yet "
                                                                           f"Production-Ready: {en}")(
        _as_english(why)))),
    (r"capex dan jadwal Elang dari riset broker serta probabilitas pengembangan (\S+) adalah "
     r"asumsi analis berlabel",
     "Elang capex and schedule from broker research and the {0} development probability are "
     "labelled Analyst Assumptions"),
    (r"dek harga rata-rata 12 bulan dieskalasi (\S+) per tahun \(inflasi AS\), biaya dan capex "
     r"ikut dieskalasi",
     "price deck at the 12-month average escalated {0} a year (US inflation), with costs and "
     "capex escalated too"),
    (r"proyeksi laba (\S+)-(\S+) adalah skenario analis tanpa model operasional bersumber",
     "the {0}-{1} earnings projection is an Analyst Scenario without a sourced Operating Model"),
    (r"diskon holding (\S+) adalah asumsi analis untuk sensitivitas",
     "the {0} holding discount is an analyst assumption for sensitivity"),
    (r"multiple (\S+) adalah asumsi analis, bukan multiple peer tervalidasi",
     "the {0} multiple is an analyst assumption, not a validated peer multiple"),
    # Freshness.
    (r"Periode (\S+) wajib terbit paling lambat (\S+) \(batas OJK\); laporan memakai (\S+)\.",
     "The {0} period must be published by {1} (OJK deadline); the report uses {2}."),
    (r"Rilis resmi (\S+) terbit (\S+); laporan memakai (\S+)\.",
     "The official {0} release came out on {1}; the report uses {2}."),
    (r"Pemicu pembaruan terbuka sejak (\S+); laporan tetap tampil dengan label stale sampai "
     r"ditinjau\.( Materialitas belum diukur karena belum ada kandidat pengganti\.)?",
     _Call(lambda day, rest: f"An update trigger has been open since {day}; the report stays "
                             "visible, labelled stale, until it is reviewed."
                             + (" Materiality is not yet measured: there is no replacement "
                                "candidate yet." if rest else ""))),
    (r"Perubahan material \((.+)\) tanpa pengganti yang disetujui dalam (\d+) hari bursa sejak "
     r"(\S+)\.",
     "Material change ({0}) without an approved replacement within {1} trading days since {2}."),
    (r"Kesalahan forecast laba induk (\S+) (\S+) melewati materialitas; tinjau asumsi dan putuskan "
     r"revisi atau pertahankan dengan alasan tercatat\.",
     "The {0} parent-profit forecast error of {1} exceeds materiality; review the assumptions "
     "and decide to revise or maintain with a recorded reason."),
]
_FIELDS = {"question_en", "hypotheses_en", "steps", "headline_en", "findings", "hypotheses",
           "next_checks_en"}
PATTERNS = [(re.compile(p), t) for p, t in _PATTERNS]


def _method(text):
    """A method name or line: its English, or itself when it is already English."""
    return _as_english(text) or (text if prose_lang.language_neutral(text) else None)


def _source(text):
    return prose_lang.known(text) or (text if text in ("Yahoo Finance",) else None)


# English function words: host text some code already writes in English (a
# release blocker quoted in a Method Chain reason) holds at least one.
_ENGLISH_WORD = re.compile(r"\b(the|a|an|of|to|in|on|for|and|or|is|are|not|after|before|this|"
                           r"than|with|from|by|at|be|been|has|have)\b", re.I)


def _as_english(text):
    """The English of host text, else the text itself when host code already
    writes it in English: an English function word and no Indonesian one.

    The tables come first: "belum Production-Ready: <an English blocker>" holds
    English words and a single Indonesian one, which ``prose_lang.mixed`` (two
    or more) lets through, so it would pass for English and keep its prefix."""
    found = _nested(text)
    if found:
        return found
    if _ENGLISH_WORD.search(text) and not prose_lang.indonesian_words(text):
        return text
    return None


def _display(text):
    """A signal display value in English: its words, or its figures in English format."""
    return _nested(text) or report_lang.plain(text)


@functools.lru_cache(maxsize=8192)
def _english(text: str) -> str | None:
    hit = FIXED.get(text)
    if hit is not None:
        return hit
    for pattern, template in PATTERNS:
        found = pattern.fullmatch(text)
        if found:
            out = template.format(*(g or "" for g in found.groups()))
            if out:
                return out
    known = report_lang.known(text) or prose_lang.known(text)
    if known and not prose_lang.mixed(known):
        return known
    note = report_lang.note(text, "en")
    if note != text:
        return note
    if "; " in text:  # a Method Chain reason: release limitations joined
        parts = [_as_english(p) for p in text.split("; ")]
        if all(parts):
            return "; ".join(parts)
    return None


def english(text) -> str | None:
    """The English of host-written Indonesian `text`, figures in English format;
    None when it is not known host text."""
    if not isinstance(text, str) or not text.strip():
        return None
    found = _english(text)
    found = report_lang.plain(found) if found else None
    return found if found != text else None


def figures(text) -> str | None:
    """`text` with its figures in English format, or None when nothing changes
    (a signal's display value, a table cell of figures)."""
    if not isinstance(text, str):
        return None
    out = english(text) or report_lang.plain(text)
    return out if out != text else None


def add(holder: dict, *keys: str, how=None) -> dict:
    """Set ``<key>_en`` on `holder` for each key whose text has English and no
    twin yet (``how``: english by default). Returns `holder`."""
    how = how or english
    for key in keys:
        if holder.get(f"{key}_en") is None:
            found = how(holder.get(key))
            if found is not None:
                holder[f"{key}_en"] = found
    return holder


def add_list(holder: dict, key: str, how=None) -> dict:
    """``<key>_en``: a parallel list for a list of strings (None where there is
    no English), set only when there is none yet and some item has English."""
    how = how or english
    values = holder.get(key)
    if holder.get(f"{key}_en") is None and isinstance(values, list):
        found = [how(v) for v in values]
        if any(v is not None for v in found):
            holder[f"{key}_en"] = found
    return holder
