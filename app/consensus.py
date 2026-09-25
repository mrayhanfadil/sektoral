"""Published analyst consensus per issuer (plan 2.2), dated and sourced.

data/consensus/{T}.json holds the target-price consensus a public aggregator
shows (analyst count, rating split, average, high and low target) with its
source, URL and retrieval date, and the consensus earnings estimates when a
citable source shows them (``estimates``; ``estimates_note`` says why not).
A report reads the file only when it was retrieved on or before the Report
Date; otherwise it states that consensus was not available on that date.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from . import fmt

ROOT = Path(__file__).resolve().parent.parent / "data" / "consensus"
TITLE = "Nilai model Sektoral dan konsensus analis"


def load(ticker, as_of, root=ROOT):
    """(consensus, reason): the dated consensus, or None and why not."""
    path = Path(root) / f"{str(ticker).upper()}.json"
    if not path.exists():
        return None, "konsensus analis belum dikumpulkan untuk emiten ini"
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        when = date.fromisoformat(doc["as_of"])
    except (OSError, ValueError, KeyError):
        return None, "berkas konsensus tidak valid"
    if as_of and when > date.fromisoformat(str(as_of)[:10]):
        return None, (f"konsensus diambil {when.isoformat()}, sesudah tanggal laporan; tidak "
                      "dipakai (tanpa data sesudah tanggal laporan)")
    return doc, None


def exhibit(ticker, as_of, target, _rating, price, root=ROOT):
    """Informational model value vs sourced consensus, without house action labels."""
    doc, why = load(ticker, as_of, root)
    rp = lambda v: f"Rp{fmt.rp(v)}"
    rows = [["Skenario nilai indikatif", rp(target) if target else
             "Belum diterbitkan; menunggu peninjauan"]]
    if not doc:
        rows.append(["Konsensus analis", f"tidak tersedia: {why}"])
        note = "Sumber: Sektoral Estimates."
    else:
        avg = doc["target_avg"]
        rows += [
            [f"Rata-rata target konsensus ({doc['analysts']} analis)", rp(avg)],
            ["Rentang target konsensus", f"{rp(doc['target_low'])} s.d. {rp(doc['target_high'])}"],
            ["Nilai model Sektoral dibanding rata-rata konsensus",
             fmt.pct(target / avg - 1) if target and avg else
             "tidak dihitung: skenario nilai belum diterbitkan"],
            ["Selisih rata-rata konsensus dari harga terakhir",
             fmt.pct(avg / price - 1) if price else "tidak dihitung: harga pasar tidak tersedia"],
            ["Estimasi konsensus pendapatan, EBITDA, laba", doc.get("estimates_note") or "-"],
            ["Sumber konsensus", f"{doc['source_title']}, diambil {doc['as_of']}"]]
        note = f"Sumber: {doc['source_title']} ({doc['source_url']}), diambil {doc['as_of']}; Sektoral Estimates."
    return {"n": 0, "judul": TITLE, "tipe": "tabel",
            "data": {"cols": ["Keterangan", "Nilai"], "rows": rows}, "catatan_sumber": note}
