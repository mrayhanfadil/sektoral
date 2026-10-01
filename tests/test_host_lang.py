"""English for the Indonesian the host writes for the web app (app.host_lang)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import host_lang  # noqa: E402


@pytest.mark.parametrize("indonesian, english", [
    # Run events.
    ("Agent menyusun rencana riset", "Agent drafts the research plan"),
    ("Membaca memori riset", "Reading the research memory"),
    ("riset terakhir 2026-09-25", "last research 2026-09-25"),
    ("Rencana siap", "Plan ready"),
    ("Hipotesis 3", "Hypothesis 3"),
    ("38 sinyal dihitung, 3 bertanda", "38 signals computed, 3 flagged"),
    ("H2 belum terjawab", "H2 unanswered"),
    ("Menjalankan rank_peers", "Running rank_peers"),
    ("news: data tidak tersedia", "news: data not available"),
    ("Membaca /financials/quarterly/BBRI/", "Reading /financials/quarterly/BBRI/"),
    ("/news/ terbaca", "/news/ read"),
    ("12 artikel relevan, 23 ditolak", "12 relevant articles, 23 rejected"),
    ("1 artikel relevan, 26 ditolak", "1 relevant article, 26 rejected"),
    ("6 kueri pencarian sampai tanggal laporan", "6 search queries up to the Report Date"),
    ("Subagent Dampak berita", "Subagent News impact"),
    ("Skenario laba FY tervalidasi", "FY earnings scenario validated"),
    ("Dampak berita ditolak validator", "News impact rejected by the validator"),
    ("Asumsi forecast selesai (dipakai ulang untuk bukti yang sama)",
     "Forecast assumptions done (reused for the same evidence)"),
    ("tanpa insight yang lolos validasi", "no insight passed validation"),
    ("Status rilis: dapat didistribusikan, berbasis asumsi analis",
     "Release status: distributable, Assumption-Led"),
    ("2 pemeriksaan menahan rating dan target harga", "2 checks hold back the rating and Target Price"),
    ("rating dan target harga diterbitkan", "rating and Target Price published"),
    # Method Gates and the Method Chain.
    ("Kewajaran hasil", "Output sanity"),
    ("metode utama DDM / Excess Return, pembanding Relative Valuation",
     "primary method DDM / Excess Return, comparison Relative Valuation"),
    ("data belum cukup untuk porsi kepentingan nonpengendali",
     "not enough data for non-controlling interest share"),
    ("upside dalam rentang wajar; porsi nilai terminal wajar",
     "upside within a reasonable range; reasonable terminal-value share"),
    ("Metode utama DDM dividen skenario FY26F-FY30F + terminal Gordon (CoE, bukan WACC)",
     "Primary method DDM on scenario dividends FY26F-FY30F + Gordon terminal (CoE, not WACC)"),
    ("PER FY skenario", "Scenario FY PER"),
    ("P/BV-ROE FY skenario (cross-check)", "Scenario FY P/BV-ROE (cross-check)"),
    ("peer PER valid kurang dari tiga", "fewer than three valid peer PERs"),
    ("EPS FY adalah skenario analis dari aktual 1H + asumsi H2, bukan forecast driver "
     "terekonsiliasi; PER peer TTM dari data Sectors; peer dianggap sebanding",
     "FY EPS is an Analyst Scenario from 1H actuals + H2 assumptions, not a reconciled driver "
     "forecast; TTM peer PER from Sectors data; peers taken as comparable"),
    # A release blocker the host writes in English stays as it is inside a reason.
    ("multiple 8x adalah asumsi analis, bukan multiple peer tervalidasi; house-assumption policy "
     "became effective after the Report Date",
     "the 8x multiple is an analyst assumption, not a validated peer multiple; house-assumption "
     "policy became effective after the Report Date"),
    # ... but an Indonesian prefix on it is translated, not passed off as English.
    ("driver ke depan (pertumbuhan kredit, NIM, pendapatan non-bunga, CIR, biaya kredit) adalah "
     "panduan manajemen untuk tahun pertama dan asumsi analis berlabel sesudahnya; belum "
     "Production-Ready: house-assumption policy became effective after the Report Date",
     "forward drivers (loan growth, NIM, non-interest income, CIR, cost of credit) are management "
     "guidance for the first year and labelled Analyst Assumptions after it; not yet "
     "Production-Ready: house-assumption policy became effective after the Report Date"),
    ("belum Production-Ready: house-assumption policy became effective after the Report Date",
     "not yet Production-Ready: house-assumption policy became effective after the Report Date"),
    # The analyst: tool summaries, signals, change items, host fallback.
    ("2 sinyal, 2 bertanda: lonjakan, berbalik ke laba", "2 signals, 2 flagged: surge, back to profit"),
    ("1 sinyal", "1 signal"),
    ("6 berita bertanggal", "6 dated news items"),
    ("10 emiten · tabel peer Sectors milik BBRI yang memuat BBCA",
     "10 issuers · the Sectors peer table of BBRI, which includes BBCA"),
    ("peringkat 4 dari 6 (1 = lebih tinggi)", "rank 4 of 6 (1 = higher)"),
    ("basis pembanding tahun lalu sangat kecil; persentase tidak informatif",
     "the year-earlier base is very small; the percentage is not informative"),
    ("2026-06-01 s.d. 2026-09-11", "2026-06-01 to 2026-09-11"),
    ("5 sesi jual bersih", "5 sessions of net selling"),
    ("Margin laba bersih: peringkat 7 → 4 dari 6", "Net profit margin: rank 7 → 4 of 6"),
    ("Sinyal Liabilitas / ekuitas (tertinggi di grup) tidak lagi muncul",
     "The Liabilities / equity signal (highest in the group) no longer appears"),
    ("Berita baru: Saham Big Caps Menguat", "New article: Saham Big Caps Menguat"),
    ("P/E saat ini vs rata-rata tahun sebelumnya: jauh di bawah rata-rata historis",
     "Current P/E vs the average of earlier years: far below the historical average"),
    ("Ringkasan sinyal yang ditandai host", "Summary of the signals the host flagged"),
    ("Sinyal ini ditandai aturan host; belum ada tafsir agent.",
     "The host rules flagged this signal; there is no agent interpretation yet."),
    ("Perlu dibaca bersama konteks usaha emiten.",
     "Read it together with the issuer's business context."),
    ("Agent tidak menyelesaikan penilaian hipotesis.",
     "The agent did not finish assessing the hypothesis."),
    ("sintesis ditolak: hypotheses[1].verdict harus salah satu ('didukung', 'tidak didukung', "
     "'belum terjawab'); prosa memuat bahasa rekomendasi investasi",
     "synthesis rejected: hypotheses[1].verdict must be one of ('didukung', 'tidak didukung', "
     "'belum terjawab'); prose contains investment-advice wording"),
    # Report list and freshness.
    ("Tambang", "Mining"),
    ("menunggu review publikasi oleh reviewer", "awaiting publication review by a reviewer"),
    ("Rilis resmi 9M26 terbit 2026-10-30; laporan memakai 1H26.",
     "The official 9M26 release came out on 2026-10-30; the report uses 1H26."),
    # The report's own English (report_lang, data/source_text_en).
    ("DCF FCFF skenario FY26F-FY30F + terminal Gordon; exit EV/EBITDA historis sebagai cross-check",
     "FCFF DCF on scenario FY26F-FY30F + Gordon terminal; historical exit EV/EBITDA as cross-check"),
    ("Brief ini merangkum temuan cache yang lolos validasi.",
     "This brief summarizes the cache findings that passed validation."),
])
def test_host_text_has_english(indonesian, english):
    assert host_lang.english(indonesian) == english


@pytest.mark.parametrize("text", [
    # Agent prose, source data and codes have no host English.
    "Verifikasi H1: apakah revenue YoY masih menunjukkan lonjakan dan net income masih berbalik laba.",
    "Asing Net Sell Rp 791 Miliar, Intip Saham yang Banyak Dijual Selama Sepekan Ini",
    "\"BBRI\" Bank Rakyat Indonesia (Persero) saham emiten berita",
    "PT Industri Jamu Dan Farmasi Sido Muncul Tbk",
    "Hasil 1H aktual + asumsi 2H; bukan forecast LoM, catatan agen",
    "distributable_assumption_led", "DDM", "", None, 12,
    # A reason part with one Indonesian word is not English as it stands.
    "peer dianggap sebanding; belum dimodelkan after the Report Date",
])
def test_other_text_has_none(text):
    assert host_lang.english(text) is None


def test_english_states_figures_in_english_format():
    assert host_lang.english("dek harga rata-rata 12 bulan dieskalasi 2,2% per tahun (inflasi AS), "
                             "biaya dan capex ikut dieskalasi") == (
        "price deck at the 12-month average escalated 2.2% a year (US inflation), with costs and "
        "capex escalated too")
    assert host_lang.figures("38.858,7%") == "38,858.7%"
    assert host_lang.figures("Rp1.234 miliar") == "Rp1,234bn"
    assert host_lang.figures("5 sesi beli bersih") == "5 sessions of net buying"
    assert host_lang.figures("n.a.") is None and host_lang.figures("2026-03-31 vs 2025-03-31") is None


def test_add_sets_a_twin_only_where_there_is_none():
    row = {"label": "Rencana siap", "flag": "lonjakan", "flag_en": "kept", "note": "catatan agen"}
    host_lang.add(row, "label", "flag", "note")
    assert row == {"label": "Rencana siap", "label_en": "Plan ready", "flag": "lonjakan",
                   "flag_en": "kept", "note": "catatan agen"}
    plan = {"hypotheses": ["Profitabilitas emiten berbeda dari median peer.", "Hipotesis agen."]}
    host_lang.add_list(plan, "hypotheses")
    assert plan["hypotheses_en"] == ["The issuer's profitability differs from the peer median.", None]
