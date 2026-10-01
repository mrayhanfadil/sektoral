"""Sectoral web server: JSON API, generated documents and the React app.

Run with ``python -m app.server`` after building the frontend
(``npm --prefix web run build``). The server binds to loopback unless told
otherwise; the Docker image binds to all interfaces inside the container.

Routes:

* ``/api/...``   JSON for the React app (tickers, research history, reports,
  research jobs, audit traces). Only whitelisted fields are returned.
* ``/files/...`` generated documents: company update HTML/PDF (the English
  edition too when it is in the published bundle), the standalone trace HTML
  and report cover thumbnails (``cover.en.png`` from the English PDF), each
  confined to its folder.
* everything else: the built single-page app from ``web/dist``.
"""
from __future__ import annotations

import argparse
from contextlib import asynccontextmanager
import hmac
import logging
import os
from pathlib import Path
import re

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from . import (assumption_review, gallery, host_lang, outputs, publication_archive,
               release_policy, report_lang, reviewer_auth, run_events, trace_view)
from .jobs import ResearchJobs, TICKER, available_tickers
from agents.analyst import memory as agent_memory

LOG = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "web" / "dist"
# ``TICKER.en.html``/``.en.pdf`` are served only while they are in the
# published bundle, unchanged (gallery.public_artifact, ADR 0015).
_REPORT_FILE = re.compile(r"^([A-Z0-9]{2,6})(\.en\.html|\.en\.pdf|\.html|\.pdf|-trace\.html)$")
_KIND = {".html": "html", ".pdf": "pdf", "-trace.html": "trace",
         ".en.html": "html_en", ".en.pdf": "pdf_en"}
# Archived files by route kind: (archive kind, media type).
_ARCHIVE_KINDS = {"html": ("html", "text/html; charset=utf-8"),
                  "pdf": ("pdf", "application/pdf"),
                  "trace": ("trace_html", "text/html; charset=utf-8"),
                  "html_en": ("html_en", "text/html; charset=utf-8"),
                  "pdf_en": ("pdf_en", "application/pdf")}
_NO_STORE = {"Cache-Control": "no-store"}
# A republish rewrites report files in place under the same URL, so a proxy or
# browser must revalidate (ETag) before reusing a copy; Cloudflare then skips caching.
_REVALIDATE = {"Cache-Control": "no-cache"}


class JobRequest(BaseModel):
    ticker: str


class ReviewEdit(BaseModel):
    path: str
    value: float
    reason: str


class ReviewRequest(BaseModel):
    # Retained for old clients. Server-side identity comes from the reviewer
    # token registry, so the client-supplied value is ignored.
    reviewer: str = ""
    note: str = ""
    supersession_reason: str = ""
    edits: list[ReviewEdit] = []
    attestation: dict | None = None


class WithdrawalRequest(BaseModel):
    reason: str


def live_runs() -> str:
    """Who may start a live (paid) research run: "open" (anyone, the local
    default), "token" (only with ``SECTORAL_RUN_TOKEN``, the public
    deployment) or "off". Visitors can always replay stored runs."""
    mode = (os.environ.get("SECTORAL_LIVE_RUNS") or "open").strip().lower()
    return mode if mode in ("open", "token", "off") else "token"


def run_token_ok(given: str | None) -> bool:
    expected = os.environ.get("SECTORAL_RUN_TOKEN") or ""
    return bool(expected) and hmac.compare_digest(str(given or ""), expected)


def review_token_ok(given: str | None) -> bool:
    """True only when a token resolves to a configured reviewer identity."""
    return reviewer_auth.authenticate(given) is not None


def _history(reports: Path) -> list[dict]:
    try:
        rows = agent_memory.watchlist()[:6]
    except OSError:
        return []
    return [{"ticker": r["ticker"], "runs": r["runs"], "market_date": r.get("market_date"),
             "flags": r["flags"],
             "pdf_url": f"/files/reports/{r['ticker']}.pdf"
             if gallery.public_artifact(reports, r["ticker"], "pdf") else None}
            for r in rows]


def _audit_appendix(doc) -> list[dict]:
    """Report sections kept out of the printed report (``lampiran_audit``):
    their prose and tables, as plain text, bounded.

    Each carries its English as the English Company Update would print it:
    headings and cells through ``report_lang``, prose and source notes from
    the report's English twins (``paragraf_en``, ``catatan_sumber_en``; a
    report built before them has none) or a known sentence (``host_lang``)."""
    cell = lambda v: str(v if v is not None else "")[:300]
    label = lambda v: cell(report_lang.label(cell(v), "en"))

    def prose(id_text, en_text, limit):
        """The report's English twin (figures in English), else a known sentence."""
        if isinstance(en_text, str) and en_text.strip():
            return report_lang.plain(en_text)[:limit]
        found = host_lang.english(id_text)
        return found[:limit] if found else None

    out = []
    for page in ((doc or {}).get("lampiran_audit") or [])[:40]:
        if not isinstance(page, dict):
            continue
        exhibits = []
        for e in (page.get("exhibit") or [])[:8]:
            data = e.get("data") if isinstance(e.get("data"), dict) else {}
            if e.get("tipe") != "tabel" or not isinstance(data.get("rows"), list):
                continue
            rows = [row[:12] for row in data["rows"][:60] if isinstance(row, list)]
            # Cells the English prose run wrote itself (``rows_en``), as render._cell prints them.
            written = data.get("rows_en") if isinstance(data.get("rows_en"), list) else []

            def english(r, i, value):
                row_en = written[r] if r < len(written) and isinstance(written[r], list) else []
                own = row_en[i] if i < len(row_en) else None
                return cell(own) if isinstance(own, str) else label(value)
            exhibits.append({"title": cell(e.get("judul")),
                             "title_en": cell(report_lang.title(e, "en")),
                             "cols": [cell(c) for c in (data.get("cols") or [])[:12]],
                             "cols_en": [label(c) for c in (data.get("cols") or [])[:12]],
                             "rows": [[cell(c) for c in row] for row in rows],
                             "rows_en": [[english(r, i, c) for i, c in enumerate(row)]
                                         for r, row in enumerate(rows)],
                             "note": str(e.get("catatan_sumber") or "")[:1500],
                             "note_en": prose(e.get("catatan_sumber"), e.get("catatan_sumber_en"),
                                              1500)})
        paragraphs = [(i, x) for i, x in enumerate((page.get("paragraf") or [])[:8])
                      if isinstance(x, str)]
        english = page.get("paragraf_en") if isinstance(page.get("paragraf_en"), list) else []
        out.append({"title": cell(page.get("judul")),
                    "title_en": label(page.get("judul")),
                    "paragraphs": [str(x)[:2000] for _i, x in paragraphs],
                    "paragraphs_en": [prose(x, english[i] if i < len(english) else None, 2000)
                                      for i, x in paragraphs],
                    "exhibits": exhibits})
    return out


def create_app(outdir: str | Path = "out/demo", reports: str | Path | None = None,
               want_pdf: bool = False, static_dir: str | Path | None = STATIC_DIR) -> FastAPI:
    jobs = ResearchJobs(outdir, reports, want_pdf)

    @asynccontextmanager
    async def lifespan(_app):
        yield
        jobs.close()

    app = FastAPI(title="Sectoral", lifespan=lifespan, docs_url="/api/docs",
                  openapi_url="/api/openapi.json", redoc_url=None)
    app.state.jobs = jobs

    def data(payload, status_code=200):
        return JSONResponse(payload, status_code=status_code, headers=_NO_STORE)

    @app.get("/api/tickers")
    def tickers():
        # Suggest only issuers with a full report in the gallery; the others
        # stay hidden from the research launcher and the search palette.
        published = set(outputs.tickers(outputs.REPORT, jobs.reports))
        return data({"tickers": [t for t in available_tickers() if t in published]})

    @app.get("/api/config")
    def config():
        return data({"live_runs": live_runs(),
                     "review": reviewer_auth.approvals_enabled()})

    @app.get("/api/history")
    def history():
        return data({"items": _history(jobs.reports)})

    @app.get("/api/reports")
    def reports_list():
        return data({"items": gallery.load(jobs.reports)})

    @app.get("/api/reports/{ticker}/trace")
    def report_trace(ticker: str):
        t = ticker.upper()
        if not gallery.is_publishable(jobs.reports, t):
            raise HTTPException(404, "Jejak riset tidak ditemukan.")
        doc = outputs.load(outputs.REPORT, jobs.reports, t) if TICKER.fullmatch(t) else None
        view = trace_view.build(outputs.load(outputs.TRACE, jobs.reports, t)
                                if TICKER.fullmatch(t) else None, doc)
        if view is None:
            raise HTTPException(404, "Jejak riset tidak ditemukan.")
        view["audit_appendix"] = _audit_appendix(doc)
        # A report can be public without an approval (automatic publication).
        view["review_state"] = assumption_review.status(jobs.reports, t)["state"]
        return data(view)

    @app.get("/api/reports/{ticker}/trace/preview")
    def report_trace_preview(ticker: str,
                             x_review_token: str | None = Header(default=None)):
        """Reviewer-only preview for reports that are not public yet."""
        if not review_token_ok(x_review_token):
            raise HTTPException(403, "Token reviewer tidak valid atau review belum diaktifkan.")
        t = ticker.upper()
        if not TICKER.fullmatch(t):
            raise HTTPException(404, "Jejak riset tidak ditemukan.")
        doc = outputs.load(outputs.REPORT, jobs.reports, t)
        view = trace_view.build(outputs.load(outputs.TRACE, jobs.reports, t), doc)
        if view is None:
            raise HTTPException(404, "Jejak riset tidak ditemukan.")
        view["audit_appendix"] = _audit_appendix(doc)
        view["review_state"] = assumption_review.status(jobs.reports, t)["state"]
        return data(view)

    @app.get("/api/reports/{ticker}/artifact-preview/{kind}")
    def report_artifact_preview(ticker: str, kind: str,
                                x_review_token: str | None = Header(default=None)):
        """Serve the exact report bundle to an authenticated reviewer only."""
        if not review_token_ok(x_review_token):
            raise HTTPException(403, "Token reviewer tidak valid atau review belum diaktifkan.")
        t = ticker.upper()
        if not TICKER.fullmatch(t) or kind not in gallery.PREVIEW_FILES:
            raise HTTPException(404, "Pratinjau laporan tidak ditemukan.")
        found = gallery.artifact(jobs.reports, t, kind)
        if found is None:
            raise HTTPException(404, "Pratinjau laporan tidak ditemukan.")
        return FileResponse(found[0], media_type=found[1], headers={"Cache-Control": "no-store"})

    @app.get("/api/reports/{ticker}/review")
    def report_review(ticker: str, x_review_token: str | None = Header(default=None)):
        t = ticker.upper()
        if not TICKER.fullmatch(t) or not outputs.exists(outputs.REPORT, jobs.reports, t):
            raise HTTPException(404, "Laporan tidak ditemukan.")
        enabled = reviewer_auth.approvals_enabled()
        if not review_token_ok(x_review_token):
            review_state = assumption_review.status(jobs.reports, t)["state"]
            if review_state != "approved":
                return data({"state": review_state, "enabled": enabled})
            # Publication makes the reviewer attestation public, but the current
            # editable Forecast Plan values remain available only to reviewers.
            public_view = assumption_review.public(jobs.reports, t)
            public_view.pop("fields", None)
            public_view.pop("attestation_schema", None)
            return data({**public_view, "enabled": enabled})
        identity = reviewer_auth.authenticate(x_review_token)
        publication = assumption_review.public(jobs.reports, t)
        manifest = outputs.load(outputs.MANIFEST, jobs.reports, t)
        publication_id = manifest.get("publication_id") if isinstance(manifest, dict) else None
        predecessor_id = publication_archive.predecessor_candidate(
            jobs.reports, t, publication_id) if publication_id else None
        return data({**publication,
                     "enabled": enabled,
                     "attestation_draft": (assumption_review.attestation_draft(jobs.reports, t)
                                           if identity else None),
                     "predecessor_publication_id": predecessor_id,
                     "supersession_required": predecessor_id is not None,
                     "current_reviewer": ({"id": identity["id"], "name": identity["name"],
                                           "role": identity["role"]}
                                          if identity else None)})

    @app.post("/api/reports/{ticker}/review")
    def report_approve(ticker: str, body: ReviewRequest,
                       x_review_token: str | None = Header(default=None)):
        t = ticker.upper()
        if not TICKER.fullmatch(t) or not outputs.exists(outputs.REPORT, jobs.reports, t):
            raise HTTPException(404, "Laporan tidak ditemukan.")
        identity = reviewer_auth.authenticate(x_review_token)
        if identity is None:
            raise HTTPException(403, "Token reviewer tidak valid atau review belum diaktifkan.")
        if not release_policy.role_may(identity["role"], "approve"):
            raise HTTPException(403, "Identitas ini tidak memiliki peran reviewer.")
        manifest = outputs.load(outputs.MANIFEST, jobs.reports, t)
        publication_id = manifest.get("publication_id") if isinstance(manifest, dict) else None
        try:
            predecessor_id = publication_archive.predecessor_candidate(
                jobs.reports, t, publication_id) if publication_id else None
        except publication_archive.PublicationHistoryError as error:
            raise HTTPException(409, str(error)) from None
        if predecessor_id and len(body.supersession_reason.strip()) < 12:
            raise HTTPException(400, "Alasan penggantian publikasi wajib diisi (minimal 12 karakter).")
        try:
            record = assumption_review.approve(
                jobs.reports, t, identity["name"], body.note,
                [edit.model_dump() for edit in body.edits],
                attestation=body.attestation,
                reviewer_identity={"id": identity["id"], "name": identity["name"],
                                   "role": identity["role"],
                                   "source": "authenticated_registry"})
        except assumption_review.ReviewError as error:
            raise HTTPException(400, str(error)) from None
        try:
            lineage = publication_archive.record_approved_publication(
                jobs.reports, t, reviewer_token=x_review_token,
                supersession_reason=body.supersession_reason)
        except publication_archive.PublicationMutationDenied as error:
            raise HTTPException(403, str(error)) from None
        except publication_archive.SupersessionReasonRequired as error:
            raise HTTPException(400, str(error)) from None
        except publication_archive.PublicationHistoryError as error:
            raise HTTPException(409, str(error)) from None
        except publication_archive.UnknownPublicationError as error:
            raise HTTPException(404, str(error)) from None
        except ValueError as error:
            raise HTTPException(400, str(error)) from None
        return data({"record": record, "lineage": lineage,
                     **assumption_review.public(jobs.reports, t)})

    @app.get("/api/reports/{ticker}/run")
    def report_run(ticker: str):
        t = ticker.upper()
        if not TICKER.fullmatch(t) or not gallery.is_publishable(jobs.reports, t):
            raise HTTPException(404, "Run tersimpan tidak ditemukan.")
        found = run_events.replay(jobs.reports, t)
        if found is None:
            raise HTTPException(404, "Run tersimpan tidak ditemukan.")
        return data(found)

    @app.get("/api/reports/{ticker}/archives")
    def report_archives(ticker: str):
        """List verified prior publications with explicit archived identity."""
        t = ticker.upper()
        if not TICKER.fullmatch(t):
            raise HTTPException(404, "Arsip laporan tidak ditemukan.")
        items = []
        for manifest in publication_archive.list_archives(jobs.reports, t):
            publication_id = manifest.get("publication_id")
            hashes = manifest.get("artifact_hashes") or {}
            file_names = manifest.get("files") or {}
            if not isinstance(publication_id, str):
                continue
            lineage = publication_archive.publication_history(
                jobs.reports, t, publication_id)
            publication_state = lineage.get("state")
            files = {}
            for route_kind, (archive_kind, _) in _ARCHIVE_KINDS.items():
                if (publication_state not in {"withdrawn", "history_invalid"}
                        and archive_kind in file_names
                        and isinstance(hashes.get(archive_kind), str)):
                    files[route_kind] = (f"/files/reports/{t}/archives/"
                                         f"{publication_id}/{route_kind}")
                else:
                    files[route_kind] = None
            items.append({"state": "withdrawn" if publication_state == "withdrawn" else "archived",
                          "publication_state": publication_state, "ticker": t,
                          "publication_id": publication_id,
                          "archived_at": manifest.get("archived_at"),
                          "review_sha": manifest.get("review_sha"),
                          "predecessor_publication_id": lineage.get("predecessor_publication_id"),
                          "successor_publication_id": lineage.get("successor_publication_id"),
                          "supersession_reason": lineage.get("supersession_reason"),
                          "withdrawal_reason": lineage.get("withdrawal_reason"),
                          "withdrawn_at": lineage.get("withdrawn_at"),
                          "artifact_hashes": {key: hashes.get(key) for key in (
                              "html", "pdf", "trace_html", "html_en", "pdf_en")},
                          "files": files})
        return data({"ticker": t, "items": items})

    @app.post("/api/reports/{ticker}/archives/{publication_id}/withdraw")
    def withdraw_report_publication(ticker: str, publication_id: str, body: WithdrawalRequest,
                                    x_review_token: str | None = Header(default=None)):
        """Withdraw a verified publication while preserving its archived bundle."""
        t = ticker.upper()
        if not TICKER.fullmatch(t):
            raise HTTPException(404, "Arsip laporan tidak ditemukan.")
        identity = reviewer_auth.authenticate(x_review_token)
        if identity is None or not release_policy.role_may(identity["role"], "withdraw"):
            raise HTTPException(403, "Token tidak memiliki peran reviewer atau compliance.")
        try:
            lineage = publication_archive.withdraw_publication(
                jobs.reports, t, publication_id, reason=body.reason,
                reviewer_token=x_review_token)
        except publication_archive.PublicationMutationDenied as error:
            raise HTTPException(403, str(error)) from None
        except publication_archive.UnknownPublicationError as error:
            raise HTTPException(404, str(error)) from None
        except publication_archive.PublicationHistoryError as error:
            raise HTTPException(409, str(error)) from None
        except ValueError as error:
            raise HTTPException(400, str(error)) from None
        return data({"ticker": t, "publication_id": publication_id,
                     "state": "withdrawn", "lineage": lineage})

    @app.get("/files/reports/{ticker}/archives/{publication_id}/{kind}")
    def archived_report_file(ticker: str, publication_id: str, kind: str):
        """Serve a hash-verified historical artifact from an approved bundle."""
        t = ticker.upper()
        mapped = _ARCHIVE_KINDS.get(kind)
        if not TICKER.fullmatch(t) or mapped is None:
            raise HTTPException(404, "Arsip laporan tidak ditemukan.")
        state = publication_archive.publication_state(jobs.reports, t, publication_id)
        if state == "withdrawn":
            raise HTTPException(410, "Publikasi ini telah ditarik.")
        if state in {"history_invalid", "unknown"}:
            raise HTTPException(404, "Arsip laporan tidak ditemukan.")
        path = publication_archive.artifact(jobs.reports, t, publication_id, mapped[0])
        if path is None:
            raise HTTPException(404, "Arsip laporan tidak ditemukan.")
        return FileResponse(path, media_type=mapped[1],
                            headers={"Cache-Control": "public, max-age=31536000, immutable",
                                     "X-Sektoral-Artifact-State": "archived"})

    @app.post("/api/jobs", status_code=201)
    def submit(body: JobRequest, x_run_token: str | None = Header(default=None)):
        mode = live_runs()
        if mode == "off" or (mode == "token" and not run_token_ok(x_run_token)):
            raise HTTPException(403, "Riset langsung dibatasi di situs ini; putar ulang run emiten "
                                     "yang sudah diriset, atau masukkan token riset.")
        try:
            job_id = jobs.submit(body.ticker)
        except ValueError:
            raise HTTPException(400, "Masukkan kode emiten yang valid.") from None
        return data({"id": job_id}, 201)

    @app.get("/api/jobs/{job_id}")
    def job(job_id: str):
        snapshot = jobs.snapshot(job_id) if jobs_id_ok(job_id) else None
        if snapshot is None:
            raise HTTPException(404, "Riset tidak ditemukan.")
        return data(snapshot)

    @app.get("/api/jobs/{job_id}/trace")
    def job_trace(job_id: str):
        # Job IDs identify execution attempts, not approved publication bundles.
        # Public traces use /api/reports/{ticker}/trace after the bundle passes review.
        raise HTTPException(404, "Jejak riset tidak ditemukan.")

    def cover_png(ticker: str, lang: str):
        try:
            png = gallery.cover(jobs.reports, ticker, lang)
        except Exception:
            LOG.exception("cover thumbnail failed")
            png = None
        if png is None:
            raise HTTPException(404)
        return FileResponse(png, media_type="image/png", headers=_REVALIDATE)

    @app.get("/files/reports/{ticker}/cover.png")
    def cover(ticker: str):
        return cover_png(ticker, "id")

    # The English PDF's cover, while that PDF is in the published bundle.
    @app.get("/files/reports/{ticker}/cover.en.png")
    def cover_en(ticker: str):
        return cover_png(ticker, "en")

    @app.get("/files/reports/{name}")
    def report_file(name: str):
        match = _REPORT_FILE.fullmatch(name)
        found = gallery.public_artifact(jobs.reports, match.group(1), _KIND[match.group(2)]) if match else None
        if found is None:
            raise HTTPException(404)
        return FileResponse(found[0], media_type=found[1], headers=_REVALIDATE)

    @app.get("/files/jobs/{job_id}/{name}")
    def job_file(job_id: str, name: str):
        # A run directory is mutable and can be superseded. It is never a
        # public artifact namespace; snapshots link to the gated gallery bundle.
        raise HTTPException(404)

    static = Path(static_dir).resolve() if static_dir else None
    if static and (static / "index.html").is_file():
        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            if path.startswith(("api/", "files/")):
                raise HTTPException(404)
            candidate = (static / path).resolve()
            if path and candidate.is_file() and static in candidate.parents:
                return FileResponse(candidate)
            return FileResponse(static / "index.html", headers=_NO_STORE)
    else:
        LOG.warning("No built frontend at %s; run `npm --prefix web run build`.", static)

    return app


def jobs_id_ok(job_id: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{32}", job_id))


def main(argv=None):
    import uvicorn

    parser = argparse.ArgumentParser(description="Sectoral web app (API + React frontend)")
    parser.add_argument("--out", default=os.environ.get("SECTORAL_OUT", "out/demo"),
                        help="generated research output directory")
    parser.add_argument("--reports", default=os.environ.get("SECTORAL_REPORTS"),
                        help="folder of finished reports for the gallery (default: <out>/reports)")
    parser.add_argument("--host", default=os.environ.get("SECTORAL_HOST", "127.0.0.1"),
                        help="bind address (default: localhost)")
    parser.add_argument("--port", type=int, default=int(os.environ.get("SECTORAL_PORT", "8765")))
    parser.add_argument("--pdf", action="store_true",
                        default=os.environ.get("SECTORAL_PDF", "") in ("1", "true", "yes"),
                        help="also render the PDF for browser runs")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    app = create_app(args.out, args.reports, args.pdf)
    print(f"Sectoral: http://{args.host}:{args.port}", flush=True)
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
