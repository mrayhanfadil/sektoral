"""HTTP routing checks for the public landing page and research form."""
from __future__ import annotations

import re
import sys
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import web  # noqa: E402


class Server:
    def __init__(self, outdir: Path):
        self.httpd = web.create_server(outdir, port=0)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.httpd.server_address[:2]
        self.base = f"http://{host}:{port}"

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        getattr(self.httpd, "research_app").close()
        self.thread.join(timeout=2)


def get(base: str, path: str):
    try:
        with urlopen(base + path, timeout=3) as response:
            return response.status, response.headers, response.read()
    except HTTPError as error:
        return error.code, error.headers, error.read()


def test_root_is_showcase_and_research_form_has_its_own_route(tmp_path):
    server = Server(tmp_path)
    try:
        status, headers, body = get(server.base, "/")
        page = body.decode("utf-8")
        assert status == 200
        assert headers.get_content_type() == "text/html"
        assert "Coba riset emiten" in page
        assert 'href="/research"' in page
        assert 'name="ticker"' not in page

        form_status, form_headers, form_body = get(server.base, "/research")
        form = form_body.decode("utf-8")
        assert form_status == 200
        assert form_headers.get_content_type() == "text/html"
        assert 'name="ticker"' in form
        assert "Mulai riset" in form
        assert "bukan rekomendasi investasi" in form
        for html in (page, form):
            visible = re.sub(r"<(script|style)[^>]*>[\s\S]*?</\1>", " ", html, flags=re.IGNORECASE)
            visible = re.sub(r"<!--[\s\S]*?-->|<[^>]+>", " ", visible).lower()
            assert "cache" not in visible
    finally:
        server.close()


def test_brand_assets_are_served_as_svg_only_from_allowlisted_paths(tmp_path):
    server = Server(tmp_path)
    try:
        for path in ("/assets/brand/sectoral-logo.svg", "/assets/brand/research-flow.svg"):
            status, headers, body = get(server.base, path)
            assert status == 200
            assert headers.get_content_type() == "image/svg+xml"
            assert body.lstrip().startswith(b"<svg")
        assert get(server.base, "/assets/brand/../../README.md")[0] == 404
    finally:
        server.close()
