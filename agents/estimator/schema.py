"""Skema drivers JSON — kontrak antara estimator agent dan pipeline.

Satu-satunya tulisan yang boleh masuk data/drivers/{T}.json harus lolos
validate_drivers() di validate.py. Aturan inti: tiap series wajib punya
sumber; angka tanpa sumber = ditolak, bukan dilengkapi diam-diam.
"""
from __future__ import annotations

REQUIRED_SERIES = ("revenue", "ebitda", "net_profit", "capex")
OPTIONAL_SERIES = ("dna", "interest_expense", "minority", "gross_debt",
                   "inventory", "fcf", "working_capital", "bvps_path")

TOP_FIELDS = ("ticker", "basis", "as_of", "currency", "years", "drivers")


def validate_drivers(doc, years=3):
    """Kembalikan list pelanggaran (kosong = lolos). Tidak raise."""
    bad = []
    if not isinstance(doc, dict):
        return ["root bukan object"]
    for f in TOP_FIELDS:
        if f not in doc:
            bad.append(f"field hilang: {f}")
    if bad:
        return bad
    ys = doc["years"]
    if not isinstance(ys, list) or len(ys) != years:
        bad.append(f"years harus list {years} tahun")
    drv = doc["drivers"]
    if not isinstance(drv, dict):
        return bad + ["drivers bukan object"]
    for s in REQUIRED_SERIES:
        if s not in drv:
            bad.append(f"series wajib hilang: {s}")
    for s, it in drv.items():
        if not isinstance(it, dict):
            bad.append(f"{s}: bukan object")
            continue
        p = it.get("path")
        if not isinstance(p, list) or len(p) != years or \
                not all(isinstance(v, (int, float)) for v in p):
            bad.append(f"{s}.path harus list {years} angka")
        if not it.get("source") or not isinstance(it.get("source"), str):
            bad.append(f"{s}: tanpa sumber — DITOLAK")
    return bad
