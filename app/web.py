"""Local browser interface for the Sektoral research workflow.

Run with ``python -m app.web``. The HTTP server binds to loopback by default
and only exposes the report and HTML audit trace produced for a submitted job.
"""
from __future__ import annotations

import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import html
import json
import logging
import re
import threading
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
import uuid

from . import landing, research

LOG = logging.getLogger(__name__)
_TICKER = re.compile(r"^[A-Z0-9][A-Z0-9.-]{0,9}$")
_JOB_ID = re.compile(r"^[0-9a-f]{32}$")
_SAFE_STATUS = re.compile(r"^[A-Za-z0-9_.-]{1,48}$")


def _embedded_font(filename: str) -> str:
    font_path = Path(__file__).resolve().parent / "assets" / "fonts" / filename
    try:
        encoded = base64.b64encode(font_path.read_bytes()).decode("ascii")
    except OSError:
        return ""
    return f"data:font/ttf;base64,{encoded}"


_FONT_FACES = (
    f"@font-face{{font-family:Roboto;src:url('{_embedded_font('Roboto-Regular.ttf')}') format('truetype');font-weight:400;font-style:normal}}"
    f"@font-face{{font-family:Roboto;src:url('{_embedded_font('Roboto-Bold.ttf')}') format('truetype');font-weight:700 900;font-style:normal}}"
    f"@font-face{{font-family:Roboto;src:url('{_embedded_font('Roboto-Italic.ttf')}') format('truetype');font-weight:400;font-style:italic}}"
)

_PAGE_STYLE = _FONT_FACES + """
*{box-sizing:border-box}body{margin:0;background:#fff;color:#333;
font:16px/1.6 Roboto,sans-serif}
header{background:#fff;border-bottom:1px solid #D9D9D9;
padding:20px max(22px,calc((100vw - 980px)/2))}
header p{margin:10px 0 0;color:#333;max-width:62ch}
.brand{display:flex;align-items:center}.brand svg{display:block;height:34px;width:auto}
main{max-width:980px;margin:32px auto;padding:0 20px}
.panel{background:#fff;border:1px solid #D9D9D9;border-radius:12px;padding:24px}
.eyebrow{color:#0928B1;text-transform:uppercase;
letter-spacing:.12em;font-size:12px;font-weight:700}h1{margin:0;font-size:24px}h2{font-size:21px;
margin:0 0 8px}p{margin:8px 0}.muted{color:#333}
.sr-only{position:absolute;width:1px;height:1px;margin:-1px;padding:0;overflow:hidden;
clip:rect(0 0 0 0);white-space:nowrap;border:0}
.formrow{display:flex;gap:12px;align-items:end;margin-top:20px}
label{display:block;font-size:14px;font-weight:700;margin-bottom:6px}
input{width:min(340px,65vw);padding:12px 13px;border:1px solid #D9D9D9;border-radius:8px;
font:inherit;text-transform:uppercase;color:#333;background:#fff}
input:hover{border-color:#0928B1}button{border:0;border-radius:8px;background:#0928B1;
color:#fff;padding:13px 18px;font:inherit;font-weight:700;cursor:pointer}
button:hover{background:#071f8a}button:disabled{opacity:.65;cursor:not-allowed}
.job{margin-top:20px}.status{display:inline-block;border-radius:99px;background:#efefef;
color:#333;padding:4px 11px;font-size:13px;font-weight:700}
.status.partial{background:#fff1d7;color:#744900}
.links{display:flex;gap:18px;margin-top:15px;flex-wrap:wrap}a{color:#0928B1;font-weight:700}
a:hover{text-decoration-thickness:2px}:focus-visible{outline:3px solid #0928B1;outline-offset:2px}
.note{border-top:1px solid #D9D9D9;margin-top:25px;padding-top:14px;font-size:13px;color:#333}
@media(max-width:560px){.formrow{align-items:stretch;flex-direction:column}button{width:100%}}
"""

# Sectoral wordmark: leading "S", then the "E" drawn as three horizontal bars
# (primary blue, teal, green), followed by "CTORAL". Inlined (hidden from
# assistive tech; the wrapping h1 carries the accessible name) so the page
# needs no extra asset route; the standalone accessible file lives at
# app/assets/brand/sectoral-logo.svg for reuse.
_LOGO_SVG = (
    "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 200 44\" aria-hidden=\"true\" "
    "focusable=\"false\"><text x=\"0\" y=\"33\" font-family=\"Roboto\" "
    "font-size=\"30\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#333333\">S</text>"
    "<rect x=\"26\" y=\"8\" width=\"24\" height=\"6\" rx=\"3\" fill=\"#0928B1\"/>"
    "<rect x=\"26\" y=\"19\" width=\"24\" height=\"6\" rx=\"3\" fill=\"#1DCD9F\"/>"
    "<rect x=\"26\" y=\"30\" width=\"24\" height=\"6\" rx=\"3\" fill=\"#3ED628\"/>"
    "<text x=\"58\" y=\"33\" font-family=\"Roboto\" "
    "font-size=\"30\" font-weight=\"700\" letter-spacing=\"1\" fill=\"#333333\">CTORAL</text></svg>"
)


def _page(job_id: str | None = None, error: str | None = None) -> bytes:
    job_markup = ""
    script = ""
    if error:
        job_markup = f"<div class='job status partial' role='alert'>{html.escape(error)}</div>"
    if job_id:
        job_markup = (
            "<section class='panel job' aria-live='polite'>"
            "<div class='eyebrow'>Status riset</div><h2 id='job-title'>Sedang menyiapkan riset</h2>"
            "<span id='job-state' class='status'>Menunggu</span>"
            "<p id='job-detail' class='muted'>Agent memeriksa data dari Sectors cache.</p>"
            "<div id='job-links' class='links'></div></section>"
        )
        script = f"""
<script>
const jobId={json.dumps(job_id)};
const stateEl=document.getElementById('job-state');
async function refreshJob(){{
  try{{
    const response=await fetch('/api/jobs/'+jobId,{{cache:'no-store'}});
    if(!response.ok) throw new Error('status');
    const job=await response.json();
    document.getElementById('job-title').textContent='Riset '+job.ticker;
    const labels={{pending:'Menunggu',running:'Sedang diproses',completed:'Selesai',error:'Tidak selesai'}};
    stateEl.textContent=labels[job.state]||'Status';
    stateEl.className='status'+(job.quality==='partial'?' partial':'');
    document.getElementById('job-detail').textContent=job.state==='error'
      ?'Proses riset mengalami kendala. Periksa log lokal untuk detail.'
      :job.state==='completed'
        ?(job.quality==='partial'?'Analisis parsial: bukti belum cukup untuk semua bagian.':'Laporan dan jejak validasi siap ditinjau.')
        :'Agent sedang memeriksa cache dan menyiapkan company update.';
    const links=document.getElementById('job-links');
    links.replaceChildren();
    if(job.report_url) addLink(links,job.report_url,'Buka company update');
    if(job.trace_url) addLink(links,job.trace_url,'Lihat jejak agent');
    if(job.state==='pending'||job.state==='running') setTimeout(refreshJob,900);
  }}catch(_error){{
    document.getElementById('job-detail').textContent='Status belum tersedia. Muat ulang halaman untuk mencoba lagi.';
  }}
}}
function addLink(parent,href,label){{const link=document.createElement('a');link.href=href;link.textContent=label;parent.appendChild(link);}}
refreshJob();
</script>"""
    page = f"""<!doctype html><html lang="id"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sectoral | Company update</title><style>{_PAGE_STYLE}</style>
<header><h1 class="brand"><span class="sr-only">Sectoral</span>{_LOGO_SVG}</h1><p>Riset perusahaan IDX dengan sumber dan batas bukti yang terlihat.</p></header>
<main><section class="panel"><div class="eyebrow">Sectors cache · analisis yang dapat ditinjau</div>
<h2>Buat company update</h2><p class="muted">Masukkan kode emiten untuk menjalankan agent, memeriksa bukti, dan menyusun ringkasan riset.</p>
<form action="/run" method="post"><div class="formrow"><div><label for="ticker">Kode emiten IDX</label>
<input id="ticker" name="ticker" maxlength="10" pattern="[A-Za-z0-9][A-Za-z0-9.\\-]{{0,9}}" placeholder="Contoh: AMMN" required autocomplete="off"></div>
<button type="submit">Mulai riset</button></div></form>
<div class="note">Hasil menyajikan informasi dan analisis, bukan rekomendasi investasi. Kesimpulan dapat parsial jika bukti cache belum cukup.</div></section>
{job_markup}</main>{script}</html>"""
    return page.encode("utf-8")


class ResearchWeb:
    """Job registry and bounded artifact access for one local server instance."""

    def __init__(self, outdir: str | Path):
        self.outdir = Path(outdir).resolve()
        self.outdir.mkdir(parents=True, exist_ok=True)
        self._jobs: dict[str, dict] = {}
        self._lock = threading.Lock()
        # A single worker keeps generated output writes predictable. Each run
        # also receives its own directory so repeated ticker runs stay stable.
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="sektoral-research")

    def submit(self, ticker: str) -> str:
        ticker = ticker.strip().upper()
        if not _TICKER.fullmatch(ticker):
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
            result = research.run(ticker, job_outdir, want_pdf=False)
            report = self._safe_known_artifact(job_id, ticker, "report")
            trace = self._safe_known_artifact(job_id, ticker, "trace")
            if report is None or trace is None:
                raise FileNotFoundError("research run did not produce expected HTML artifacts")
            is_partial = not bool(result.get("research_ok")) or "draft" in str(
                result.get("report_status", "")
            ).lower()
            status = result.get("report_status")
            safe_status = status if isinstance(status, str) and _SAFE_STATUS.fullmatch(status) else None
            with self._lock:
                self._jobs[job_id].update({
                    "state": "completed",
                    "quality": "partial" if is_partial else "complete",
                    "report_status": safe_status,
                })
        except Exception:
            # Details may contain credentials or cache material: keep them in
            # the local server log and return only a generic state to the page.
            LOG.exception("Local research job failed for %s", ticker)
            with self._lock:
                self._jobs[job_id].update({"state": "error", "quality": "partial"})

    def snapshot(self, job_id: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            result = {"ticker": job["ticker"], "state": job["state"]}
            if job["state"] in ("completed", "error"):
                result["quality"] = job.get("quality", "partial")
            if job["state"] == "completed":
                result["report_url"] = f"/artifact/{job_id}/report"
                result["trace_url"] = f"/artifact/{job_id}/trace"
                if job.get("report_status"):
                    result["report_status"] = job["report_status"]
            return result

    def artifact(self, job_id: str, kind: str) -> Path | None:
        if not _JOB_ID.fullmatch(job_id) or kind not in ("report", "trace"):
            return None
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job.get("state") != "completed":
                return None
            ticker = job["ticker"]
        return self._safe_known_artifact(job_id, ticker, kind)

    def _safe_known_artifact(self, job_id: str, ticker: str, kind: str) -> Path | None:
        path = self._known_artifact(job_id, ticker, kind)
        try:
            resolved = path.resolve(strict=True)
        except FileNotFoundError:
            return None
        expected_dir = (self.outdir / job_id).resolve()
        if resolved.parent != expected_dir or not resolved.is_file():
            return None
        return resolved

    def _known_artifact(self, job_id: str, ticker: str, kind: str) -> Path:
        filename = f"{ticker}.html" if kind == "report" else f"{ticker}-trace.html"
        return self.outdir / job_id / filename

    def close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)


def make_handler(app: ResearchWeb):
    class Handler(BaseHTTPRequestHandler):
        server_version = "SektoralLocal/1.0"

        def log_message(self, format, *args):
            LOG.info("%s - %s", self.address_string(), format % args)

        def _send(self, status: int, body: bytes, content_type: str):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urlsplit(self.path)
            path = parsed.path
            if path == "/":
                self._send(200, landing.render_landing().encode("utf-8"), "text/html; charset=utf-8")
                return
            if path == "/research":
                self._send(200, _page(), "text/html; charset=utf-8")
                return
            if path in {"/assets/brand/sectoral-logo.svg", "/assets/brand/research-flow.svg"}:
                filename = "sectoral-logo.svg" if path.endswith("sectoral-logo.svg") else "research-flow.svg"
                asset = Path(__file__).resolve().parent / "assets" / "brand" / filename
                try:
                    body = asset.read_bytes()
                except OSError:
                    self._send(404, b"Not found", "text/plain; charset=utf-8")
                    return
                self._send(200, body, "image/svg+xml; charset=utf-8")
                return
            if path.startswith("/jobs/"):
                job_id = path.removeprefix("/jobs/")
                snapshot = app.snapshot(job_id) if _JOB_ID.fullmatch(job_id) else None
                if snapshot is None:
                    self._send(404, _page(error="Run tidak ditemukan."), "text/html; charset=utf-8")
                else:
                    self._send(200, _page(job_id), "text/html; charset=utf-8")
                return
            if path.startswith("/api/jobs/"):
                job_id = path.removeprefix("/api/jobs/")
                snapshot = app.snapshot(job_id) if _JOB_ID.fullmatch(job_id) else None
                if snapshot is None:
                    self._send(404, b'{"error":"not found"}', "application/json; charset=utf-8")
                else:
                    self._send(200, json.dumps(snapshot).encode(), "application/json; charset=utf-8")
                return
            if path.startswith("/artifact/"):
                pieces = path.split("/")
                artifact = app.artifact(pieces[2], pieces[3]) if len(pieces) == 4 else None
                if artifact is None:
                    self._send(404, b"Not found", "text/plain; charset=utf-8")
                else:
                    self._send(200, artifact.read_bytes(), "text/html; charset=utf-8")
                return
            self._send(404, b"Not found", "text/plain; charset=utf-8")

        def do_POST(self):
            if urlsplit(self.path).path != "/run":
                self._send(404, b"Not found", "text/plain; charset=utf-8")
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if length < 1 or length > 4096:
                self._send(400, _page(error="Form riset tidak valid."), "text/html; charset=utf-8")
                return
            body = self.rfile.read(length)
            if self.headers.get_content_type() != "application/x-www-form-urlencoded":
                self._send(400, _page(error="Form riset tidak valid."), "text/html; charset=utf-8")
                return
            fields = parse_qs(body.decode("utf-8", errors="replace"), keep_blank_values=True)
            values = fields.get("ticker", [])
            if len(values) != 1 or not _TICKER.fullmatch(values[0].strip().upper()):
                self._send(400, _page(error="Masukkan kode emiten yang valid."), "text/html; charset=utf-8")
                return
            job_id = app.submit(values[0])
            self.send_response(303)
            self.send_header("Location", f"/jobs/{job_id}")
            self.send_header("Content-Length", "0")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()

    return Handler


def create_server(outdir: str | Path = "out/demo", host: str = "127.0.0.1", port: int = 8765):
    app = ResearchWeb(outdir)
    server = ThreadingHTTPServer((host, port), make_handler(app))
    server.research_app = app
    return server


def main(argv=None):
    parser = argparse.ArgumentParser(description="Local Sektoral research browser");
    parser.add_argument("--out", default="out/demo", help="generated research output directory")
    parser.add_argument("--host", default="127.0.0.1", help="bind address (default: localhost)")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    server = create_server(args.out, args.host, args.port)
    print(f"Sektoral local research UI: http://{args.host}:{server.server_address[1]}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.research_app.close()
        server.server_close()


if __name__ == "__main__":
    main()
