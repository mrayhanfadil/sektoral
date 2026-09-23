"""Skema drivers JSON — kontrak antara estimator agent dan pipeline.

Satu-satunya tulisan yang boleh masuk data/drivers/{T}.json harus lolos
validate_drivers() di validate.py. Aturan inti: tiap series wajib punya
sumber; angka tanpa sumber = ditolak, bukan dilengkapi diam-diam.
"""
from __future__ import annotations

from datetime import date

REQUIRED_SERIES = ("revenue", "ebitda", "net_profit", "capex")
OPTIONAL_SERIES = ("dna", "interest_expense", "minority", "gross_debt",
                   "inventory", "fcf", "working_capital", "bvps_path")
FACT_METRIC_IDS = REQUIRED_SERIES + OPTIONAL_SERIES

TOP_FIELDS = ("ticker", "basis", "as_of", "currency", "years", "drivers")

# Optional source-backed operating facts. Keep this separate from `drivers`:
# facts are observations/guidance, not automatically forecast assumptions.
FACT_FIELDS = ("claim", "value", "unit", "period", "status", "source",
               "source_date", "page")
OPTIONAL_FACT_FIELDS = ("asset", "project")
NEWS_ANALYSIS_FIELDS = ("summary", "connection", "caveat", "source", "timestamp")
# Keep in sync with app.release.OPERATING_BRIDGE_STAGES. This module is used
# by the estimator gate, so importing app.release here would create coupling.
FACT_BRIDGE_STAGES = (
    "ore_access", "throughput", "grade", "recovery", "payable_production",
    "downstream_capacity", "downstream_utilization", "product_sales_mix",
    "realized_price_netback", "revenue", "unit_cost_royalty", "ebitda",
    "capex", "nwc", "tax", "debt", "fcff",
)


def _nonempty_text(value):
    return isinstance(value, str) and bool(value.strip())


def _valid_fact_value(value):
    # bool is an int subclass, but is not a useful evidence value here.
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return isinstance(value, (int, float))


def _valid_source_date(value):
    if not _nonempty_text(value):
        return False
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def _valid_page(value):
    # A null page explicitly records a non-paginated source (e.g. an API).
    if value is None:
        return True
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return value > 0
    return _nonempty_text(value)


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

    # Preserve legacy driver documents: `facts` is optional. When supplied,
    # each row must retain enough provenance to distinguish an observed fact
    # from a model assumption and trace it back to its source.
    if "facts" in doc:
        facts = doc["facts"]
        if not isinstance(facts, list):
            bad.append("facts harus list")
        else:
            for i, fact in enumerate(facts):
                prefix = f"facts[{i}]"
                if not isinstance(fact, dict):
                    bad.append(f"{prefix}: bukan object")
                    continue
                for field in FACT_FIELDS:
                    if field not in fact:
                        bad.append(f"{prefix}: field hilang: {field}")
                for field in ("claim", "unit", "period", "status", "source"):
                    if field in fact and not _nonempty_text(fact[field]):
                        bad.append(f"{prefix}.{field} harus teks non-kosong")
                if "value" in fact and not _valid_fact_value(fact["value"]):
                    bad.append(f"{prefix}.value harus angka atau teks non-kosong")
                if "source_date" in fact and not _valid_source_date(fact["source_date"]):
                    bad.append(f"{prefix}.source_date harus tanggal ISO YYYY-MM-DD")
                if "page" in fact and not _valid_page(fact["page"]):
                    bad.append(f"{prefix}.page harus nomor/label halaman atau null")
                for field in OPTIONAL_FACT_FIELDS:
                    if field in fact and not _nonempty_text(fact[field]):
                        bad.append(f"{prefix}.{field} harus teks non-kosong bila diisi")
                if "metric" in fact:
                    if not _nonempty_text(fact["metric"]):
                        bad.append(f"{prefix}.metric harus ID metrik non-kosong bila diisi")
                    elif fact["metric"] not in FACT_METRIC_IDS:
                        bad.append(f"{prefix}.metric bukan ID finansial kanonis yang dikenal")
                if "bridge_stage" in fact:
                    if not _nonempty_text(fact["bridge_stage"]):
                        bad.append(f"{prefix}.bridge_stage harus nama tahap non-kosong bila diisi")
                    elif fact["bridge_stage"] not in FACT_BRIDGE_STAGES:
                        bad.append(f"{prefix}.bridge_stage bukan tahap operating bridge yang dikenal")
    if "news_analysis" in doc:
        rows = doc["news_analysis"]
        if not isinstance(rows, list):
            bad.append("news_analysis harus list")
        else:
            for i, row in enumerate(rows):
                prefix = f"news_analysis[{i}]"
                if not isinstance(row, dict):
                    bad.append(f"{prefix}: bukan object")
                    continue
                for field in NEWS_ANALYSIS_FIELDS:
                    if field not in row:
                        bad.append(f"{prefix}: field hilang: {field}")
                    elif not _nonempty_text(row[field]):
                        bad.append(f"{prefix}.{field} harus teks non-kosong")
                if isinstance(row.get("timestamp"), str):
                    try:
                        date.fromisoformat(row["timestamp"][:10])
                    except ValueError:
                        bad.append(f"{prefix}.timestamp harus tanggal ISO")
    return bad
