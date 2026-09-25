#!/usr/bin/env python3
"""Record the real local Sektoral research workflow with Playwright.

Example: ``python3 scripts/record_demo.py --ticker AMMN``

The script submits through the same browser form used in the demo. It never
creates sample report content: a recording is only considered successful after
the research job completes and both generated HTML pages load.
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import re
import sys
import threading
import time

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.server import create_app


_TICKER = re.compile(r"^[A-Z0-9][A-Z0-9.-]{0,9}$")


def normalize_ticker(value: str) -> str:
    ticker = value.strip().upper()
    if not _TICKER.fullmatch(ticker):
        raise ValueError("Ticker must be 1-10 letters/digits with optional dot or hyphen.")
    return ticker


def _start_server(outdir: Path):
    """Run the API + built React app on a free localhost port in a thread."""
    import socket
    import uvicorn

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(create_app(outdir), host="127.0.0.1", port=port,
                                           log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not server.started:
        if time.monotonic() > deadline or not thread.is_alive():
            raise RuntimeError("The local web server did not start.")
        time.sleep(0.05)
    return server, thread, f"http://127.0.0.1:{port}"


def record(ticker: str, video_dir: Path, timeout_seconds: int = 900,
           headless: bool = True, require_brief: bool = True) -> Path:
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is required for recording. Install it with `pip install playwright` "
            "and install Chromium with `playwright install chromium`."
        ) from exc

    ticker = normalize_ticker(ticker)
    video_dir.mkdir(parents=True, exist_ok=True)
    server, server_thread, base_url = _start_server(ROOT / "out" / "demo")
    video_path = None
    run_error = None
    # The UI returns generic failures, while the internal logger may include
    # exception text from a data provider. Keep that material out of the
    # screen-recording session's terminal output as well.
    app_logger = logging.getLogger("app.jobs")
    was_disabled = app_logger.disabled
    app_logger.disabled = True
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=headless)
            context = browser.new_context(
                viewport={"width": 1440, "height": 1000},
                record_video_dir=str(video_dir.resolve()),
                record_video_size={"width": 1440, "height": 1000},
            )
            page = context.new_page()
            try:
                page.goto(base_url, wait_until="networkidle")
                page.get_by_role("link", name="Coba riset emiten").first.click()
                page.wait_for_url("**/research")
                page.get_by_label("Kode emiten IDX").fill(ticker)
                page.get_by_role("button", name="Mulai riset").click()
                page.wait_for_url(re.compile(r"/jobs/[0-9a-f]{32}$"), timeout=15_000)
                job_id = page.url.rsplit("/", 1)[-1]

                deadline = time.monotonic() + timeout_seconds
                state = None
                while time.monotonic() < deadline:
                    response = page.request.get(f"{base_url}/api/jobs/{job_id}")
                    if not response.ok:
                        raise RuntimeError("The research job status could not be read.")
                    state = response.json()
                    if state.get("state") in ("completed", "error"):
                        break
                    page.wait_for_timeout(500)
                else:
                    raise PlaywrightTimeoutError(
                        f"Research job exceeded {timeout_seconds} seconds."
                    )

                # Give the live status and its final honest quality label time
                # to render before navigating to the generated pages.
                page.get_by_text(re.compile(r"^(Selesai|Selesai, parsial|Tidak selesai)$")).first.wait_for(
                    timeout=10_000)
                if state["state"] == "error":
                    raise RuntimeError(
                        "Research job failed. The browser shows the failure state; "
                        "no successful demo recording was produced."
                    )
                from app import outputs
                trace_data = outputs.load(outputs.TRACE, ROOT / "out" / "demo" / job_id, ticker) or {}
                if require_brief and not trace_data.get("research", {}).get("ok"):
                    raise RuntimeError(
                        "Research brief did not pass validation; failure capture is available "
                        "but no successful agent demo was produced."
                    )

                report_link = page.get_by_role("link", name="Buka company update")
                trace_link = page.get_by_role("link", name="Lihat jejak agent")
                report_url = report_link.get_attribute("href")
                trace_url = trace_link.get_attribute("href")
                if not report_url or not trace_url:
                    raise RuntimeError("The completed job did not provide both report links.")

                report_link.click()
                page.wait_for_load_state("domcontentloaded")
                if page.locator("body").inner_text().strip() == "Not found":
                    raise RuntimeError("The generated company update could not be opened.")

                # Show the generated research content at a readable pace. The
                # selectors come from the report renderer; there are no demo
                # overlays or substituted sample cards.
                report_cards = page.locator(".research-card")
                if report_cards.count():
                    _scroll_and_hold(page, report_cards.first)
                    report_citations = page.locator(".research-cite")
                    if report_citations.count():
                        _scroll_and_hold(page, report_citations.first)
                else:
                    research_heading = page.locator("h2.sec").filter(
                        has_text="Ringkasan riset berbantuan AI"
                    )
                    if research_heading.count():
                        _scroll_and_hold(page, research_heading.first)
                    else:
                        # Sparse evidence may produce an honest draft without
                        # a research card; keep a real report page on screen.
                        _scroll_and_hold(page, page.locator(".page").last)

                page.goto(base_url + trace_url, wait_until="networkidle")
                if page.get_by_text("Jejak riset tidak ditemukan").count():
                    raise RuntimeError("The generated agent trace could not be opened.")
                trace_sections = page.locator("main article")
                if trace_sections.count():
                    _scroll_and_hold(page, trace_sections.first)
                trace_citations = page.locator("main article li")
                if trace_citations.count():
                    _scroll_and_hold(page, trace_citations.first)
                else:
                    _scroll_and_hold(page, page.locator("h2").last)

                # Finish back on the company update with its research section
                # visible, so the recording ends on the user-facing result.
                page.goto(base_url + report_url, wait_until="domcontentloaded")
                if report_cards.count():
                    _scroll_and_hold(page, report_cards.first)
                else:
                    _scroll_and_hold(page, page.locator(".page").last)
            except Exception as exc:
                run_error = exc
            finally:
                # Video is finalized by closing its browser context, including
                # on job failure so the visible failure state is reviewable.
                context.close()
                video_path = Path(page.video.path())
                browser.close()
    finally:
        app_logger.disabled = was_disabled
        server.should_exit = True
        server_thread.join(timeout=5)

    if run_error is not None:
        if video_path and video_path.exists():
            print(f"Failure recording saved for review: {video_path}", file=sys.stderr)
        raise RuntimeError(str(run_error)) from run_error
    if not video_path or not video_path.exists():
        raise RuntimeError("Playwright did not produce a video file.")
    return video_path


def _scroll_and_hold(page, locator, milliseconds: int = 2500) -> None:
    """Bring an actual report element into view and leave it readable."""
    locator.evaluate("element => element.scrollIntoView({behavior: 'instant', block: 'start'})")
    page.wait_for_timeout(milliseconds)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Record a real local Sektoral research run")
    parser.add_argument("--ticker", default="AMMN", help="IDX ticker to research (default: AMMN)")
    parser.add_argument("--timeout-seconds", type=int, default=900,
                        help="maximum wait for the actual research job")
    parser.add_argument("--headed", action="store_true", help="show Chromium during recording")
    parser.add_argument("--allow-insufficient", action="store_true",
                        help="also accept a recording where the agent brief did not pass validation")
    parser.add_argument("--video-dir", type=Path, default=ROOT / "out" / "demo-video")
    args = parser.parse_args(argv)
    if args.timeout_seconds < 1:
        parser.error("--timeout-seconds must be positive")
    try:
        video_path = record(args.ticker, args.video_dir, args.timeout_seconds,
                            not args.headed, not args.allow_insufficient)
    except Exception as exc:
        print(f"Demo recording failed: {exc}", file=sys.stderr)
        return 1
    print(f"Raw demo video saved: {video_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
