"""Renderer HTML minimal, print-friendly. Styling inline, tanpa dependensi."""
import html

CSS = """body{font-family:Georgia,serif;max-width:820px;margin:2rem auto;padding:0 1.2rem;
color:#1c1a17;background:#fdfcf9;line-height:1.65}
h1{font-size:1.7rem;margin:.2rem 0}h2{font-size:1.25rem;margin-top:2.2rem;
border-bottom:1px solid #d8d2c6;padding-bottom:.3rem}
.meta{font-family:ui-monospace,monospace;font-size:.85rem;color:#5c564a}
.badge{display:inline-block;background:#1f4d2e;color:#fff;padding:.15rem .7rem;
border-radius:999px;font-size:.85rem;font-family:system-ui}
table{border-collapse:collapse;width:100%;margin:.8rem 0;font-size:.85rem}
th,td{border:1px solid #d8d2c6;padding:.35rem .5rem;text-align:right}
th:first-child,td:first-child{text-align:left}
th{background:#f3efe4}caption{text-align:left;font-weight:bold;margin-bottom:.3rem}
.src{font-size:.75rem;color:#5c564a}.page{page-break-before:always}
.bullets li{margin-bottom:.4rem}@media print{.page{margin-top:0}}"""


def _table(ex):
    d = ex["data"]
    rows = "".join("<tr>" + "".join(f"<td>{html.escape(str(c))}</td>" for c in r)
                   + "</tr>" for r in d["rows"])
    head = "".join(f"<th>{html.escape(str(c))}</th>" for c in d["cols"])
    return (f"<table><caption>Exhibit {ex['n']}. {html.escape(ex['judul'])}</caption>"
            f"<tr>{head}</tr>{rows}</table>"
            f"<p class='src'>{html.escape(ex['catatan_sumber'])}</p>")


def render(doc):
    m, cov = doc["meta"], doc["cover"]
    h = [f"<html><head><meta charset='utf-8'><style>{CSS}</style></head><body>"]
    h.append(f"<p class='meta'>Company Update | {html.escape(str(m['tanggal']))} | "
             f"{html.escape(m['ticker'])}</p>")
    h.append(f"<p><span class='badge'>{html.escape(m['rating'])}</span></p>")
    h.append(f"<h1>{html.escape(m['emiten'])} ({html.escape(m['ticker'])})</h1>")
    h.append(f"<h2>{html.escape(cov['headline'])}</h2>")
    h.append("<ul class='bullets'>" + "".join(f"<li>{html.escape(b)}</li>"
                                              for b in cov["bullets"]) + "</ul>")
    for p in cov["paragraf"]:
        h.append(f"<h2>{html.escape(p['judul'])}</h2><p>{html.escape(p['isi'])}</p>")
    by_n = {e["n"]: e for e in doc["exhibits"]}
    h.append(_table(by_n[1]))
    for b in doc["bagian"]:
        h.append(f"<div class='page'><h2>Halaman {b['halaman']}: "
                 f"{html.escape(b['judul'])}</h2>")
        for p in b["paragraf"]:
            h.append(f"<p>{html.escape(p)}</p>")
        for e in b["exhibit"]:
            h.append(_table(e))
        h.append("</div>")
    h.append("<div class='page'><h2>Catatan metodologi</h2><ul>" + "".join(
        f"<li>{html.escape(c)}</li>" for c in doc["catatan_metodologi"]) + "</ul>"
        "<p class='src'>Sumber data: cache Sectors (snapshot, tanpa akses upstream). "
        "Bukan rekomendasi transaksi otomatis.</p></div>")
    h.append("</body></html>")
    return "\n".join(h)
