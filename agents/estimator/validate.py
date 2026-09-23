"""Gate output estimator: skema + sumber + sanity angka.

Kembalikan list pelanggaran; kosong = lolos dan boleh ditulis ke
data/drivers/. Selain skema (schema.py), gate menolak:
- series tanpa sumber (anti-karangan),
- angka negatif pada revenue/ebitda/capex level yang tidak masuk akal
  (capex boleh negatif bila dinyatakan sebagai arus masuk? tidak — capex
  level harus >= 0),
- mata uang campur (satu field currency untuk semua path).
"""
from __future__ import annotations

from .schema import REQUIRED_SERIES, validate_drivers


def gate(doc, years=3):
    bad = validate_drivers(doc, years)
    if bad:
        return bad
    cur = doc.get("currency", "")
    if not cur or not isinstance(cur, str):
        bad.append("currency harus satu string eksplisit")
    drv = doc["drivers"]
    for s in ("revenue", "ebitda", "capex"):
        if s in drv:
            for v in drv[s]["path"]:
                if v < 0:
                    bad.append(f"{s}.path negatif ({v}) — level harus >= 0")
    for s in REQUIRED_SERIES:
        note = (drv[s].get("note") or "")
        if len(note) < 10:
            bad.append(f"{s}.note terlalu tipis (<10 karakter) — jelaskan driver")
    return bad
