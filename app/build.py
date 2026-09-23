"""Pipeline v3: cache market data, local official source packs, report build."""
import argparse
import json
import sys
from pathlib import Path

from . import forecast, intake, narrative, render, report_contract, valuation

PDF_OK = True
try:
    from . import pdf as pdf_mod
except Exception:
    pdf_mod = None

OUT = Path(__file__).resolve().parent.parent / "out"


def build(ticker, outdir=OUT, want_pdf=False, method="auto", as_of=None):
    doc_in, g1 = intake.load(ticker, as_of=as_of)
    fc = forecast.build(doc_in)
    va = valuation.build(doc_in, fc)
    doc = narrative.build(doc_in, fc, va, g1, method=method)
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
    p.add_argument("--as-of", default=None,
                   help="tanggal laporan YYYY-MM-DD; harga tetap bertanggal sesuai cache")
    a = p.parse_args()
    try:
        build(a.ticker, Path(a.out), want_pdf=a.pdf, method=a.method,
              as_of=a.as_of)
    except ValueError as e:
        sys.exit(f"refused: {e}")


if __name__ == "__main__":
    main()
