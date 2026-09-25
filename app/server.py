"""Sectoral web server: JSON API, generated documents and the React app.

Run with ``python -m app.server`` after building the frontend
(``npm --prefix web run build``). The server binds to loopback unless told
otherwise; the Docker image binds to all interfaces inside the container.

Routes:

* ``/api/...``   JSON for the React app (tickers, research history, reports,
  research jobs, audit traces). Only whitelisted fields are returned.
* ``/files/...`` generated documents: company update HTML/PDF, the standalone
  trace HTML and report cover thumbnails, each confined to its folder.
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

from . import assumption_review, gallery, outputs, run_events, trace_view
from .jobs import ResearchJobs, TICKER, available_tickers
from agents.analyst import memory as agent_memory

LOG = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "web" / "dist"
_REPORT_FILE = re.compile(r"^([A-Z0-9]{2,6})(\.html|\.pdf|-trace\.html)$")
_KIND = {".html": "html", ".pdf": "pdf", "-trace.html": "trace"}
_NO_STORE = {"Cache-Control": "no-store"}


class JobRequest(BaseModel):
    ticker: str


class ReviewEdit(BaseModel):
    path: str
    value: float
    reason: str


class ReviewRequest(BaseModel):
    reviewer: str
    note: str = ""
    edits: list[ReviewEdit] = []


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
    """Approvals need the reviewer token the server was started with
    (``SECTORAL_REVIEW_TOKEN``); without one, approving is switched off."""
    expected = os.environ.get("SECTORAL_REVIEW_TOKEN") or ""
    return bool(expected) and hmac.compare_digest(str(given or ""), expected)


def _history(reports: Path) -> list[dict]:
    try:
        rows = agent_memory.watchlist()[:6]
    except OSError:
        return []
    return [{"ticker": r["ticker"], "runs": r["runs"], "market_date": r.get("market_date"),
             "flags": r["flags"],
             "pdf_url": f"/files/reports/{r['ticker']}.pdf"
             if gallery.artifact(reports, r["ticker"], "pdf") else None}
            for r in rows]


def _audit_appendix(doc) -> list[dict]:
    """Report sections kept out of the printed report (``lampiran_audit``):
    their prose and tables, as plain text, bounded."""
    cell = lambda v: str(v if v is not None else "")[:300]
    out = []
    for page in ((doc or {}).get("lampiran_audit") or [])[:40]:
        if not isinstance(page, dict):
            continue
        exhibits = []
        for e in (page.get("exhibit") or [])[:8]:
            data = e.get("data") if isinstance(e.get("data"), dict) else {}
            if e.get("tipe") != "tabel" or not isinstance(data.get("rows"), list):
                continue
            exhibits.append({"title": cell(e.get("judul")),
                             "cols": [cell(c) for c in (data.get("cols") or [])[:12]],
                             "rows": [[cell(c) for c in row[:12]] for row in data["rows"][:60]
                                      if isinstance(row, list)],
                             "note": str(e.get("catatan_sumber") or "")[:1500]})
        out.append({"title": cell(page.get("judul")),
                    "paragraphs": [str(x)[:2000] for x in (page.get("paragraf") or [])[:8]
                                   if isinstance(x, str)],
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
                     "review": bool(os.environ.get("SECTORAL_REVIEW_TOKEN"))})

    @app.get("/api/history")
    def history():
        return data({"items": _history(jobs.reports)})

    @app.get("/api/reports")
    def reports_list():
        return data({"items": gallery.load(jobs.reports)})

    @app.get("/api/reports/{ticker}/trace")
    def report_trace(ticker: str):
        view = trace_view.build(outputs.load(outputs.TRACE, jobs.reports, ticker)
                                if TICKER.fullmatch(ticker.upper()) else None)
        if view is None:
            raise HTTPException(404, "Jejak riset tidak ditemukan.")
        view["audit_appendix"] = _audit_appendix(outputs.load(outputs.REPORT, jobs.reports, ticker.upper()))
        # A gallery report is published only once its plan is approved.
        review = assumption_review.status(jobs.reports, ticker.upper())
        view["review_state"] = review["state"]
        if review["state"] != "approved" and view["report"].get("published"):
            view["report"].update(published=False, rating=None, target_price=None, method=None,
                                  held_reason="menunggu persetujuan asumsi oleh analis")
        return data(view)

    @app.get("/api/reports/{ticker}/review")
    def report_review(ticker: str):
        t = ticker.upper()
        if not TICKER.fullmatch(t) or not outputs.exists(outputs.REPORT, jobs.reports, t):
            raise HTTPException(404, "Laporan tidak ditemukan.")
        return data({**assumption_review.public(jobs.reports, t),
                     "enabled": bool(os.environ.get("SECTORAL_REVIEW_TOKEN"))})

    @app.post("/api/reports/{ticker}/review")
    def report_approve(ticker: str, body: ReviewRequest,
                       x_review_token: str | None = Header(default=None)):
        t = ticker.upper()
        if not TICKER.fullmatch(t) or not outputs.exists(outputs.REPORT, jobs.reports, t):
            raise HTTPException(404, "Laporan tidak ditemukan.")
        if not review_token_ok(x_review_token):
            raise HTTPException(403, "Token reviewer tidak valid atau review belum diaktifkan.")
        try:
            record = assumption_review.approve(
                jobs.reports, t, body.reviewer, body.note,
                [edit.model_dump() for edit in body.edits])
        except assumption_review.ReviewError as error:
            raise HTTPException(400, str(error)) from None
        return data({"record": record, **assumption_review.public(jobs.reports, t)})

    @app.get("/api/reports/{ticker}/run")
    def report_run(ticker: str):
        found = run_events.replay(jobs.reports, ticker) if TICKER.fullmatch(ticker.upper()) else None
        if found is None:
            raise HTTPException(404, "Run tersimpan tidak ditemukan.")
        return data(found)

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
        view = trace_view.build(jobs.trace(job_id)) if jobs_id_ok(job_id) else None
        if view is None:
            raise HTTPException(404, "Jejak riset tidak ditemukan.")
        return data(view)

    @app.get("/files/reports/{ticker}/cover.png")
    def cover(ticker: str):
        try:
            png = gallery.cover(jobs.reports, ticker)
        except Exception:
            LOG.exception("cover thumbnail failed")
            png = None
        if png is None:
            raise HTTPException(404)
        return FileResponse(png, media_type="image/png")

    @app.get("/files/reports/{name}")
    def report_file(name: str):
        match = _REPORT_FILE.fullmatch(name)
        found = gallery.artifact(jobs.reports, match.group(1), _KIND[match.group(2)]) if match else None
        if found is None:
            raise HTTPException(404)
        return FileResponse(found[0], media_type=found[1])

    @app.get("/files/jobs/{job_id}/{name}")
    def job_file(job_id: str, name: str):
        path = jobs.artifact(job_id, name)
        if path is None:
            raise HTTPException(404)
        return FileResponse(path, media_type="text/html; charset=utf-8")

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
