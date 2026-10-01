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

from . import fmt, prose_lang
from .prose_lang import t as _t

ROOT = Path(__file__).resolve().parent.parent / "data" / "consensus"
TITLE = "Target harga Sektoral dan konsensus analis"


def load(ticker, as_of, root=ROOT):
    """(consensus, reason): the dated consensus, or None and why not."""
    path = Path(root) / f"{str(ticker).upper()}.json"
    if not path.exists():
        return None, _t("konsensus analis belum dikumpulkan untuk emiten ini",
                        "analyst consensus has not been collected for this issuer")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        when = date.fromisoformat(doc["as_of"])
    except (OSError, ValueError, KeyError):
        return None, _t("berkas konsensus tidak valid", "the consensus file is not valid")
    if as_of and when > date.fromisoformat(str(as_of)[:10]):
        return None, _t(f"konsensus diambil {when.isoformat()}, sesudah tanggal laporan; tidak "
                        "dipakai (tanpa data sesudah tanggal laporan)",
                        f"consensus retrieved {when.isoformat()}, after the Report Date; not used "
                        "(no data after the Report Date)")
    return doc, None


def exhibit(ticker, as_of, target, rating, price, root=ROOT):
    """House target vs consensus, or a one-row table saying why it is absent."""
    doc, why = load(ticker, as_of, root)
    rp = lambda v: f"Rp{fmt.rp(v)}"
    rows = [["Target harga Sektoral", f"{rating or '-'} {rp(target)}" if target else "-"]]
    if not doc:
        rows.append(["Konsensus analis", _t(f"tidak tersedia: {why}", f"not available: {why}")])
        note = "Sumber: Sektoral Estimates."
    else:
        avg = doc["target_avg"]
        rows += [
            [f"Rata-rata target konsensus ({doc['analysts']} analis)", rp(avg)],
            ["Rentang target konsensus", _t(f"{rp(doc['target_low'])} s.d. {rp(doc['target_high'])}",
                                            f"{rp(doc['target_low'])} to {rp(doc['target_high'])}")],
            ["Rekomendasi (beli / tahan / jual)", f"{doc['buy']} / {doc['hold']} / {doc['sell']}"],
            ["Target Sektoral terhadap rata-rata konsensus",
             fmt.pct(target / avg - 1) if target and avg else
             _t("tidak dihitung: target harga Sektoral ditahan",
                "not computed: the Sektoral Target Price is withheld")],
            ["Upside rata-rata konsensus terhadap harga",
             fmt.pct(avg / price - 1) if price else
             _t("tidak dihitung: harga pasar tidak tersedia",
                "not computed: no market price is available")],
            # The file's own note (data/consensus), English in data/source_text_en.
            ["Estimasi konsensus pendapatan, EBITDA, laba",
             prose_lang.source(doc.get("estimates_note")) or "-"],
            ["Sumber konsensus", _t(f"{doc['source_title']}, diambil {doc['as_of']}",
                                    f"{doc['source_title']}, retrieved {doc['as_of']}")]]
        note = f"Sumber: {doc['source_title']} ({doc['source_url']}), diambil {doc['as_of']}; Sektoral Estimates."
    return {"n": 0, "judul": TITLE, "tipe": "tabel",
            "data": {"cols": ["Keterangan", "Nilai"], "rows": rows}, "catatan_sumber": note}
