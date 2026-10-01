"""Report gallery: finished company updates in a local reports folder.

A batch run (``python -m app.batch ... --out out/reports --pdf``) writes
``{T}.html``, ``{T}.pdf`` and ``{T}-trace.html`` into the folder and stores the
report and audit-trace documents in the app database under that folder
(``app.outputs``). The gallery reads a small public summary from each report
document (rating, target, method, status, headline, method chain); the server
serves the HTML, PDF and trace HTML as files, the trace only through its public
view, and a cover thumbnail rendered from the PDF.

The cover is keyed on the published bundle's PDF hash on either basis, and
only a PDF that still has those bytes gets one; an English reader gets the
English PDF's cover when that PDF is in the bundle (#45).

The English edition (``{T}.en.html``/``.en.pdf``) is public only as part of the
published bundle (ADR 0015): its kind must be in the bundle and the file on
disk must still carry the bundle's SHA-256.

A summary's Indonesian fields keep their English beside them as
``<field>_en`` (#34): the report's own English prose (``cover.headline_en``,
``risks[].judul_en``) and, for the labels the host writes, ``app.host_lang``.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from . import (assumption_review, exhibit_ids, host_lang, outputs, publication_archive,
               publication_monitor, release_policy, report_extras, report_lang, run_manifest)

TICKER = re.compile(r"^[A-Z0-9]{2,6}$")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PROFILE_LABEL = {"financial_ddm": "Bank", "finite_life_mining": "Tambang",
                 "going_concern_fcff": "Korporasi"}
FILES = {"pdf": ("{t}.pdf", "application/pdf"),
         "html": ("{t}.html", "text/html; charset=utf-8"),
         "trace": ("{t}-trace.html", "text/html; charset=utf-8")}
# The English Company Update (app.report_lang) sits beside the Indonesian
# files. A public route serves it only when it is in the published bundle and
# unchanged since (ADR 0015); a reviewer preview serves whatever file exists.
ENGLISH_FILES = {"html_en": ("{t}.en.html", "text/html; charset=utf-8"),
                 "pdf_en": ("{t}.en.pdf", "application/pdf")}
PREVIEW_FILES = {**FILES, **ENGLISH_FILES}
# Languages a reader may open from a public route, with their HTML kind.
PUBLIC_LANGUAGES = {"id": "html", "en": "html_en"}
# The PDF whose first page is the cover thumbnail, per reader language.
COVER_KINDS = {"id": "pdf", "en": "pdf_en"}
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
    triggers = [t.get("detail") for t in decision.get("triggers") or []]
    return {"state": decision["state"], "reason": decision.get("reason"),
            "reason_en": host_lang.english(decision.get("reason")), "triggers": triggers,
            "triggers_en": [host_lang.english(t) for t in triggers]}

def _chain(doc):
    """Method-chain rows as (step, decision, decision_code, value) from the report exhibit;
    ``value_en`` is the value as the English report prints it ("Rp3,490")."""
    exhibit = exhibit_ids.find(doc.get("exhibits"), exhibit_ids.METHOD_CHAIN)
    rows = ((exhibit or {}).get("data") or {}).get("rows") or []
    out = []
    for row in rows:
        if len(row) >= 3:
            step = re.sub(r"^\S+\.\s*", "", str(row[0])).replace(" (utama)", "")
            out.append({"step": step, "step_en": host_lang.english(step), "decision": str(row[1]),
                        "decision_code": report_extras.decision_code(row[1]), "value": str(row[2]),
                        "value_en": report_lang.plain(str(row[2]))})
    return out


def _iso_date(value) -> str | None:
    """``value`` when it is an ISO date ("2026-09-24"), else None."""
    return value if isinstance(value, str) and ISO_DATE.fullmatch(value) else None


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
    published = analytical and (approved or automatic)
    return {"analytically_eligible": analytical,
            "publication_state": publication_state,
            "review": review,
            "published": published,
            "basis": ("analyst_reviewed" if analytical and approved else
                      "automatic" if automatic else None),
            "bundle": (_bundle(review, folder, ticker, db, approved=approved)
                       if published else {})}


def _bundle(review, folder, ticker, db=None, *, approved) -> dict:
    """{kind: sha256} of the bundle a published report stands on (ADR 0015).

    Analyst-reviewed: the approved record's ``artifact_hashes``. Automatic
    (ADR 0014): the finalized run manifest's ``artifacts``, the files the
    build hashed when it finished."""
    if approved:
        hashes = (review.get("record") or {}).get("artifact_hashes")
        return dict(hashes) if isinstance(hashes, dict) else {}
    manifest = outputs.load(outputs.MANIFEST, folder, ticker, db)
    listed = manifest.get("artifacts") if isinstance(manifest, dict) else None
    return {kind: row["sha256"] for kind, row in (listed or {}).items()
            if isinstance(row, dict) and run_manifest.re_full_sha(row.get("sha256"))}


def _in_bundle(folder, ticker: str, kind: str, bundle: dict) -> bool:
    """Whether a file is in the bundle and still has its bundle bytes."""
    expected = bundle.get(kind)
    found = artifact(folder, ticker, kind)
    return (found is not None and isinstance(expected, str)
            and run_manifest.file_sha256(found[0]) == expected)


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
    method = str(doc.get("method") or "").split(" [")[0]
    profile = PROFILE_LABEL.get(str(meta.get("model_profile")
                                    or (doc.get("run_manifest") or {}).get("profile") or ""), "Emiten")
    cover = doc.get("cover") if isinstance(doc.get("cover"), dict) else {}
    headline = str(cover.get("headline") or "")
    risks = [r for r in doc.get("risks") or [] if isinstance(r, dict)][:3]
    held_reason = ("" if published else
                   "publikasi ini ditarik" if publication["publication_state"] == "withdrawn" else
                   "riwayat publikasi tidak valid" if publication["publication_state"] == "history_invalid" else
                   "publikasi ini telah digantikan" if publication["publication_state"] == "superseded" else
                   "menunggu review publikasi oleh reviewer" if releasable else
                   "laporan belum tersedia untuk umum")
    bundle = publication.get("bundle") or {}
    files = {**{kind: published and (folder / pattern.format(t=ticker)).is_file()
                for kind, (pattern, _) in FILES.items()},
             "trace_json": published and outputs.exists(outputs.TRACE, folder, ticker),
             **{kind: published and _in_bundle(folder, ticker, kind, bundle)
                for kind in ENGLISH_FILES}}
    return {
        "ticker": ticker,
        "name": str(meta.get("emiten") or ticker),
        "date": str(meta.get("tanggal") or ""),
        "release_status": (meta.get("status") if meta.get("status") in RELEASE_STATUSES
                           else "draft_non_distributable"),
        "analytically_eligible": releasable,
        "publication_state": publication["publication_state"],
        "price": meta.get("harga"),
        # The close the price is (``harga_tanggal``), not the report date.
        "price_date": _iso_date(meta.get("harga_tanggal")),
        "published": published,
        # Policy 1.3.0: "automatic" (gates passed, not analyst-reviewed) or
        # "analyst_reviewed" (an authenticated approval of this bundle).
        "publication_basis": publication.get("basis"),
        "rating": meta.get("rating") if published else None,
        "rating_status": meta.get("rating_status"),
        "tp": meta.get("tp") if published else None,
        "upside": meta.get("upside_persen") if published else None,
        "method": method if published else "",
        "method_en": host_lang.english(method) if published else None,
        # Drafts carry no model_profile in meta; the run manifest still records it.
        "profile": profile,
        "profile_en": host_lang.PROFILES.get(profile),
        "headline": headline if published else "",
        "headline_en": ((cover.get("headline_en") if isinstance(cover.get("headline_en"), str)
                         else host_lang.english(headline)) if published else None),
        "risks": [str(r.get("judul")) for r in risks] if published else [],
        # The report's English risk titles, a parallel list; None when it has none.
        "risks_en": ([r.get("judul_en") if isinstance(r.get("judul_en"), str) else None
                      for r in risks]
                     if published and any(isinstance(r.get("judul_en"), str) for r in risks)
                     else None),
        # Unapproved method choices, blockers and thesis text stay on the
        # authenticated preview; the public gallery only says review is pending.
        "chain": _chain(doc) if published else [],
        "blockers": (len((doc.get("harness") or {}).get("blockers") or [])
                     if published else None),
        "held_reason": held_reason,
        "held_reason_en": host_lang.english(held_reason),
        # Release policy 1.2.0: a published view stays visible but is labelled
        # stale once a newer official period is due or has been published.
        "freshness": (_freshness(folder, ticker) if published else None),
        "review": {"state": review["state"], "reviewer": reviewed.get("reviewer"),
                   "reviewed_at": reviewed.get("reviewed_at"),
                   "decision": reviewed.get("decision"),
                   "edits": len(assumption_review.plan_edits(reviewed))},
        "files": files,
        # Report languages a reader can open now (see PUBLIC_LANGUAGES).
        "languages": [lang for lang, kind in PUBLIC_LANGUAGES.items() if files[kind]],
    }


def load(folder) -> list[dict]:
    """All reports in ``folder``: published first, then by ticker."""
    folder = Path(folder)
    items = [s for s in (summary(outputs.load(outputs.REPORT, folder, t), folder, t)
                         for t in outputs.tickers(outputs.REPORT, folder)
                         if TICKER.fullmatch(t)) if s]
    return sorted(items, key=lambda s: (not s["published"], s["ticker"]))


def artifact(folder, ticker: str, kind: str) -> tuple[Path, str] | None:
    """A physical file for one ticker, confined to ``folder`` (no release check).

    ``kind`` is one of PREVIEW_FILES; public callers go through public_artifact."""
    ticker = str(ticker).upper()
    if not TICKER.fullmatch(ticker) or kind not in PREVIEW_FILES:
        return None
    pattern, content_type = PREVIEW_FILES[kind]
    folder = Path(folder).resolve()
    path = (folder / pattern.format(t=ticker)).resolve()
    if path.parent != folder or not path.is_file():
        return None
    return path, content_type


def public_artifact(folder, ticker: str, kind: str, db=None) -> tuple[Path, str] | None:
    """A file from the currently published, analytically eligible report bundle.

    An English file also has to be in that bundle with its bytes unchanged."""
    ticker = str(ticker).upper()
    if kind not in PREVIEW_FILES or not TICKER.fullmatch(ticker):
        return None
    doc = outputs.load(outputs.REPORT, folder, ticker, db)
    publication = _publication(doc, folder, ticker, db)
    if not publication["published"]:
        return None
    if kind in ENGLISH_FILES and not _in_bundle(folder, ticker, kind,
                                                 publication.get("bundle") or {}):
        return None
    return artifact(folder, ticker, kind)


def cover(folder, ticker: str, lang: str = "id", db=None) -> Path | None:
    """PNG of page 1 of the published PDF in ``lang``, cached by its bundle hash.

    The hash is the bundle's on either basis: the approved record's, or the
    finalized run manifest's on the automatic basis (ADR 0014), the same
    bundle that gates the English files. A PDF whose bytes no longer match it
    gets no cover, and neither does a language whose PDF is not in the bundle."""
    ticker = str(ticker).upper()
    kind = COVER_KINDS.get(lang)
    if kind is None or not TICKER.fullmatch(ticker) or not shutil.which("pdftoppm"):
        return None
    doc = outputs.load(outputs.REPORT, folder, ticker, db)
    publication = _publication(doc, folder, ticker, db)
    bundle = publication.get("bundle") or {}
    if not publication["published"] or not _in_bundle(folder, ticker, kind, bundle):
        return None
    pdf = artifact(folder, ticker, kind)[0]
    thumbs = pdf.parent / ".thumbs"
    thumbs.mkdir(exist_ok=True)
    png = thumbs / f"{ticker}-{bundle[kind][:16]}-cover.png"
    if not png.exists():
        base = png.with_suffix("")
        subprocess.run(["pdftoppm", "-png", "-r", "70", "-f", "1", "-l", "1", "-singlefile",
                        str(pdf), str(base)], check=True, timeout=60,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return png if png.exists() else None
