"""Research jobs for the web app: a bounded registry and what it may expose.

The API server submits a ticker here, a worker thread runs the full research
pipeline into its own directory, and the browser polls a snapshot. Snapshots
carry only whitelisted fields: pipeline results and exceptions can contain
source data or credentials, so they stay in the local log.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import logging
import re
import shutil
import threading
from pathlib import Path
from urllib.parse import urlsplit
import uuid

from agents.analyst.run import verdict_code

from . import assumption_review, cache, gallery, outputs, progress, publication_archive, research

LOG = logging.getLogger(__name__)
TICKER = re.compile(r"^[A-Z0-9][A-Z0-9.-]{0,9}$")
JOB_ID = re.compile(r"^[0-9a-f]{32}$")
_SAFE_STATUS = re.compile(r"^[A-Za-z0-9_.-]{1,48}$")
_MAX_EVENTS = 600


def text(value, limit=400):
    """A display string, cut at a word boundary with an ellipsis when too long."""
    if not isinstance(value, (str, int, float)) or value is None:
        return None
    value = str(value)
    if len(value) <= limit:
        return value
    return value[:limit - 1].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"


def http_url(value):
    parts = urlsplit(str(value or ""))
    return str(value)[:500] if parts.scheme in ("http", "https") and parts.netloc else None


def public_intel(intel) -> dict | None:
    """Whitelist the analyst result fields the web app renders.

    English twins (``<field>_en``) pass through beside their Indonesian; results
    stored before them simply have none (None). ``verdict_code`` is the
    verdict's stable code, worked out for results stored before it."""
    if not isinstance(intel, dict) or not isinstance(intel.get("plan"), dict):
        return None
    plan, synthesis = intel["plan"], intel.get("synthesis") or {}
    changes = intel.get("changes") or {}
    signals = []
    for signal in intel.get("signals") or []:
        if not isinstance(signal, dict):
            continue
        row = {key: text(signal.get(key), 200) for key in
               ("id", "kind", "label", "label_en", "display", "note", "flag", "flag_en", "period",
                "median_display")}
        for key in ("rank", "n"):
            row[key] = signal.get(key) if isinstance(signal.get(key), int) else None
        if signal.get("kind") == "web":
            row["url"] = http_url(signal.get("url"))
        if signal.get("kind") == "peer":
            row["peers"] = [{"symbol": text(p.get("symbol"), 12), "display": text(p.get("display"), 40)}
                            for p in (signal.get("peers") or [])[:15] if isinstance(p, dict)]
        signals.append(row)

    def ids(values):
        return [text(x, 60) for x in (values or []) if isinstance(x, str)][:8]

    def texts(values, limit, count):
        """A parallel list of English twins, or None when there is none."""
        if not isinstance(values, list):
            return None
        return [text(x, limit) for x in values[:count]]

    return {
        "ticker": text(intel.get("ticker"), 12), "name": text(intel.get("name"), 120),
        "market_date": text(intel.get("market_date"), 20), "status": text(intel.get("status"), 20),
        "plan": {"question": text(plan.get("question"), 500), "source": text(plan.get("source"), 20),
                 "hypotheses": [text(h, 400) for h in (plan.get("hypotheses") or [])[:4]],
                 "question_en": text(plan.get("question_en"), 500),
                 "hypotheses_en": texts(plan.get("hypotheses_en"), 400, 4)},
        "steps": [{key: text(step.get(key), 240)
                   for key in ("tool", "why", "why_en", "summary", "status", "origin")}
                  for step in (intel.get("steps") or [])[:10] if isinstance(step, dict)],
        "signals": signals[:30],
        "peers": {key: text((intel.get("peers") or {}).get(key), 160) for key in ("basis", "group")},
        "web_news": {"window": text(((intel.get("web_news") or {}).get("window")), 40),
                     "items": [{"title": text(i.get("title"), 200), "url": http_url(i.get("url")),
                                "domain": text(i.get("domain"), 80), "date": text(i.get("date"), 12)}
                               for i in ((intel.get("web_news") or {}).get("items") or [])[:8]
                               if isinstance(i, dict) and http_url(i.get("url"))]},
        "synthesis": {
            "headline": text(synthesis.get("headline"), 400), "source": text(synthesis.get("source"), 20),
            "headline_en": text(synthesis.get("headline_en"), 400),
            "findings": [{"title": text(f.get("title"), 200), "interpretation": text(f.get("interpretation"), 900),
                          "caveat": text(f.get("caveat"), 400), "signal_ids": ids(f.get("signal_ids")),
                          "title_en": text(f.get("title_en"), 200),
                          "interpretation_en": text(f.get("interpretation_en"), 900),
                          "caveat_en": text(f.get("caveat_en"), 400)}
                         for f in (synthesis.get("findings") or [])[:4] if isinstance(f, dict)],
            "hypotheses": [{"index": h.get("index") if isinstance(h.get("index"), int) else None,
                            "verdict": text(h.get("verdict"), 30), "reason": text(h.get("reason"), 400),
                            "signal_ids": ids(h.get("signal_ids")),
                            "verdict_code": verdict_code(h), "reason_en": text(h.get("reason_en"), 400)}
                           for h in (synthesis.get("hypotheses") or [])[:4] if isinstance(h, dict)],
            "next_checks": [text(x, 200) for x in (synthesis.get("next_checks") or [])[:3]],
            "next_checks_en": texts(synthesis.get("next_checks_en"), 200, 3),
        },
        "changes": {"first_run": bool(changes.get("first_run")),
                    "same_market_date": bool(changes.get("same_market_date")),
                    "previous_run_at": text(changes.get("previous_run_at"), 40),
                    "previous_market_date": text(changes.get("previous_market_date"), 20),
                    "items": [{"kind": text(i.get("kind"), 20), "text": text(i.get("text"), 240)}
                              for i in (changes.get("items") or [])[:12] if isinstance(i, dict)]},
    }


def available_tickers() -> list[str]:
    """Tickers with a company report in the local Sectors data, for suggestions."""
    try:
        endpoints = cache.endpoints()
    except Exception:  # the form still works without suggestions
        LOG.warning("Ticker suggestions unavailable", exc_info=True)
        return []
    return sorted({
        match.group(1)
        for endpoint in endpoints
        if (match := re.fullmatch(r"/company/report/([A-Z0-9.-]{1,10})/", endpoint))
    })


class ResearchJobs:
    """Job registry and bounded artifact access for one server instance."""

    def __init__(self, outdir: str | Path, reports: str | Path | None = None, want_pdf: bool = False):
        self.outdir = Path(outdir).resolve()
        self.outdir.mkdir(parents=True, exist_ok=True)
        # Finished reports shown in the gallery and on the landing page.
        self.reports = Path(reports).resolve() if reports else self.outdir / "reports"
        self.want_pdf = want_pdf
        self._jobs: dict[str, dict] = {}
        self._lock = threading.Lock()
        # A single worker keeps generated output writes predictable. Each run
        # also receives its own directory so repeated ticker runs stay stable.
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="sektoral-research")

    def submit(self, ticker: str) -> str:
        ticker = ticker.strip().upper()
        if not TICKER.fullmatch(ticker):
            raise ValueError("Kode emiten tidak valid.")
        job_id = uuid.uuid4().hex
        with self._lock:
            self._jobs[job_id] = {"ticker": ticker, "state": "pending"}
        self._executor.submit(self._run, job_id, ticker)
        return job_id

    def _run(self, job_id: str, ticker: str) -> None:
        with self._lock:
            self._jobs[job_id]["state"] = "running"
        try:
            job_outdir = self.outdir / job_id
            job_outdir.mkdir(parents=True, exist_ok=True)

            def record(event):
                with self._lock:
                    events = self._jobs[job_id].setdefault("events", [])
                    if len(events) < _MAX_EVENTS:
                        events.append(event)

            with progress.capture(record):
                result = research.run(ticker, job_outdir, want_pdf=self.want_pdf)
            if self.artifact(job_id, f"{ticker}.html", require_done=False) is None or \
                    self.artifact(job_id, f"{ticker}-trace.html", require_done=False) is None:
                raise FileNotFoundError("research run did not produce expected HTML artifacts")
            is_partial = not bool(result.get("research_ok")) or "draft" in str(
                result.get("report_status", "")).lower()
            status = result.get("report_status")
            safe_status = status if isinstance(status, str) and _SAFE_STATUS.fullmatch(status) else None
            self._publish(job_outdir, ticker)
            with self._lock:
                self._jobs[job_id].update({
                    "state": "completed",
                    "quality": "partial" if is_partial else "complete",
                    "report_status": safe_status,
                    "intel": public_intel(result.get("intel")),
                })
        except Exception:
            # Details may contain credentials or source data: keep them in
            # the local server log and return only a generic state.
            LOG.exception("Local research job failed for %s", ticker)
            with self._lock:
                self._jobs[job_id].update({"state": "error", "quality": "partial"})

    def _publish(self, job_outdir: Path, ticker: str) -> None:
        """Copy a finished run into the reports folder so the gallery lists it."""
        try:
            self.reports.mkdir(parents=True, exist_ok=True)
            # Preserve the currently approved publication before replacing the
            # gallery's fixed ticker paths. Unapproved or stale runs are not
            # archived and remain subject to the usual review gate.
            review = assumption_review.status(self.reports, ticker)
            if (review.get("state") == "approved" and
                    all(kind in (review.get("artifact_hashes") or {})
                        for kind in assumption_review.REQUIRED_PUBLISH_ARTIFACTS)):
                archived = publication_archive.archive_approved_bundle(self.reports, ticker)
                if archived is None:
                    raise OSError(f"refusing to replace approved {ticker}: publication archive failed")
            for name in (f"{ticker}.html", f"{ticker}.pdf", f"{ticker}-trace.html",
                         f"{ticker}.en.html", f"{ticker}.en.pdf"):
                source = job_outdir / name
                if source.is_file():
                    shutil.copy2(source, self.reports / name)
                elif name not in (f"{ticker}.html", f"{ticker}-trace.html"):
                    # A run without PDF or English output must not inherit an older file.
                    (self.reports / name).unlink(missing_ok=True)
            outputs.copy(job_outdir, ticker, self.reports)
        except OSError:
            LOG.exception("Could not publish %s to the reports folder", ticker)
            # _run marks the job as errored on publication failure. Returning
            # normally would mark it complete and could make the prior
            # gallery report look like the output of this run.
            raise

    def snapshot(self, job_id: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            ticker = job["ticker"]
            result = {"id": job_id, "ticker": ticker, "state": job["state"],
                      "events": list(job.get("events") or [])}
            if job["state"] in ("completed", "error"):
                result["quality"] = job.get("quality", "partial")
            if job["state"] == "completed":
                # Completed output stays private until the gallery's current
                # report bundle is analytically eligible and analyst-approved.
                if gallery.is_publishable(self.reports, ticker):
                    if gallery.public_artifact(self.reports, ticker, "html"):
                        result["report_url"] = f"/files/reports/{ticker}.html"
                    if gallery.public_artifact(self.reports, ticker, "trace"):
                        result["trace_url"] = f"/laporan/{ticker}/jejak"
                    if gallery.public_artifact(self.reports, ticker, "pdf"):
                        result["pdf_url"] = f"/files/reports/{ticker}.pdf"
                result["gallery_url"] = "/laporan"
                if job.get("report_status"):
                    result["report_status"] = job["report_status"]
                if job.get("intel"):
                    result["intel"] = job["intel"]
            return result

    def artifact(self, job_id: str, name: str, require_done: bool = True) -> Path | None:
        """``TICKER.html`` or ``TICKER-trace.html`` of one job.

        Paths are resolved (symlinks included) and must stay inside the job's
        own directory; anything else is None.
        """
        if not JOB_ID.fullmatch(job_id):
            return None
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or (require_done and job.get("state") != "completed"):
                return None
            ticker = job["ticker"]
        if name not in (f"{ticker}.html", f"{ticker}-trace.html"):
            return None
        expected_dir = (self.outdir / job_id).resolve()
        try:
            resolved = (self.outdir / job_id / name).resolve(strict=True)
        except (FileNotFoundError, OSError):
            return None
        if resolved.parent != expected_dir or not resolved.is_file():
            return None
        return resolved

    def trace(self, job_id: str) -> dict | None:
        """The stored audit trace of a completed job."""
        if not JOB_ID.fullmatch(job_id):
            return None
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job.get("state") != "completed":
                return None
            ticker = job["ticker"]
        trace = outputs.load(outputs.TRACE, self.outdir / job_id, ticker)
        return trace if isinstance(trace, dict) else None

    def close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
