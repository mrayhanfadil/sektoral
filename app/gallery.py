"""Report gallery: finished company updates in a local reports folder.

A batch run (``python -m app.batch ... --out out/reports --pdf``) writes
``{T}.html``, ``{T}.pdf`` and ``{T}-trace.html`` into the folder and stores the
report and audit-trace documents in the app database under that folder
(``app.outputs``). The gallery reads a small public summary from each report
document (rating, target, method, status, headline, method chain); the server
serves the HTML, PDF and trace HTML as files, the trace only through its public
view, and a cover thumbnail rendered from the PDF.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from . import outputs

TICKER = re.compile(r"^[A-Z0-9]{2,6}$")
PROFILE_LABEL = {"financial_ddm": "Bank", "finite_life_mining": "Tambang",
                 "going_concern_fcff": "Korporasi"}
FILES = {"pdf": ("{t}.pdf", "application/pdf"),
         "html": ("{t}.html", "text/html; charset=utf-8"),
         "trace": ("{t}-trace.html", "text/html; charset=utf-8")}


def _chain(doc):
    """Method-chain rows as (step, decision, value) from the report exhibit."""
    exhibit = next((e for e in doc.get("exhibits") or []
                    if e.get("judul") == "Rantai metode valuasi"), None)
    rows = ((exhibit or {}).get("data") or {}).get("rows") or []
    out = []
    for row in rows:
        if len(row) >= 3:
            step = re.sub(r"^\S+\.\s*", "", str(row[0])).replace(" (utama)", "")
            out.append({"step": step, "decision": str(row[1]), "value": str(row[2])})
    return out


def _held_reason(blockers) -> str:
    """Short reader label for why a draft holds its rating."""
    text = " ".join(str(b) for b in blockers).lower()
    if "extreme" in text:
        return "Method Gate 5, hasil ekstrem (Review Required)"
    if "peer" in text and "fewer than three" in text:
        return "peer valid kurang dari tiga"
    if "forecast" in text or "s2.9" in text:
        return "forecast belum tervalidasi"
    if "interim" in text or "s1" in text:
        return "rilis resmi terbaru belum lengkap"
    if "t4.discount_rate_currency" in text:
        return "discount rate belum sesuai mata uang pelaporan"
    if any(str(b).startswith("T.") for b in blockers):
        return "pemeriksaan format laporan belum lolos"
    return "bukti belum lengkap"


def summary(doc, folder: Path, stored_ticker: str) -> dict | None:
    """Public fields of one report document; None when it is not a report."""
    meta = doc.get("meta") if isinstance(doc, dict) else None
    if not isinstance(meta, dict) or not meta.get("ticker"):
        return None
    ticker = str(meta["ticker"]).upper()
    if not TICKER.fullmatch(ticker) or ticker != stored_ticker.upper():
        return None
    status = str(meta.get("status") or "")
    published = status.startswith("distributable")
    method = str(doc.get("method") or "")
    return {
        "ticker": ticker,
        "name": str(meta.get("emiten") or ticker),
        "date": str(meta.get("tanggal") or ""),
        "price": meta.get("harga"),
        "published": published,
        "rating": meta.get("rating") if published else None,
        "rating_status": meta.get("rating_status"),
        "tp": meta.get("tp") if published else None,
        "upside": meta.get("upside_persen") if published else None,
        "method": method.split(" [")[0],
        # Drafts carry no model_profile in meta; the run manifest still records it.
        "profile": PROFILE_LABEL.get(str(meta.get("model_profile")
                                         or (doc.get("run_manifest") or {}).get("profile") or ""), "Emiten"),
        "headline": str((doc.get("cover") or {}).get("headline") or ""),
        "risks": [str(r.get("judul")) for r in doc.get("risks") or [] if isinstance(r, dict)][:3],
        "chain": _chain(doc),
        "blockers": len((doc.get("harness") or {}).get("blockers") or []),
        "held_reason": _held_reason((doc.get("harness") or {}).get("blockers") or []),
        "files": {**{kind: (folder / pattern.format(t=ticker)).is_file()
                      for kind, (pattern, _) in FILES.items()},
                  "trace_json": outputs.exists(outputs.TRACE, folder, ticker)},
    }


def load(folder) -> list[dict]:
    """All reports in ``folder``: published first, then by ticker."""
    folder = Path(folder)
    items = [s for s in (summary(outputs.load(outputs.REPORT, folder, t), folder, t)
                         for t in outputs.tickers(outputs.REPORT, folder)
                         if TICKER.fullmatch(t)) if s]
    return sorted(items, key=lambda s: (not s["published"], s["ticker"]))


def artifact(folder, ticker: str, kind: str) -> tuple[Path, str] | None:
    """A served file for one ticker, confined to ``folder``."""
    ticker = str(ticker).upper()
    if not TICKER.fullmatch(ticker) or kind not in FILES:
        return None
    pattern, content_type = FILES[kind]
    folder = Path(folder).resolve()
    path = (folder / pattern.format(t=ticker)).resolve()
    if path.parent != folder or not path.is_file():
        return None
    return path, content_type


def cover(folder, ticker: str) -> Path | None:
    """PNG of page 1 of the ticker's PDF, rendered once into ``.thumbs``."""
    found = artifact(folder, ticker, "pdf")
    if not found or not shutil.which("pdftoppm"):
        return None
    pdf = found[0]
    thumbs = pdf.parent / ".thumbs"
    thumbs.mkdir(exist_ok=True)
    png = thumbs / f"{ticker.upper()}-cover.png"
    if not png.exists() or png.stat().st_mtime < pdf.stat().st_mtime:
        base = thumbs / f"{ticker.upper()}-cover"
        subprocess.run(["pdftoppm", "-png", "-r", "70", "-f", "1", "-l", "1", "-singlefile",
                        str(pdf), str(base)], check=True, timeout=60,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return png if png.exists() else None
