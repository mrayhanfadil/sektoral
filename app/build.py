"""Pipeline v3: cache market data, local official source packs, report build."""
import argparse
import sys
from datetime import date
from pathlib import Path

from . import evidence as evidence_mod, forecast, intake, narrative, outputs, render, report_contract, report_extras, run_manifest, scrub, valuation

PDF_OK = True
try:
    from . import pdf as pdf_mod
except Exception:
    pdf_mod = None

OUT = Path(__file__).resolve().parent.parent / "out"


def build(ticker, outdir=OUT, want_pdf=False, method="auto", as_of=None,
          illustrative_scenarios=False, assumption_plan=None,
          analyst_target=False, assumption_status=None, news_evidence=None,
          method_override=None, spec_sha=None):
    doc_in, s1 = intake.load(ticker, as_of=as_of)
    if news_evidence is not None:
        doc_in["news"] = news_evidence["rows"]
        doc_in["news_full"] = news_evidence["full"]
        doc_in["news_search"] = news_evidence["search"]
    fc = forecast.build(doc_in, assumption_plan=assumption_plan)
    # --method <key>: analis override; sistem tetap simpan proposed order.
    # "auto" berarti tanpa override. Nilai diteruskan ke valuation.
    _override = None if (method_override or method) in (None, "auto") else (method_override or method)
    va = valuation.build(doc_in, fc, analyst_target=analyst_target,
                         assumption_status=assumption_status,
                         method_override=_override,
                         assumption_plan=assumption_plan or fc.get("assumption_plan"))
    doc = narrative.build(doc_in, fc, va, s1, method=method,
                          illustrative_scenarios=illustrative_scenarios or analyst_target)
    report_extras.enrich(doc, doc_in, report_extras.valuation_inputs(doc_in, fc, va), va=va, fc=fc)
    doc = narrative.client_copy(doc)
    scrub.normalize_doc_prose(doc)
    doc["forecast_assumptions"] = {
        "plan": fc.get("assumption_plan"),
        "news_effects": fc.get("news_assumptions") or [],
        "interim_scenario": fc.get("interim_scenario"),
        "outyear_scenario": fc.get("outyear_scenario"),
        "product_sales_scenario": doc_in.get("analyst_scenario"),
    }
    try:
        doc["evidence_register"] = evidence_mod.build(
            ticker, doc["meta"].get("tanggal") or as_of, doc_in,
            doc_in.get("news") or [], doc_in.get("news_full") or [],
            fc.get("assumption_plan"))
    except Exception as e:
        print(f"  evidence_register gagal: {e}", flush=True)
        doc["evidence_register"] = {"ticker": str(ticker).upper(), "rows": [],
                                    "violations": [], "error": str(e)}
    for violation in doc["evidence_register"].get("violations") or []:
        print(f"  PERINGATAN look-ahead: {violation}", flush=True)
    # Harness: single source of truth for Instruksi-Report-v3 compliance.
    # Engine + LLM call the same tools; critical blockers force draft.
    try:
        from .harness import run_all as _harness_run
        harness = _harness_run(doc_in, fc, va, doc, assumption_status=assumption_status)
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
    # With the release status final, drop screening values that would read as
    # a withheld or second target.
    report_extras.drop_screening_values(doc)
    # State that the published value is an analyst model scenario.
    meta = doc["meta"]
    rating_status = ("Skenario nilai indikatif"
                     if meta.get("status") != "draft_non_distributable" else
                     "Dalam peninjauan")
    meta["rating_status"] = rating_status
    if isinstance(doc.get("cover"), dict):
        doc["cover"]["rating_status"] = rating_status
    # Immutable run manifest, built once after the harness so it records the
    # final release (not the engine's pre-harness status). research.run
    # reuses this object instead of rebuilding it.
    try:
        doc["run_manifest"] = run_manifest.build_manifest(
            ticker=ticker, as_of=doc["meta"].get("tanggal") or as_of,
            intake=doc_in, forecast=fc,
            valuation={"method": va.get("method"), "tp": doc["meta"].get("tp")},
            news_evidence={"rows": doc_in.get("news") or [],
                           "full": doc_in.get("news_full") or [],
                           "search": doc_in.get("news_search") or {}},
            assumption_plan=fc.get("assumption_plan"),
            release={"status": doc["meta"].get("status"),
                     "engine_status": (va.get("release") or {}).get("status"),
                     "blockers": doc["harness"]["blockers"]},
            spec_sha=spec_sha)
    except Exception as e:
        print(f"  run_manifest gagal: {e}", flush=True)
        doc["run_manifest"] = {"ticker": str(ticker).upper(), "error": str(e)}
    report_contract.validate_or_raise(doc)
    from . import run_events  # lazy: run_events reads app.jobs, which imports this module
    run_events.emit_valuation(doc)
    outdir.mkdir(parents=True, exist_ok=True)
    t = doc["meta"]["ticker"]
    outputs.save(outputs.REPORT, outdir, t, doc)
    (outdir / f"{t}.html").write_text(render.render(doc))
    gates = {"S1": s1["S1"], "S2": fc["s2"], "S3": va["s3"]}
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
                   help="override analis: auto atau method key (fcff_dcf, relative_pe, ddm, pbv_roe, sotp_lom, rnav_lom, ev_ebitda_fy, pe_fy_scenario, ev_ebitda_peer, ev_sales_peer, pbv_relative, holding_sotp, property_nav, dcf_reference)")
    p.add_argument("--as-of", default=date.today().isoformat(),
                   help="tanggal laporan YYYY-MM-DD (default: hari ini); harga tetap bertanggal sesuai data Sectors")
    p.add_argument("--illustrative-scenarios", action="store_true",
                   help="tambahkan screen historis dan valuasi ilustratif ke draft; bukan target harga")
    a = p.parse_args()
    try:
        build(a.ticker, Path(a.out), want_pdf=a.pdf, method=a.method,
              method_override=None if a.method == "auto" else a.method,
              as_of=a.as_of, illustrative_scenarios=a.illustrative_scenarios)
    except ValueError as e:
        sys.exit(f"refused: {e}")


if __name__ == "__main__":
    main()
