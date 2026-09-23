"""Pipeline v3: intake → forecast → valuation → narrative → render.

Facts are read only from data/sectors_cache.db. No network, LLM, analyst
driver files, or local operating-profile files enter the report build. A
separate agent-written news note is included only after matching it back to
the ticker-specific cached news rows.
"""
import argparse
import json
import sys
from pathlib import Path

from . import forecast, intake, narrative, render, valuation

PDF_OK = True
try:
    from . import pdf as pdf_mod
except Exception:
    pdf_mod = None

OUT = Path(__file__).resolve().parent.parent / "out"


def build(ticker, outdir=OUT, want_pdf=False, method="auto"):
    doc_in, g1 = intake.load(ticker)
    fc = forecast.build(doc_in)
    va = valuation.build(doc_in, fc)
    doc = narrative.build(doc_in, fc, va, g1, method=method)
    outdir.mkdir(parents=True, exist_ok=True)
    t = doc["meta"]["ticker"]
    (outdir / f"{t}.json").write_text(json.dumps(doc, indent=1))
    (outdir / f"{t}.html").write_text(render.render(doc))
    gates = {"G1": g1["G1"], "G2": fc["g2"], "G3": va["g3"]}
    tp = doc["meta"].get("tp")
    upside = doc["meta"].get("upside_persen")
    tp_text = f"Rp{tp:,}" if tp is not None else "Ditahan"
    upside_text = f"{upside}%" if upside is not None else "n.a."
    print(f"{t} {doc['meta']['rating']} TP {tp_text} upside {upside_text}")
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
    a = p.parse_args()
    try:
        build(a.ticker, Path(a.out), want_pdf=a.pdf, method=a.method)
    except ValueError as e:
        sys.exit(f"refused: {e}")


if __name__ == "__main__":
    main()
