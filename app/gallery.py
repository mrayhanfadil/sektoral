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

from . import (assumption_review, exhibit_ids, outputs, publication_archive, publication_monitor,
               release_policy)

TICKER = re.compile(r"^[A-Z0-9]{2,6}$")
PROFILE_LABEL = {"financial_ddm": "Bank", "finite_life_mining": "Tambang",
                 "going_concern_fcff": "Korporasi"}
FILES = {"pdf": ("{t}.pdf", "application/pdf"),
         "html": ("{t}.html", "text/html; charset=utf-8"),
         "trace": ("{t}-trace.html", "text/html; charset=utf-8")}
ANALYTICALLY_ELIGIBLE = frozenset({"production_ready", "distributable",
                                   "distributable_assumption_led"})
RELEASE_STATUSES = ANALYTICALLY_ELIGIBLE | frozenset({"draft_non_distributable"})



def _freshness(folder, ticker) -> dict | None:
    """Stale label for a published report; never hides it (withdrawal is an event)."""
    try:
        decision = publication_monitor.assess(folder, ticker)
    except (OSError, ValueError, KeyError):
        return None
    if decision.get("state") not in {"stale", "withdrawal_due"}:
        return {"state": "current"}
    return {"state": decision["state"], "reason": decision.get("reason"),
            "triggers": [t.get("detail") for t in decision.get("triggers") or []]}

def _chain(doc):
    """Method-chain rows as (step, decision, value) from the report exhibit."""
    exhibit = exhibit_ids.find(doc.get("exhibits"), exhibit_ids.METHOD_CHAIN)
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


def _publication(doc, folder: Path, stored_ticker: str, db=None) -> dict:
    """Current publication decision shared by the gallery and artifact routes."""
    meta = doc.get("meta") if isinstance(doc, dict) else None
    ticker = str(meta.get("ticker") or "").upper() if isinstance(meta, dict) else ""
    valid_identity = (TICKER.fullmatch(ticker) is not None
                      and ticker == str(stored_ticker).upper())
    analytical = valid_identity and meta.get("status") in ANALYTICALLY_ELIGIBLE
    review = assumption_review.status(folder, ticker, db) if valid_identity else {
        "state": "no_report", "record": None}
    approved = review.get("state") == "approved"
    automatic = (analytical and not approved and release_policy.auto_publish_enabled()
                 and meta.get("status") in release_policy.AUTO_PUBLISH_STATUSES)
    publication_state = ("built" if not analytical else
                         "published" if approved else
                         "auto_published" if automatic else "review_pending")
    if analytical and review.get("state") == "approved":
        manifest = outputs.load(outputs.MANIFEST, folder, ticker, db)
        publication_id = manifest.get("publication_id") if isinstance(manifest, dict) else None
        if publication_id:
            lineage_state = publication_archive.publication_state(
                folder, ticker, publication_id, db)
            if lineage_state in {"withdrawn", "superseded", "history_invalid"}:
                publication_state = ("history_invalid" if lineage_state == "history_invalid"
                                     else lineage_state)
                return {"analytically_eligible": analytical,
                        "publication_state": publication_state,
                        "review": review, "published": False}
    return {"analytically_eligible": analytical,
            "publication_state": publication_state,
            "review": review,
            "published": analytical and (approved or automatic),
            "basis": ("analyst_reviewed" if analytical and approved else
                      "automatic" if automatic else None)}


def is_publishable(folder, ticker: str, db=None) -> bool:
    """Whether the current report and its review permit any public artifact."""
    ticker = str(ticker).upper()
    if not TICKER.fullmatch(ticker):
        return False
    doc = outputs.load(outputs.REPORT, folder, ticker, db)
    return _publication(doc, folder, ticker, db)["published"]


def summary(doc, folder: Path, stored_ticker: str) -> dict | None:
    """Public fields of one report document; None when it is not a report.

    A report is published only when its release gate passed and, with
    ``require_review``, an analyst approved the Forecast Plan it was built on
    (app.assumption_review); until then it is a draft awaiting review.
    """
    meta = doc.get("meta") if isinstance(doc, dict) else None
    if not isinstance(meta, dict) or not meta.get("ticker"):
        return None
    ticker = str(meta["ticker"]).upper()
    if not TICKER.fullmatch(ticker) or ticker != stored_ticker.upper():
        return None
    publication = _publication(doc, folder, ticker)
    releasable = publication["analytically_eligible"]
    review = publication["review"]
    published = publication["published"]
    reviewed = review.get("record") or {}
    method = str(doc.get("method") or "")
    return {
        "ticker": ticker,
        "name": str(meta.get("emiten") or ticker),
        "date": str(meta.get("tanggal") or ""),
        "release_status": (meta.get("status") if meta.get("status") in RELEASE_STATUSES
                           else "draft_non_distributable"),
        "analytically_eligible": releasable,
        "publication_state": publication["publication_state"],
        "price": meta.get("harga"),
        "published": published,
        # Policy 1.3.0: "automatic" (gates passed, not analyst-reviewed) or
        # "analyst_reviewed" (an authenticated approval of this bundle).
        "publication_basis": publication.get("basis"),
        "rating": meta.get("rating") if published else None,
        "rating_status": meta.get("rating_status"),
        "tp": meta.get("tp") if published else None,
        "upside": meta.get("upside_persen") if published else None,
        "method": method.split(" [")[0] if published else "",
        # Drafts carry no model_profile in meta; the run manifest still records it.
        "profile": PROFILE_LABEL.get(str(meta.get("model_profile")
                                         or (doc.get("run_manifest") or {}).get("profile") or ""), "Emiten"),
        "headline": str((doc.get("cover") or {}).get("headline") or "") if published else "",
        "risks": ([str(r.get("judul")) for r in doc.get("risks") or [] if isinstance(r, dict)][:3]
                  if published else []),
        # Unapproved method choices, blockers and thesis text stay on the
        # authenticated preview; the public gallery only says review is pending.
        "chain": _chain(doc) if published else [],
        "blockers": (len((doc.get("harness") or {}).get("blockers") or [])
                     if published else None),
        "held_reason": ("" if published else
                        "publikasi ini ditarik" if publication["publication_state"] == "withdrawn" else
                        "riwayat publikasi tidak valid" if publication["publication_state"] == "history_invalid" else
                        "publikasi ini telah digantikan" if publication["publication_state"] == "superseded" else
                        "menunggu review publikasi oleh reviewer" if releasable else
                        "laporan belum tersedia untuk umum"),
        # Release policy 1.2.0: a published view stays visible but is labelled
        # stale once a newer official period is due or has been published.
        "freshness": (_freshness(folder, ticker) if published else None),
        "review": {"state": review["state"], "reviewer": reviewed.get("reviewer"),
                   "reviewed_at": reviewed.get("reviewed_at"),
                   "decision": reviewed.get("decision"),
                   "edits": len(assumption_review.plan_edits(reviewed))},
        "files": {**{kind: published and (folder / pattern.format(t=ticker)).is_file()
                      for kind, (pattern, _) in FILES.items()},
                  "trace_json": published and outputs.exists(outputs.TRACE, folder, ticker)},
    }


def load(folder) -> list[dict]:
    """All reports in ``folder``: published first, then by ticker."""
    folder = Path(folder)
    items = [s for s in (summary(outputs.load(outputs.REPORT, folder, t), folder, t)
                         for t in outputs.tickers(outputs.REPORT, folder)
                         if TICKER.fullmatch(t)) if s]
    return sorted(items, key=lambda s: (not s["published"], s["ticker"]))


def artifact(folder, ticker: str, kind: str) -> tuple[Path, str] | None:
    """A physical file for one ticker, confined to ``folder`` (no release check)."""
    ticker = str(ticker).upper()
    if not TICKER.fullmatch(ticker) or kind not in FILES:
        return None
    pattern, content_type = FILES[kind]
    folder = Path(folder).resolve()
    path = (folder / pattern.format(t=ticker)).resolve()
    if path.parent != folder or not path.is_file():
        return None
    return path, content_type


def public_artifact(folder, ticker: str, kind: str, db=None) -> tuple[Path, str] | None:
    """A file from the currently approved, analytically eligible report bundle."""
    if not is_publishable(folder, ticker, db):
        return None
    return artifact(folder, ticker, kind)


def cover(folder, ticker: str) -> Path | None:
    """PNG of page 1 of the current approved PDF, cached by its content hash."""
    found = public_artifact(folder, ticker, "pdf")
    if not found or not shutil.which("pdftoppm"):
        return None
    review = assumption_review.status(folder, str(ticker).upper())
    pdf_sha = (review.get("artifact_hashes") or {}).get("pdf")
    if review.get("state") != "approved" or not pdf_sha:
        return None
    pdf = found[0]
    thumbs = pdf.parent / ".thumbs"
    thumbs.mkdir(exist_ok=True)
    png = thumbs / f"{ticker.upper()}-{pdf_sha[:16]}-cover.png"
    if not png.exists():
        base = png.with_suffix("")
        subprocess.run(["pdftoppm", "-png", "-r", "70", "-f", "1", "-l", "1", "-singlefile",
                        str(pdf), str(base)], check=True, timeout=60,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return png if png.exists() else None
