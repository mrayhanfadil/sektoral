"""Pipeline v3: cache market data, local official source packs, report build."""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

from . import forecast, intake, narrative, render, report_contract, report_extras, valuation

PDF_OK = True
try:
    from . import pdf as pdf_mod
except Exception:
    pdf_mod = None

OUT = Path(__file__).resolve().parent.parent / "out"


def build(ticker, outdir=OUT, want_pdf=False, method="auto", as_of=None,
          illustrative_scenarios=False, assumption_plan=None,
          analyst_target=False, assumption_status=None, news_evidence=None):
    doc_in, g1 = intake.load(ticker, as_of=as_of)
    if news_evidence is not None:
        doc_in["news"] = news_evidence["rows"]
        doc_in["news_full"] = news_evidence["full"]
        doc_in["news_search"] = news_evidence["search"]
    fc = forecast.build(doc_in, assumption_plan=assumption_plan)
    va = valuation.build(doc_in, fc, analyst_target=analyst_target,
                         assumption_status=assumption_status)
    doc = narrative.build(doc_in, fc, va, g1, method=method,
                          illustrative_scenarios=illustrative_scenarios or analyst_target)
    report_extras.enrich(doc, doc_in, report_extras.valuation_inputs(doc_in, fc, va))
    doc["forecast_assumptions"] = {
        "plan": fc.get("assumption_plan"),
        "news_effects": fc.get("news_assumptions") or [],
        "interim_scenario": fc.get("interim_scenario"),
        "outyear_scenario": fc.get("outyear_scenario"),
        "product_sales_scenario": doc_in.get("analyst_scenario"),
    }
    # Harness: single source of truth for Instruksi-Report-v3 compliance.
    # Engine + LLM call the same tools; critical blockers force draft.
    try:
        from .harness import run_all as _harness_run
        harness = _harness_run(doc_in, fc, va, doc)
    except Exception as e:  # fail closed
        harness = {"tool": "run_all", "status": "draft_non_distributable",
                   "blockers": [f"harness error: {e}"], "log_gate": {}}
    doc["harness"] = {"status": harness.get("status"),
                      "blockers": harness.get("blockers") or [],
                      "log_gate": harness.get("log_gate") or {}}
    # Fail closed: harness draft overrides any production claim from engine.
    if harness.get("status") == "draft_non_distributable" and \
            doc.get("meta", {}).get("status") != "draft_non_distributable":
        doc["meta"]["status"] = "draft_non_distributable"
        doc["meta"].pop("rating", None)
        doc["meta"].pop("tp", None)
        doc["meta"].pop("upside_persen", None)
    report_contract.validate_or_raise(doc)
    outdir.mkdir(parents=True, exist_ok=True)
    t = doc["meta"]["ticker"]
    (outdir / f"{t}.json").write_text(json.dumps(doc, indent=1))
    (outdir / f"{t}.html").write_text(render.render(doc))
    gates = {"G1": g1["G1"], "G2": fc["g2"], "G3": va["g3"]}
    print(f"{t} {doc['meta'].get('status', 'analysis')} "
          f"({len(doc.get('exhibits') or [])} exhibits)")
    release_result = va.get("release") or {}
    if release_result.get("status"):
        print(f"  release: {release_result['status']} "
              f"({len(release_result.get('blockers') or [])} blocker)")
    for stage, log in gates.items():
        flat = {k: (v if isinstance(v, str) else v[0]) for k, v in log.items()
                if not k.startswith("catatan")}
        bad = {k: v for k, v in flat.items() if "gagal" in v and "dilabeli" not in v}
        print(f"  {stage}: {'OK' if not bad else 'GAGAL ' + str(bad)} "
              f"({len(flat)} cek)")
    print(f"  harness: {harness.get('status')} "
          f"({len(harness.get('blockers') or [])} blocker)")
    if want_pdf:
        if pdf_mod is None:
            print("  pdf: Playwright tidak tersedia, HTML saja")
        else:
            print(f"  pdf: {pdf_mod.to_pdf(t, outdir)}")
    return doc


def main():
    p = argparse.ArgumentParser()
    p.add_argument("ticker")
    p.add_argument("--out", default=str(OUT))
    p.add_argument("--pdf", action="store_true")
    p.add_argument("--method", default="auto",
                   help="opsi valuasi analis: auto|dcf|ddm|rnav")
    p.add_argument("--as-of", default=date.today().isoformat(),
                   help="tanggal laporan YYYY-MM-DD (default: hari ini); harga tetap bertanggal sesuai data Sectors")
    p.add_argument("--illustrative-scenarios", action="store_true",
                   help="tambahkan screen historis dan valuasi ilustratif ke draft; bukan target harga")
    a = p.parse_args()
    try:
        build(a.ticker, Path(a.out), want_pdf=a.pdf, method=a.method,
              as_of=a.as_of, illustrative_scenarios=a.illustrative_scenarios)
    except ValueError as e:
        sys.exit(f"refused: {e}")


if __name__ == "__main__":
    main()
